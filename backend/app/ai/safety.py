"""
Kio AI Safety Module
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

# Patterns are grouped category -> severity -> regexes.
#
#   "hard"  = high-precision, explicit signals. A hard match trips the keyword
#             tripwire (instant provisional alert to counselors) on the
#             synchronous path, independent of the LLM.
#   "soft"  = lower-precision / hyperbole-prone signals (e.g. "sab khatam").
#             These are audit-logged for context + evaluation but do NOT alert;
#             the LLM analysis (which sees the full message) weighs them. This
#             keeps false positives out of the counselor queue.
#
# Coverage is English + romanized Hindi/Hinglish + common misspellings, since
# Indian students rarely phrase distress in textbook English. Spelling varies
# a lot (nahi/nhi, mann/man, marna/mrna), so patterns stay deliberately loose.
#
# NOTE: this dict is the code-fallback. It is structured so the same shape can
# later be served from a DB table (Admin-editable, per-language, enable/disable)
# without changing the scanning logic below.
SAFETY_PATTERNS: dict[str, dict[str, list[str]]] = {
    "self_harm": {
        "hard": [
            # English
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
            r"\btake\s*my\s*own\s*life\b",
            r"\bhang\s*my\s*self\b",
            r"\boverdose\b",
            # Romanized Hindi / Hinglish
            r"jee?na?\s*nah?i\s*chah",        # jeena/jina nahi chahta
            r"jee?ne?\s*ka\s*man+\s*nah?i",   # jeene ka mann nahi
            r"m[ae]?r\s*jaa?na?\s*h",         # mar jana hai / marna hai
            r"mrna\s*h",                       # mrna hai (misspelling)
            r"m[ae]r\s*jau?ng",               # mar jaunga / jaungi
            r"khud-?kushi",
            r"atma-?hatya",
            r"jaan\s*de\s*d",                  # jaan de dunga
            r"khud\s*ko\s*khatam",
            r"zindagi\s*khatam",
            r"nas\s*kaat",                     # nas kaatna
        ],
    },
    "abuse": {
        "hard": [
            r"\bbeing\s*abus\w*\b",
            r"\bhits?\s*me\b",
            r"\bbeat\w*\s*me\b",
            r"\btouche[sd]\s*me\b",
            r"\bmolest\w*\b",
            r"\bsexual\s*abuse\b",
            r"\bdomestic\s*violen\w*\b",
            r"ghar\s*(me|mein)\s*maar",        # ghar me maarte hain
            r"(papa|mummy|maa|bhai)\s+(mujhe\s+|mereko\s+)?maar",  # papa (mujhe) maarte hain
            r"maar[\s-]?peet",
            r"galat\s*(tarah|tarike)\s*se\s*chua",
        ],
    },
    "violence": {
        "hard": [
            r"\bkill\s*(someone|him|her|them|people)\b",
            r"\bhurt\s*(someone|him|her|them|people)\b",
            r"\bbring\s*a\s*(gun|knife|weapon)\b",
            r"\bshoot\b",
            r"\bstab\b",
            r"jaan\s*se\s*maar",               # jaan se maar dunga
            r"goli\s*maar",
        ],
    },
    "hopelessness": {
        "soft": [
            r"sab\s*khatam",
            r"ab\s*aur\s*nah?i\s*hota",
            r"ko?i\s*faida\s*nah?i",
            r"kya\s*faida",
            r"kisi\s*ko\s*farak\s*nah?i",
            r"m[ae]in\s*bojh\s*(hoon|hu)",     # main bojh hoon
            r"\b(i\s*am|i'?m)\s*a\s*burden\b",
            r"\bno\s*(one|body)\s*cares\b",
            r"\bgive\s*up\b",
            r"haar\s*gaya",
            r"thak\s*gaya\s*(hoon|hu)",
            r"\bcan'?t\s*do\s*this\s*anymore\b",
        ],
    },
    "isolation": {
        "soft": [
            r"\b(i\s*am|i'?m)\s*(so\s*)?alone\b",
            r"\bno\s*friends\b",
            r"akela\s*(hoon|hu|feel|mehsoos)",
            r"ko?i\s*nah?i\s*hai\s*mera",
            r"sabne\s*chho?d\s*diya",
        ],
    },
    "running_away": {
        "soft": [
            r"\brun\s*away\b",
            r"\bleave\s*home\b",
            r"ghar\s*se\s*bhaag",
            r"bhaag\s*jau?ng",
            r"chho?d\s*ke\s*chala",
        ],
    },
    "panic": {
        "soft": [
            r"\bpanic\s*attack\b",
            r"\bcan'?t\s*breathe\b",
            r"saans\s*nah?i",
            r"ghabra(hat|ahat|ana)",
            r"(bahut|itna)\s*pressure",
            r"pressure\s*bahut",
            r"dab\s*gaya",
        ],
    },
    "bullying": {
        "soft": [
            r"\bbull(y|ied|ying)\b",
            r"\bharass\w*\b",
            r"tang\s*karte",
            r"chidha(te|na)",
            r"mazak\s*uda",
        ],
    },
}

# Compile patterns for performance: category -> severity -> [compiled]
_COMPILED_PATTERNS: dict[str, dict[str, list[re.Pattern]]] = {
    category: {
        severity: [re.compile(p, re.IGNORECASE) for p in patterns]
        for severity, patterns in by_severity.items()
    }
    for category, by_severity in SAFETY_PATTERNS.items()
}


def _scan(message_text: str) -> tuple[list[str], list[str]]:
    """Return (hard, soft) matched categories for a message.

    A category with any hard match is 'hard'; a category with only a soft match
    is 'soft'. One match per category is enough.
    """
    hard: list[str] = []
    soft: list[str] = []
    for category, by_severity in _COMPILED_PATTERNS.items():
        if any(p.search(message_text) for p in by_severity.get("hard", ())):
            hard.append(category)
        elif any(p.search(message_text) for p in by_severity.get("soft", ())):
            soft.append(category)
    return hard, soft


def detect_safety_events(message_text: str) -> list[str]:
    """Hard (alert-worthy) safety categories detected in a message.

    Back-compatible: returns the categories with an explicit, high-precision
    match (e.g. ["self_harm"]). Soft/hyperbole signals are excluded here --
    use scan_safety_signals() for those.
    """
    hard, _ = _scan(message_text)
    return hard


def scan_safety_signals(message_text: str) -> tuple[list[str], list[str]]:
    """(hard, soft) categories. Hard trips the counselor tripwire; soft is
    logged for context/evaluation and left for the LLM to weigh."""
    return _scan(message_text)

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

    A hard (explicit) match also raises an instant provisional risk assessment
    + counselor notifications (keyword tripwire) in the same committed session.
    Soft (hyperbole-prone) matches are logged as `safety_soft_signal:*` for
    context/evaluation but never alert -- the LLM analysis weighs them instead.

    Returns:
        List of event types that were logged (hard + soft).
    """
    from database.session import async_session_factory

    hard, soft = scan_safety_signals(message_text)
    if not hard and not soft:
        return []

    async with async_session_factory() as db:
        for event_type in hard:
            db.add(AuditLog(
                audit_id=uuid.uuid4(),
                user_id=student_user_id,
                action=f"safety_event:{event_type}",
                entity_type="conversation",
                entity_id=conversation_id,
            ))
        for event_type in soft:
            db.add(AuditLog(
                audit_id=uuid.uuid4(),
                user_id=student_user_id,
                action=f"safety_soft_signal:{event_type}",
                entity_type="conversation",
                entity_id=conversation_id,
            ))

        if hard:
            try:
                await _raise_keyword_tripwire(db, conversation_id, student_user_id, set(hard))
            except Exception as e:
                # Audit rows must still commit even if the tripwire fails
                logger.warning("Keyword tripwire failed (non-fatal): %s", str(e))

        await db.commit()
    return hard + soft

    return events
