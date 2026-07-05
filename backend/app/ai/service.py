"""
MindBridge Comrade AI Service
Core Gemini integration with prompt versioning, metadata tracking,
safety logging, memory extraction, title generation, and summary hooks.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import router as ai_router
from app.ai.prompts import (
    COMRADE_PROMPT_NAME,
    COMRADE_PROMPT_VERSION,
    COMRADE_SYSTEM_PROMPT,
    build_conversation_prompt,
)
from app.ai.safety import log_safety_events
from app.config import settings
from database.models import (
    AIPromptVersion,
    Conversation,
    MemoryItem,
    Message,
    StudentOnboarding,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Prompt Loading (DB-first, code-fallback)
# ===================================================================

async def _load_active_prompt(db: AsyncSession) -> tuple[str, str]:
    """
    Load the active Comrade prompt from the DB.
    Falls back to the hardcoded prompt in prompts.py.

    Returns:
        Tuple of (prompt_content, prompt_version)
    """
    result = await db.execute(
        select(AIPromptVersion).where(
            AIPromptVersion.prompt_name == COMRADE_PROMPT_NAME,
            AIPromptVersion.is_active == True,  # noqa: E712
        ).order_by(AIPromptVersion.created_at.desc()).limit(1)
    )
    db_prompt = result.scalar_one_or_none()

    if db_prompt:
        logger.info(
            "Loaded prompt from DB: %s %s",
            db_prompt.prompt_name,
            db_prompt.prompt_version,
        )
        return db_prompt.prompt_content, db_prompt.prompt_version

    logger.info("Using fallback prompt: %s", COMRADE_PROMPT_VERSION)
    return COMRADE_SYSTEM_PROMPT, COMRADE_PROMPT_VERSION


# ===================================================================
# Conversation History Builder
# ===================================================================

async def _load_conversation_history(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    max_messages: int = 20,
) -> list[dict]:
    """
    Load recent messages from a conversation for context.

    Returns:
        List of {"role": "user"|"model", "text": str}
    """
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(max_messages)
    )
    messages = list(reversed(result.scalars().all()))

    history = []
    for msg in messages:
        role = "model" if msg.sender_type == "ai" else "user"
        history.append({"role": role, "text": msg.message_text})

    return history


# ===================================================================
# Memory System
# ===================================================================

# Types that are always stored regardless of importance score
ALWAYS_STORE_TYPES = {"goal", "academic", "emotion", "relationship"}
IMPORTANCE_THRESHOLD = 0.75


async def load_student_memories(
    db: AsyncSession,
    student_id: uuid.UUID,
    max_memories: int = 5,
) -> str:
    """
    Load top memories for injection into the Comrade prompt.

    Strategy:
    1. Pinned memories are ALWAYS included (no limit)
    2. Top N non-pinned memories by importance + recency

    Returns:
        Formatted string for system prompt injection, or empty string.
    """
    # Load pinned memories
    pinned_result = await db.execute(
        select(MemoryItem)
        .where(
            MemoryItem.student_id == student_id,
            MemoryItem.is_pinned == True,  # noqa: E712
        )
        .order_by(MemoryItem.importance_score.desc().nullslast())
    )
    pinned = list(pinned_result.scalars().all())

    # Load top N non-pinned by importance + recency
    non_pinned_result = await db.execute(
        select(MemoryItem)
        .where(
            MemoryItem.student_id == student_id,
            MemoryItem.is_pinned == False,  # noqa: E712
        )
        .order_by(
            MemoryItem.importance_score.desc().nullslast(),
            MemoryItem.updated_at.desc(),
        )
        .limit(max_memories)
    )
    non_pinned = list(non_pinned_result.scalars().all())

    all_memories = pinned + non_pinned
    if not all_memories:
        return ""

    # Format for prompt injection
    lines = ["STUDENT CONTEXT (What you know about this student):"]
    for mem in all_memories:
        label = mem.memory_type.capitalize()
        pin_marker = " [PINNED]" if mem.is_pinned else ""
        lines.append(f"- {label}{pin_marker}: {mem.content}")

    return "\n".join(lines)


async def load_student_onboarding_context(
    db: AsyncSession,
    student_id: uuid.UUID,
) -> str:
    """
    Load the student's onboarding questionnaire as a prompt-injection block
    so Comrade can personalize tone and focus. Returns "" if not completed.
    """
    result = await db.execute(
        select(StudentOnboarding).where(StudentOnboarding.student_id == student_id)
    )
    ob = result.scalar_one_or_none()
    if ob is None:
        return ""

    lines = ["STUDENT PROFILE (from onboarding -- use to personalize your support):"]
    if ob.class_level:
        lines.append(f"- Class/Level: {ob.class_level}")
    if ob.help_goals:
        lines.append(f"- Wants help with: {', '.join(ob.help_goals)}")
    if ob.hobbies:
        lines.append(f"- Hobbies: {', '.join(ob.hobbies)}")
    if ob.strengths:
        lines.append(f"- Strengths: {', '.join(ob.strengths)}")
    if ob.interaction_style:
        lines.append(f"- Preferred interaction style: {ob.interaction_style} "
                     "(adapt your tone to this)")

    # Only the header means nothing useful was stored
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


async def extract_memories(
    db: AsyncSession,
    student_id: uuid.UUID,
    conversation_id: uuid.UUID,
    student_message: str,
    ai_response: str,
) -> list[dict]:
    """
    Extract memory-worthy information from a conversation exchange.

    Uses Gemini to analyze the exchange and extract structured memories.
    Only stores memories that meet the quality threshold.

    Returns:
        List of extracted memory dicts
    """
    extraction_prompt = """Analyze this conversation exchange between a student and their AI companion.
