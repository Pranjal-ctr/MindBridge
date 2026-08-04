"""
Combined post-message analysis: ONE LLM call (feature `risk_detection`)
returning risk + emotion + stress + sentiment as structured JSON, persisted to
risk_assessments, emotion_history, stress_distributions, and messages.sentiment.

The risk LEVEL is always derived server-side from configured bands -- the
model only produces scores.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import router as ai_router
from app.intelligence.config import RISK_LEVEL_RANK, derive_risk_level, load_config
from app.intelligence.parsing import parse_json_response
from app.intelligence.prompts import (
    ANALYSIS_PROMPT_NAME,
    ANALYSIS_PROMPT_VERSION,
    ANALYSIS_SYSTEM_PROMPT,
    load_prompt,
)
from app.intelligence.schemas import (
    ANALYSIS_RESPONSE_SCHEMA,
    STRESS_CATEGORIES,
    MessageAnalysis,
)
from database.models import (
    EmotionSnapshot,
    Message,
    RiskAssessment,
    StressDistribution,
    StudentProfile,
    WellnessRecord,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisOutcome:
    """What the pipeline's downstream steps (crisis, wellness, insights) need."""
    analysis: MessageAnalysis
    assessment: RiskAssessment
    previous_profile_level: str
    new_profile_level: str


def _apply_safety_floor(analysis: MessageAnalysis, floors: dict) -> bool:
    """Force overall risk to at least `enforced_overall` when a credible acute
    category signal is present.

    The prompt already tells the model "self-harm => risk >= 70", but a prompt
    is guidance, not a guarantee. This is the deterministic backstop: if the
    model reports a high self-harm/suicidal/abuse category yet a low `overall`,
    we raise `overall` so an under-scored aggregate can never mask acute risk.
    Protective factors never lower it -- risk is a floor, not an average.

    Returns True when the floor changed the score (for auditability).
    """
    cats = analysis.risk.categories or {}
    enforced = float(floors["enforced_overall"])
    tripped = (
        cats.get("self_harm", 0) >= float(floors["self_harm"])
        or cats.get("suicidal_ideation", 0) >= float(floors["suicidal_ideation"])
        or cats.get("abuse", 0) >= float(floors["abuse"])
    )
    if tripped and analysis.risk.overall < enforced:
        analysis.risk.overall = enforced
        return True
    return False


async def _build_analysis_input(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    student_id: uuid.UUID,
    context_messages: int,
) -> str:
    """Serialize the recent transcript + continuity signals into one analyst input."""
    from app.ai.service import _load_conversation_history

    history = await _load_conversation_history(db, conversation_id, context_messages)
    transcript_lines = [
        f"{'Comrade' if turn['role'] == 'model' else 'Student'}: {turn['text']}"
        for turn in history
    ]

    sections = ["CONVERSATION TRANSCRIPT (oldest first):", *transcript_lines]

    # Continuity block: prior scores + latest summary so the model assesses
    # trajectory, not a single message.
    prior_result = await db.execute(
        select(RiskAssessment)
        .where(RiskAssessment.student_id == student_id)
        .order_by(RiskAssessment.created_at.desc())
        .limit(3)
    )
    priors = list(prior_result.scalars().all())
    if priors:
        scores = " -> ".join(
            str(int(p.risk_score)) for p in reversed(priors) if p.risk_score is not None
        )
        latest_summary = next((p.summary for p in priors if p.summary), None)
        block = f"\nPRIOR ASSESSMENT (baseline): recent overall scores: {scores or 'n/a'}."
        if latest_summary:
            block += f" Latest summary: {latest_summary}"
        sections.append(block)

    checkin_result = await db.execute(
        select(WellnessRecord).where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.date_recorded == date.today(),
        ).limit(1)
    )
    checkin = checkin_result.scalar_one_or_none()
    if checkin:
        sections.append(
            f"\nTODAY'S SELF-REPORTED CHECK-IN (1-10): mood={checkin.mood_score}, "
            f"stress={checkin.stress_score}, anxiety={checkin.anxiety_score}, "
            f"energy={checkin.energy_score}, confidence={checkin.confidence_score}"
        )

    return "\n".join(sections)


async def _sync_profile_risk_level(
    db: AsyncSession,
    student_id: uuid.UUID,
    derived_level: str,
    deescalate_after: int,
) -> tuple[str, str]:
    """Escalate immediately; de-escalate only after N consecutive lower assessments.

    Returns (previous_level, new_level). Caller must have flushed the new
    assessment so it is included in the consecutive-window query.
    """
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.student_id == student_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return "green", "green"

    previous = profile.risk_level or "green"
    current_rank = RISK_LEVEL_RANK.get(previous, 0)
    derived_rank = RISK_LEVEL_RANK.get(derived_level, 0)

    if derived_rank >= current_rank:
        profile.risk_level = derived_level
        return previous, derived_level

    # Lower reading: only de-escalate if the last N assessments are ALL below
    # the current profile level (avoids flapping on one calm message).
    recent_result = await db.execute(
        select(RiskAssessment.risk_level)
        .where(RiskAssessment.student_id == student_id)
        .order_by(RiskAssessment.created_at.desc())
        .limit(deescalate_after)
    )
    recent_levels = [row[0] for row in recent_result.all()]
    if len(recent_levels) < deescalate_after or any(
        RISK_LEVEL_RANK.get(level, 0) >= current_rank for level in recent_levels
    ):
        return previous, previous

    new_level = max(recent_levels, key=lambda level: RISK_LEVEL_RANK.get(level, 0))
    profile.risk_level = new_level
    return previous, new_level


