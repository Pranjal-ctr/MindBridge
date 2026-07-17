"""
Kio Conversations Service
Business logic for ChatGPT-style conversation management.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.conversations.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageCreate,
    MessageResponse,
)
from database.models import Conversation, Message, StudentProfile


async def create_conversation(
    db: AsyncSession,
    student_id: uuid.UUID,
    payload: ConversationCreate,
) -> ConversationResponse:
    """Create a new conversation for a student."""
    conversation = Conversation(
        conversation_id=uuid.uuid4(),
        student_id=student_id,
        title=payload.title or "New Conversation",
        ai_generated_title=False,  # Will be set True when Gemini generates a smart title
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return ConversationResponse.model_validate(conversation)


async def list_conversations(
    db: AsyncSession,
    student_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    include_archived: bool = False,
) -> tuple[list[ConversationResponse], int]:
    """List conversations for a student, newest first."""
    query = select(Conversation).where(Conversation.student_id == student_id)
    count_query = (
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.student_id == student_id)
    )

    if not include_archived:
        query = query.where(Conversation.is_archived == False)  # noqa: E712
        count_query = count_query.where(Conversation.is_archived == False)  # noqa: E712

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = (
        query.order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    conversations = result.scalars().all()

    return [ConversationResponse.model_validate(c) for c in conversations], total


async def get_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    student_id: uuid.UUID | None = None,
) -> Conversation:
    """Get a single conversation, optionally verify ownership."""
    query = select(Conversation).where(Conversation.conversation_id == conversation_id)

    if student_id:
        query = query.where(Conversation.student_id == student_id)

    result = await db.execute(query)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


async def update_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: ConversationUpdate,
) -> ConversationResponse:
    """Update conversation title or archive status."""
    conversation = await get_conversation(db, conversation_id, student_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conversation, field, value)

    if "title" in update_data:
        conversation.ai_generated_title = False

    await db.flush()
    await db.refresh(conversation)
    return ConversationResponse.model_validate(conversation)


async def delete_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    student_id: uuid.UUID,
) -> None:
    """Soft-delete a conversation by archiving it."""
    conversation = await get_conversation(db, conversation_id, student_id)
    conversation.is_archived = True
    await db.flush()


async def send_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    student_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MessageCreate,
) -> MessageResponse:
    """Add a message to a conversation."""
    # Verify conversation ownership
    conversation = await get_conversation(db, conversation_id, student_id)

    message = Message(
        message_id=uuid.uuid4(),
        conversation_id=conversation_id,
        sender_type="user",
        sender_id=user_id,
        message_text=payload.message_text,
        metadata_=None,
    )
    db.add(message)

    # Update conversation metadata (atomic increment -- concurrent sends must not lose updates)
    await db.execute(
        update(Conversation)
        .where(Conversation.conversation_id == conversation_id)
        .values(
            total_messages=Conversation.total_messages + 1,
            updated_at=datetime.now(timezone.utc),
        )
    )

    await db.flush()
    await db.refresh(message)
    return MessageResponse.model_validate(message)


async def get_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    student_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[MessageResponse], bool, str | None]:
    """
    Get messages in a conversation with cursor-based pagination.

    Returns:
        Tuple of (messages, has_more, next_cursor)
    """
    if student_id:
        await get_conversation(db, conversation_id, student_id)

    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )

    if cursor:
        try:
            cursor_id = uuid.UUID(cursor)
            # Get the message at the cursor
            cursor_result = await db.execute(
                select(Message.created_at).where(Message.message_id == cursor_id)
            )
            cursor_time = cursor_result.scalar_one_or_none()
            if cursor_time:
                query = query.where(Message.created_at > cursor_time)
        except ValueError:
            pass

    query = query.limit(limit + 1)  # Fetch one extra to check has_more
    result = await db.execute(query)
    messages = list(result.scalars().all())

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = str(messages[-1].message_id) if has_more and messages else None

    return [MessageResponse.model_validate(m) for m in messages], has_more, next_cursor


async def get_student_id_for_user(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    """Look up the student_id from a user_id."""
    result = await db.execute(
        select(StudentProfile.student_id).where(StudentProfile.user_id == user_id)
    )
    student_id = result.scalar_one_or_none()

    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )

    return student_id


async def send_ai_response(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    student_id: uuid.UUID,
    user_id: uuid.UUID,
    student_message_text: str,
) -> MessageResponse:
    """
    Generate and store a Comrade AI response.

    Called after the user's message is stored. Title generation and memory
    extraction run afterwards as background tasks (run_post_response_hooks)
    so the student gets their reply without waiting on auxiliary AI calls.
    """
    from app.ai.service import generate_comrade_response
    from app.config import settings
    from database.models import AIUsageLog

    # Verify conversation ownership
    conversation = await get_conversation(db, conversation_id, student_id)

    # Daily spend cap: count today's chat AI calls for this student
    usage_result = await db.execute(
        select(func.count())
        .select_from(AIUsageLog)
        .where(
            AIUsageLog.student_id == student_id,
            AIUsageLog.feature_name == "comrade_chat",
            AIUsageLog.created_at >= func.date_trunc("day", func.now()),
        )
    )
    if (usage_result.scalar() or 0) >= settings.AI_DAILY_MESSAGE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily message limit reached. Comrade will be ready to chat again tomorrow.",
        )

    # Generate AI response (provider routing, retry, and fallback in AIRouter)
    response_text, metadata = await generate_comrade_response(
        db, conversation_id, student_id, user_id, student_message_text
    )

    # Store AI message with metadata
    ai_message = Message(
        message_id=uuid.uuid4(),
        conversation_id=conversation_id,
        sender_type="ai",
        sender_id=None,
        message_text=response_text,
        metadata_=metadata,
    )
    db.add(ai_message)

    # Update conversation metadata (atomic increment -- see send_message)
    await db.execute(
        update(Conversation)
        .where(Conversation.conversation_id == conversation_id)
        .values(
            total_messages=Conversation.total_messages + 1,
            updated_at=datetime.now(timezone.utc),
        )
    )

    await db.flush()
    await db.refresh(ai_message)

    return MessageResponse.model_validate(ai_message)


async def run_post_response_hooks(
    conversation_id: uuid.UUID,
    student_id: uuid.UUID,
    student_user_id: uuid.UUID,
    student_message_id: uuid.UUID | None,
    student_message_text: str,
    ai_response_text: str,
) -> None:
    """
    Background task after a chat exchange: auto-title + memory extraction,
    then the intelligence pipeline (risk/emotion/stress analysis, wellness
    recalc, crisis workflow, timeline, parent insights).

    Runs after the HTTP response is sent, in its own DB session -- these
    auxiliary AI calls must not add latency to the chat request or hold
    its transaction open.
    """
    from app.ai.service import extract_memories, generate_conversation_title
    from app.intelligence.pipeline import run_intelligence_pipeline
    from database.session import async_session_factory

    try:
        async with async_session_factory() as db:
            conv_result = await db.execute(
                select(Conversation).where(Conversation.conversation_id == conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()
            if conversation is None:
                return

            # Auto-rename: after second AI response (total_messages >= 4)
            if conversation.total_messages >= 4 and not conversation.ai_generated_title:
                title = await generate_conversation_title(db, conversation_id)
                if title:
                    conversation.title = title
                    conversation.ai_generated_title = True
                    logger.info("Conversation %s renamed to: %s", conversation_id, title)

            # Memory extraction: the extraction itself filters for quality
            await extract_memories(
                db, student_id, conversation_id,
                student_message_text, ai_response_text,
            )

            await db.commit()
    except Exception as e:
        logger.warning("Post-response hooks failed (non-fatal): %s", str(e))

    # Intelligence pipeline (own session, each step individually non-fatal)
    try:
        await run_intelligence_pipeline(
            conversation_id, student_id, student_user_id, student_message_id
        )
    except Exception as e:
        logger.warning("Intelligence pipeline failed (non-fatal): %s", str(e))
