"""
MindBridge AI Safety Module
Detects safety-related keywords in messages, logs audit events, and raises an
instant provisional risk alert (keyword tripwire) for the most severe
categories.

The tripwire runs on the synchronous chat path, BEFORE the background AI
analysis -- so counselor alerting never depends on the LLM being up. The AI
pipeline later supersedes it with a scored assessment.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuditLog, RiskAssessment, StudentProfile, User

logger = logging.getLogger(__name__)

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


# Categories severe enough to raise an instant provisional risk alert
TRIPWIRE_CATEGORIES = {"self_harm", "abuse"}

# Skip duplicate tripwires for the same conversation within this window;
# the background AI analysis supersedes the provisional assessment anyway.
_TRIPWIRE_DEDUP_WINDOW = timedelta(hours=1)


async def _raise_keyword_tripwire(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    student_user_id: uuid.UUID,
    tripped: set[str],
) -> None:
    """Provisional risk assessment + counselor notifications on keyword match."""
    from app.intelligence.config import RISK_LEVEL_RANK, load_config
    from app.notifications.service import notify_users

    # Dedup: one pending tripwire per conversation per window
    cutoff = datetime.now(timezone.utc) - _TRIPWIRE_DEDUP_WINDOW
    existing = await db.execute(
        select(RiskAssessment.risk_id).where(
            RiskAssessment.conversation_id == conversation_id,
            RiskAssessment.generated_by == "keyword_tripwire",
            RiskAssessment.review_status == "pending",
            RiskAssessment.created_at >= cutoff,
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        return

    result = await db.execute(
        select(StudentProfile, User)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(StudentProfile.user_id == student_user_id)
    )
    row = result.one_or_none()
    if row is None:
        return
    profile, student_user = row

    crisis_cfg = await load_config(db, "crisis")
    level = crisis_cfg["tripwire_level"]

    db.add(RiskAssessment(
        student_id=profile.student_id,
        conversation_id=conversation_id,
        risk_level=level,
        trigger_reason=f"keyword: {', '.join(sorted(tripped))}",
        generated_by="keyword_tripwire",
        review_status="pending",
    ))

    # Escalate the profile immediately (never de-escalate from a tripwire)
    if RISK_LEVEL_RANK.get(level, 0) > RISK_LEVEL_RANK.get(profile.risk_level or "green", 0):
        profile.risk_level = level

    # Alert tenant counselors + school admins (content-free)
    staff_result = await db.execute(
        select(User.user_id).where(
            User.tenant_id == student_user.tenant_id,
            User.role.in_(["counselor", "school_admin"]),
            User.is_active == True,  # noqa: E712
        )
    )
    staff_ids = [r[0] for r in staff_result.all()]
    if staff_ids:
        await notify_users(
            db, staff_ids,
            title="High-risk alert",
            message=(
                f"High-risk alert: {student_user.first_name} {student_user.last_name} "
                "-- review required."
            ),
        )
    logger.info(
        "Keyword tripwire raised for conversation %s (categories: %s)",
        conversation_id, ", ".join(sorted(tripped)),
    )


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

    For self_harm/abuse matches, also raises an instant provisional risk
    assessment + counselor notifications (keyword tripwire) in the same
    committed session.

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

        tripped = TRIPWIRE_CATEGORIES & set(events)
        if tripped:
            try:
                await _raise_keyword_tripwire(db, conversation_id, student_user_id, tripped)
            except Exception as e:
                # Audit rows must still commit even if the tripwire fails
                logger.warning("Keyword tripwire failed (non-fatal): %s", str(e))

        await db.commit()

    return events