async def _store_stress_distribution(
    db: AsyncSession,
    student_id: uuid.UUID,
    conversation_id: uuid.UUID,
    new_values: dict[str, float],
    smoothing: float,
) -> None:
    """Append a smoothed distribution row: new = a*analysis + (1-a)*previous."""
    prev_result = await db.execute(
        select(StressDistribution)
        .where(StressDistribution.student_id == student_id)
        .order_by(StressDistribution.created_at.desc())
        .limit(1)
    )
    previous = prev_result.scalar_one_or_none()
    prev_values = previous.categories if previous else {}

    smoothed = {}
    for category in STRESS_CATEGORIES:
        new_v = float(new_values.get(category, 0))
        prev_v = float(prev_values.get(category, 0)) if isinstance(prev_values, dict) else 0.0
        smoothed[category] = round(smoothing * new_v + (1 - smoothing) * prev_v)

    db.add(StressDistribution(
        student_id=student_id,
        conversation_id=conversation_id,
        categories=smoothed,
    ))


async def run_message_analysis(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    student_id: uuid.UUID,
    student_message_id: uuid.UUID | None,
) -> AnalysisOutcome:
    """Run the combined analysis and persist all four sinks (flushes, no commit).

    Raises on provider/parse failure -- the pipeline treats that as a skipped,
    non-fatal step (the keyword tripwire already ran on the sync path).
    """
    analysis_cfg = await load_config(db, "analysis")
    bands = await load_config(db, "risk_level_bands")
    crisis_cfg = await load_config(db, "crisis")
    floors = await load_config(db, "safety_floors")

    system_prompt, prompt_version = await load_prompt(
        db, ANALYSIS_PROMPT_NAME, ANALYSIS_SYSTEM_PROMPT, ANALYSIS_PROMPT_VERSION
    )
    analysis_input = await _build_analysis_input(
        db, conversation_id, student_id, int(analysis_cfg["context_messages"])
    )

    text, _metadata = await ai_router.run(
        db,
        feature="risk_detection",
        system_prompt=system_prompt,
        contents=[{"role": "user", "parts": [{"text": analysis_input}]}],
        temperature=0.1,
        max_output_tokens=1024,
        conversation_id=conversation_id,
        student_id=student_id,
        response_schema=ANALYSIS_RESPONSE_SCHEMA,
    )

    analysis = MessageAnalysis.model_validate(parse_json_response(text))

    # Deterministic safety backstop BEFORE deriving the level, so a credible
    # self-harm/abuse signal can never be masked by a low aggregate score.
    floor_applied = _apply_safety_floor(analysis, floors)
    derived_level = derive_risk_level(analysis.risk.overall, bands)

    trigger_reason = f"AI conversation analysis (prompt {prompt_version})"
    if floor_applied:
        trigger_reason += " + safety floor applied"

    # 1. Risk assessment (append-only history)
    assessment = RiskAssessment(
        student_id=student_id,
        conversation_id=conversation_id,
        message_id=student_message_id,
        risk_score=round(analysis.risk.overall, 2),
        risk_level=derived_level,
        categories=analysis.risk.categories,
        confidence=round(analysis.risk.confidence, 2),
        summary=analysis.risk.summary or None,
        trigger_reason=trigger_reason,
        generated_by="ai_pipeline",
    )
    db.add(assessment)
    await db.flush()

    previous_level, new_level = await _sync_profile_risk_level(
        db, student_id, derived_level, int(crisis_cfg["deescalate_after"])
    )

    # 2. Emotion snapshot
    db.add(EmotionSnapshot(
        student_id=student_id,
        conversation_id=conversation_id,
        current_emotion=analysis.emotion.current,
        intensity=round(analysis.emotion.intensity),
        confidence=round(analysis.emotion.confidence, 2),
        secondary_emotions=analysis.emotion.secondary,
    ))

    # 3. Stress distribution (smoothed)
    await _store_stress_distribution(
        db, student_id, conversation_id,
        analysis.stress, float(analysis_cfg["stress_smoothing"]),
    )

    # 4. Sentiment onto the analyzed student message
    if student_message_id is not None:
        await db.execute(
            update(Message)
            .where(Message.message_id == student_message_id)
            .values(sentiment=analysis.sentiment)
        )

    await db.flush()
    logger.info(
        "Analysis stored for student %s: risk=%s (%s), emotion=%s",
        student_id, assessment.risk_score, derived_level, analysis.emotion.current,
    )
    return AnalysisOutcome(
        analysis=analysis,
        assessment=assessment,
        previous_profile_level=previous_level,
        new_profile_level=new_level,
    )
