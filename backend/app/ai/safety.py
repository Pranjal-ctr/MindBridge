"""
MindBridge AI Safety Module
Detects safety-related keywords in messages and logs audit events.

Does NOT trigger workflows -- just logs for future risk detection.
"""

from __future__ import annotations

import re
import uuid

from database.models import AuditLog

# ===================================================================
# Safety Keyword Patterns
# ===================================================================

SAFETY_PATTERNS: dict[str, list[str]] = {
    "self_harm": [
        r"\bkill\s*my\s*self\b",
        r"\bsuicid\w*\b",
        r"\bself[\s-]*harm\b",
        r"\bcut\s*my\s*self\b",
        r"\bwant\s*to\s*die\b",
        r"\bend\s*my\s*life\b",
        r"\bend\s*it\s*all\b",
        r"\bnot\s*worth\s*living\b",
        r"\bbetter\s*off\s*dead\b",
        r"\bno\s*reason\s*to\s*live\b",
    ],
    "abuse": [
        r"\bbeing\s*abus\w*\b",
        r"\bhits?\s*me\b",
        r"\bbeat\w*\s*me\b",
        r"\btouche[sd]\s*me\b",
        r"\bmolest\w*\b",
        r"\bsexual\s*abuse\b",
        r"\bdomestic\s*violen\w*\b",
    ],
    "violence": [
        r"\bkill\s*(someone|him|her|them|people)\b",
        r"\bhurt\s*(someone|him|her|them|people)\b",
        r"\bbring\s*a\s*(gun|knife|weapon)\b",
        r"\bshoot\b",
        r"\bstab\b",
    ],
}

# Compile patterns for performance
_COMPILED_PATTERNS: dict[str, list[re.Pattern]] = {
    event_type: [re.compile(p, re.IGNORECASE) for p in patterns]
    for event_type, patterns in SAFETY_PATTERNS.items()
}


def detect_safety_events(message_text: str) -> list[str]:
    """
    Scan a message for safety-related keywords.

    Returns:
        List of event types detected (e.g., ["self_harm", "violence"])
    """
    detected = []
    for event_type, patterns in _COMPILED_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(message_text):
                detected.append(event_type)
                break  # One match per category is enough
    return detected


async def log_safety_events(
    conversation_id: uuid.UUID,
    student_user_id: uuid.UUID,
    message_text: str,
) -> list[str]:
    """
    Detect and log safety events from a message.

    Creates audit log entries for each detected event type, in a dedicated
    session committed immediately -- a self-harm/abuse signal must be
    persisted even if the surrounding chat request later fails and rolls back.

    Does NOT trigger any workflows -- just data for future risk detection.

    Returns:
        List of event types that were logged.
    """
    from database.session import async_session_factory

    events = detect_safety_events(message_text)
    if not events:
        return []

    async with async_session_factory() as db:
        for event_type in events:
            db.add(AuditLog(
                audit_id=uuid.uuid4(),
                user_id=student_user_id,
                action=f"safety_event:{event_type}",
                entity_type="conversation",
                entity_id=conversation_id,
            ))
        await db.commit()

    return events