Extract any meaningful information worth remembering about the student.

ONLY extract if the information reveals something important about the student:
- Goals or aspirations
- Academic challenges or strengths
- Emotional state or recurring feelings
- Relationships (friends, family, teachers)
- Preferences or habits
- Important life events

Do NOT extract:
- Casual small talk ("I like pizza", "I'm tired")
- Temporary states ("I'm bored right now")
- Questions they're asking (unless revealing)

Respond with a JSON array. Each item should have:
- "type": one of "goal", "academic", "emotion", "relationship", "preference", "fact"
- "content": a concise summary (max 100 chars)
- "importance": 0.0 to 1.0 (how important is this to remember?)
- "confidence": 0.0 to 1.0 (how confident are you this is accurate?)

If nothing worth remembering, respond with: []

Student said: "{student_message}"
Comrade responded: "{ai_response}"
"""

    try:
        text_result, _ = await ai_router.run(
            db,
            feature="memory_extraction",
            system_prompt="",
            contents=[{
                "role": "user",
                "parts": [{"text": extraction_prompt.format(
                    student_message=student_message,
                    ai_response=ai_response,
                )}],
            }],
            temperature=0.2,
            max_output_tokens=512,
            conversation_id=conversation_id,
            student_id=student_id,
        )

        # Parse JSON response
        text = (text_result or "[]").strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()

        memories = json.loads(text)

        if not isinstance(memories, list):
            return []

        # Filter and store memories
        stored = []
        for mem in memories:
            mem_type = mem.get("type", "")
            importance = float(mem.get("importance", 0))
            confidence = float(mem.get("confidence", 0))
            content = mem.get("content", "").strip()

            if not content or not mem_type:
                continue

            # Smart filtering: only store meaningful memories
            if mem_type in ALWAYS_STORE_TYPES or importance >= IMPORTANCE_THRESHOLD:
                # Check for duplicate content (simple substring match)
                existing = await db.execute(
                    select(MemoryItem).where(
                        MemoryItem.student_id == student_id,
                        MemoryItem.memory_type == mem_type,
                        MemoryItem.content == content,
                    )
                )
                if existing.scalar_one_or_none():
                    continue  # Skip duplicate

                item = MemoryItem(
                    student_id=student_id,
                    memory_type=mem_type,
                    content=content[:200],  # Trim to reasonable length
                    importance_score=min(importance, 1.0),
                    confidence_score=min(confidence, 1.0),
                    source_conversation_id=conversation_id,
                )
                db.add(item)
                stored.append({"type": mem_type, "content": content})

        if stored:
            await db.flush()
            logger.info(
                "Extracted %d memories for student in conversation %s",
                len(stored), conversation_id,
            )

        return stored

    except Exception as e:
        logger.warning("Memory extraction failed (non-fatal): %s", str(e))
        return []


# ===================================================================
# Conversation Title Generation
# ===================================================================

async def generate_conversation_title(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> str | None:
    """
    Generate a descriptive title for a conversation using Gemini.

    Called after the first exchange (2-3 messages).
    Returns a concise 3-6 word title, or None on failure.
    """
    # Load the first few messages
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(4)
    )
    messages = result.scalars().all()

    if len(messages) < 2:
        return None

    exchange = "\n".join(
        f"{'Student' if m.sender_type == 'user' else 'Comrade'}: {m.message_text[:200]}"
        for m in messages
    )

    title_prompt = f"""Generate a concise 3-6 word title for this conversation.
