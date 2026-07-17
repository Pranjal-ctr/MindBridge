"""
Parent insight generator (feature `parent_insight`): one LLM call that turns
aggregated signals into a readable narrative + recommendations + insight cards.

Privacy: the model receives ONLY aggregated data (wellness components, risk
trajectory scores/levels/summaries, emotion trends, stress distribution,
engagement counts) -- never conversation content.

Debounced: regenerates only when forced (crisis / risk-level change), when no
insight exists yet, or when the stored one is older than the configured TTL
and there has been new activity since.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import router as ai_router
from app.intelligence.config import load_config
from app.intelligence.parsing import parse_json_response
from app.intelligence.prompts import (
    PARENT_INSIGHT_PROMPT_NAME,
    PARENT_INSIGHT_PROMPT_VERSION,
    PARENT_INSIGHT_SYSTEM_PROMPT,
    load_prompt,
)
from app.intelligence.schemas import PARENT_INSIGHT_RESPONSE_SCHEMA, ParentInsightPayload
from database.models import (
    Conversation,
    EmotionSnapshot,
    Message,
    ParentInsightHistory,
    RiskAssessment,
    StressDistribution,
    StudentProfile,
    WellnessRecord,
    WellnessScore,
)

logger = logging.getLogger(__name__)


async def _new_activity_since(db: AsyncSession, student_id: uuid.UUID, since: datetime) -> bool:
    messages = (await db.execute(
        select(func.count()).select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.conversation_id)
        .where(
            Conversation.student_id == student_id,
            Message.sender_type == "user",
            Message.created_at > since,
        )
    )).scalar() or 0
    if messages:
        return True
    checkins = (await db.execute(
        select(func.count()).select_from(WellnessRecord).where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.created_at > since,
        )
    )).scalar() or 0
    return checkins > 0


async def _build_signal_summary(db: AsyncSession, student_id: uuid.UUID) -> str | None:
    """Aggregate-only input for the model. Returns None when there is no data."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    sections: list[str] = []

    wellness = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id)
        .order_by(WellnessScore.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if wellness is not None:
        component_lines = ", ".join(
            f"{name}: {c['normalized']:.0f}/100 ({c['detail']})"
            for name, c in (wellness.components or {}).items()
        )
        sections.append(
            f"WELLNESS SCORE: {float(wellness.overall_score):.0f}/100, trend {wellness.trend}. "
            f"Components: {component_lines}. Explanation: {wellness.explanation}"
        )

    assessments = (await db.execute(
        select(RiskAssessment)
        .where(RiskAssessment.student_id == student_id, RiskAssessment.created_at >= week_ago)
        .order_by(RiskAssessment.created_at.asc())
    )).scalars().all()
    if assessments:
        trajectory = ", ".join(
            f"{a.created_at.date().isoformat()}: {a.risk_level}"
            f"{f' ({int(a.risk_score)})' if a.risk_score is not None else ''}"
            for a in assessments[-7:]
        )
        latest_summary = next(
            (a.summary for a in reversed(assessments) if a.summary), None
        )
        block = f"RISK TRAJECTORY (7 days): {trajectory}."
        if latest_summary:
            block += f" Latest analyst summary: {latest_summary}"
        sections.append(block)

    emotions = (await db.execute(
        select(EmotionSnapshot.current_emotion, func.count())
        .where(EmotionSnapshot.student_id == student_id, EmotionSnapshot.created_at >= week_ago)
        .group_by(EmotionSnapshot.current_emotion)
        .order_by(func.count().desc())
    )).all()
    if emotions:
        sections.append(
            "EMOTIONS THIS WEEK: "
            + ", ".join(f"{emotion} x{count}" for emotion, count in emotions)
        )

    stress = (await db.execute(
        select(StressDistribution)
        .where(StressDistribution.student_id == student_id)
        .order_by(StressDistribution.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if stress is not None:
        top = sorted(stress.categories.items(), key=lambda kv: kv[1], reverse=True)[:5]
        sections.append(
            "TOP STRESS AREAS: " + ", ".join(f"{name} {value}%" for name, value in top if value)
        )

    messages_7d = (await db.execute(
        select(func.count()).select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.conversation_id)
        .where(
            Conversation.student_id == student_id,
            Message.sender_type == "user",
            Message.created_at >= week_ago,
        )
    )).scalar() or 0
    checkins_7d = (await db.execute(
        select(func.count()).select_from(WellnessRecord).where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.created_at >= week_ago,
        )
    )).scalar() or 0
    sections.append(
        f"ENGAGEMENT: {messages_7d} companion chat message(s) and "
        f"{checkins_7d} wellness check-in(s) in the last 7 days."
    )

    if not (wellness or assessments or emotions):
        return None
    return "\n\n".join(sections)


async def maybe_refresh_parent_insight(
    db: AsyncSession,
    student_id: uuid.UUID,
    force: bool = False,
) -> ParentInsightHistory | None:
    """Regenerate the parent insight if forced or stale. Flushes, no commit.

    Returns the new row, or None when skipped (debounced or no data).
    """
    cfg = await load_config(db, "parent_insight")

    profile = (await db.execute(
        select(StudentProfile).where(StudentProfile.student_id == student_id)
    )).scalar_one_or_none()
    if profile is None:
        return None

    latest = (await db.execute(
        select(ParentInsightHistory)
        .where(ParentInsightHistory.student_id == student_id)
        .order_by(ParentInsightHistory.generated_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    should_refresh = force or latest is None
    if not should_refresh and cfg.get("regen_on_risk_change", True):
        should_refresh = (latest.risk_level or "green") != (profile.risk_level or "green")
    if not should_refresh:
        age = datetime.now(timezone.utc) - latest.generated_at
        if age > timedelta(hours=float(cfg["ttl_hours"])):
            should_refresh = await _new_activity_since(db, student_id, latest.generated_at)
    if not should_refresh:
        return None

    signal_summary = await _build_signal_summary(db, student_id)
    if signal_summary is None:
        logger.info("No signals for student %s; skipping parent insight", student_id)
        return None

    system_prompt, _version = await load_prompt(
        db, PARENT_INSIGHT_PROMPT_NAME,
        PARENT_INSIGHT_SYSTEM_PROMPT, PARENT_INSIGHT_PROMPT_VERSION,
    )

    text, _metadata = await ai_router.run(
        db,
        feature="parent_insight",
        system_prompt=system_prompt,
        contents=[{"role": "user", "parts": [{"text": signal_summary}]}],
        temperature=0.4,
        max_output_tokens=1024,
        student_id=student_id,
        response_schema=PARENT_INSIGHT_RESPONSE_SCHEMA,
    )
    payload = ParentInsightPayload.model_validate(parse_json_response(text))

    insight = ParentInsightHistory(
        student_id=student_id,
        wellness_score=profile.wellness_score,
        risk_level=profile.risk_level or "green",
        summary=payload.summary,
        recommendations="|".join(payload.recommendations),
        insights_json={
            "today_insights": [i.model_dump() for i in payload.today_insights],
            "improvements": payload.improvements,
            "concerns": payload.concerns,
            "family_communication": payload.family_communication,
            "family_activities": payload.family_activities,
            "protective_factors": payload.protective_factors,
            "risk_factors": payload.risk_factors,
        },
    )
    db.add(insight)
    await db.flush()
    logger.info("Parent insight regenerated for student %s (force=%s)", student_id, force)
    return insight


async def refresh_parent_insight_task(student_id: uuid.UUID) -> None:
    """BackgroundTasks wrapper: own session, re-checks the debounce."""
    from database.session import async_session_factory

    try:
        async with async_session_factory() as db:
            await maybe_refresh_parent_insight(db, student_id, force=False)
            await db.commit()
    except Exception as e:
        logger.warning("Background insight refresh failed (non-fatal): %s", str(e))