The title should capture the main topic or theme.
Respond with ONLY the title, no quotes, no punctuation at the end.

Examples:
- Exam Stress Discussion
- Career Planning Chat
- Friendship Challenges
- Study Habits Improvement
- Feeling Lonely at School

Conversation:
{exchange}

Title:"""

    try:
        text_result, _ = await ai_router.run(
            db,
            feature="title_generation",
            system_prompt="",
            contents=[{
                "role": "user",
                "parts": [{"text": title_prompt}],
            }],
            temperature=0.3,
            max_output_tokens=20,
            conversation_id=conversation_id,
        )
        title = (text_result or "").strip().strip('"').strip("'")
        if title and len(title) <= 100:
            return title
        return None
    except Exception as e:
        logger.warning("Title generation failed (non-fatal): %s", str(e))
        return None


# ===================================================================
# Summary Generation Hook (placeholder for future use)
# ===================================================================

async def _maybe_trigger_summary_hook(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    total_messages: int,
) -> None:
    """
    Hook for future conversation summary generation.
    NOT IMPLEMENTED YET.
    """
    if total_messages >= settings.AI_SUMMARY_THRESHOLD:
        logger.debug(
            "Summary hook: conversation %s has %d messages (threshold: %d)",
            conversation_id,
            total_messages,
            settings.AI_SUMMARY_THRESHOLD,
        )
        pass


# ===================================================================
# Core: Generate AI Response
# ===================================================================

async def generate_comrade_response(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    student_id: uuid.UUID,
    student_user_id: uuid.UUID,
    student_message: str,
) -> tuple[str, dict]:
    """
    Generate a Comrade AI response using Gemini 2.5 Flash.

    Flow:
    1. Load active prompt from DB (or fallback)
    2. Load student memories and inject into prompt
    3. Load conversation history
    4. Build prompt payload
    5. Call Gemini API
    6. Log safety events
    7. Trigger summary hook if needed
    8. Return response text + metadata

    Args:
        db: Database session
        conversation_id: The conversation UUID
        student_id: The student profile UUID
        student_user_id: The student's user UUID (for audit logging)
        student_message: The new message from the student

    Returns:
        Tuple of (response_text, metadata_dict)
    """
    # 1. Load active prompt
    system_prompt, prompt_version = await _load_active_prompt(db)

    # 2. Load onboarding profile + memories and inject into system prompt
    onboarding_context = await load_student_onboarding_context(db, student_id)
    if onboarding_context:
        system_prompt = f"{system_prompt}\n\n{onboarding_context}"

    memory_context = await load_student_memories(db, student_id)
    if memory_context:
        system_prompt = f"{system_prompt}\n\n{memory_context}"

    # 3. Load conversation history
    history = await _load_conversation_history(
        db, conversation_id, settings.AI_MAX_CONTEXT_MESSAGES
    )

    # 4. Build prompt payload
    contents = build_conversation_prompt(system_prompt, history, student_message)

    # 5. Call the routed AI provider (retry + fallback handled by AIRouter)
    start_time = time.monotonic()
    try:
        response_text, call_metadata = await ai_router.run(
            db,
            feature="comrade_chat",
            system_prompt=system_prompt,
            contents=contents,
            temperature=0.7,
            max_output_tokens=1024,
            conversation_id=conversation_id,
            student_id=student_id,
        )
        response_text = response_text or "I'm here for you. Could you tell me more about what's on your mind?"
    except Exception as e:
        logger.error("AI provider error: %s", str(e))
        response_text = (
            "I'm having a moment -- could you try sending that again? "
            "I want to make sure I give you a thoughtful response."
        )
        prompt_version = f"{prompt_version}-error"
        call_metadata = {"response_time_ms": int((time.monotonic() - start_time) * 1000)}

    # 6. Log safety events (own session -- must survive request rollback)
    await log_safety_events(conversation_id, student_user_id, student_message)

    # 7. Build metadata
    metadata = {
        **call_metadata,
        "model": call_metadata.get("model", settings.GEMINI_MODEL),
        "prompt_version": prompt_version,
        "memories_injected": bool(memory_context),
    }

    # 8. Get conversation for summary hook
    conv_result = await db.execute(
        select(Conversation).where(Conversation.conversation_id == conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if conversation:
        await _maybe_trigger_summary_hook(
            db, conversation_id, conversation.total_messages
        )

    return response_text, metadata
