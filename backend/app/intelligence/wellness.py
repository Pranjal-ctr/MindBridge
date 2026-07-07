"""
Deterministic wellness engine -- zero LLM calls.

Computes an explainable 0-100 score from stored signals using configurable
weights (platform_config.wellness_weights). Components without data are
dropped and the remaining weights renormalized; confidence is the share of
total weight that had data. Every run appends a wellness_scores row with the
full component breakdown and a templated explanation, and syncs
StudentProfile.wellness_score for backward compatibility.
"""

from __future__ import annotations

import logging
import statistics
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.config import load_config
from database.models import (
    Conversation,
    CounselorSession,
    Goal,
    JournalEntry,
    Message,
    RiskAssessment,
    StudentProfile,
    WellnessRecord,
    WellnessScore,
)

logger = logging.getLogger(__name__)

# Human-readable labels for explanations
COMPONENT_LABELS = {
    "checkin_engagement": "check-in engagement",
    "mood_level": "reported mood",
    "mood_stability": "mood stability",
    "conversation_sentiment": "conversation sentiment",
    "stress_trend": "stress levels",
    "risk_signal": "risk signals",
    "goal_progress": "goal progress",
    "journal_consistency": "journaling",
    "counselor_engagement": "counselor engagement",
    "improvement_delta": "recent momentum",
}

SENTIMENT_VALUES = {"positive": 100, "neutral": 60, "mixed": 45, "negative": 20}
GOAL_STATUS_VALUES = {"completed": 100, "active": 60, "paused": 40, "abandoned": 10}

TREND_BAND = 3.0  # points either side counts as "stable"


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


async def _component_signals(
    db: AsyncSession, student_id: uuid.UUID
) -> dict[str, tuple[float, str] | None]:
    """Each component's (normalized 0-100, detail) or None when no data exists."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    today = date.today()
    signals: dict[str, tuple[float, str] | None] = {}

    # --- check-in + chat activity, last 7 days ---
    records_7d = (await db.execute(
        select(WellnessRecord)
        .where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.date_recorded >= today - timedelta(days=7),
        )
        .order_by(WellnessRecord.date_recorded.desc())
    )).scalars().all()

    messages_7d = (await db.execute(
        select(func.count()).select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.conversation_id)
        .where(
            Conversation.student_id == student_id,
            Message.sender_type == "user",
            Message.created_at >= week_ago,
        )
    )).scalar() or 0

    checkin_days = len({r.date_recorded for r in records_7d})
    if checkin_days == 0 and messages_7d == 0:
        signals["checkin_engagement"] = None
    else:
        score = _clamp(checkin_days * 12 + min(messages_7d, 20) * 2)
        signals["checkin_engagement"] = (
            score, f"{checkin_days} check-in day(s) and {messages_7d} chat message(s) this week"
        )

    # --- reported mood level (mood/energy/confidence avg, 1-10 -> 0-100) ---
    mood_values = [
        v for r in records_7d
        for v in (r.mood_score, r.energy_score, r.confidence_score)
        if v is not None
    ]
    if mood_values:
        avg = sum(mood_values) / len(mood_values)
        signals["mood_level"] = ((avg - 1) / 9 * 100, f"average reported mood {avg:.1f}/10 this week")
    else:
        signals["mood_level"] = None

    # --- mood stability (stddev of mood over 14 days, inverted) ---
    moods_14d = [
        r.mood_score for r in (await db.execute(
            select(WellnessRecord).where(
                WellnessRecord.student_id == student_id,
                WellnessRecord.date_recorded >= today - timedelta(days=14),
            )
        )).scalars().all()
        if r.mood_score is not None
    ]
    if len(moods_14d) >= 3:
        stddev = statistics.pstdev(moods_14d)
        signals["mood_stability"] = (
            100 - min(stddev / 3, 1) * 100,
            f"mood variation over two weeks: {'steady' if stddev < 1.5 else 'fluctuating'}",
        )
    else:
        signals["mood_stability"] = None

    # --- conversation sentiment (AI-labeled student messages, last 7 days) ---
    sentiments = [
        row[0] for row in (await db.execute(
            select(Message.sentiment)
            .join(Conversation, Message.conversation_id == Conversation.conversation_id)
            .where(
                Conversation.student_id == student_id,
                Message.sender_type == "user",
                Message.sentiment.isnot(None),
                Message.created_at >= week_ago,
            )
        )).all()
        if row[0] in SENTIMENT_VALUES
    ]
    if sentiments:
        avg = sum(SENTIMENT_VALUES[s] for s in sentiments) / len(sentiments)
        negatives = sum(1 for s in sentiments if s == "negative")
        signals["conversation_sentiment"] = (
            avg, f"{len(sentiments)} analyzed message(s), {negatives} negative"
        )
    else:
        signals["conversation_sentiment"] = None

    # --- stress trend (stress+anxiety this week vs prior week, inverted) ---
    def _stress_values(records) -> list[int]:
        return [v for r in records for v in (r.stress_score, r.anxiety_score) if v is not None]

    prior_records = (await db.execute(
        select(WellnessRecord).where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.date_recorded >= today - timedelta(days=14),
            WellnessRecord.date_recorded < today - timedelta(days=7),
        )
    )).scalars().all()

    recent_stress = _stress_values(records_7d)
    prior_stress = _stress_values(prior_records)
    if recent_stress:
        avg_recent = sum(recent_stress) / len(recent_stress)
        score = 100 - (avg_recent - 1) / 9 * 100
        detail = f"average stress/anxiety {avg_recent:.1f}/10 this week"
        if prior_stress:
            avg_prior = sum(prior_stress) / len(prior_stress)
            score += (avg_prior - avg_recent) * 5  # reward week-over-week improvement
            direction = "down" if avg_recent < avg_prior else ("up" if avg_recent > avg_prior else "flat")
            detail += f", {direction} from {avg_prior:.1f} last week"
        signals["stress_trend"] = (_clamp(score), detail)
    else:
        signals["stress_trend"] = None

    # --- risk signal (latest assessment, inverted) ---
    latest_risk = (await db.execute(
        select(RiskAssessment)
        .where(RiskAssessment.student_id == student_id, RiskAssessment.risk_score.isnot(None))
        .order_by(RiskAssessment.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if latest_risk is not None:
        signals["risk_signal"] = (
            _clamp(100 - float(latest_risk.risk_score)),
            f"latest AI risk level: {latest_risk.risk_level}",
        )
    else:
        signals["risk_signal"] = None

    # --- goal progress (recent goals, status-weighted) ---
    goals = (await db.execute(
        select(Goal)
        .where(Goal.student_id == student_id)
        .order_by(Goal.created_at.desc())
        .limit(10)
    )).scalars().all()
    if goals:
        avg = sum(GOAL_STATUS_VALUES.get(g.status, 40) for g in goals) / len(goals)
        completed = sum(1 for g in goals if g.status == "completed")
        signals["goal_progress"] = (avg, f"{completed} of {len(goals)} recent goal(s) completed")
    else:
        signals["goal_progress"] = None

    # --- journal consistency ---
    journal_7d = (await db.execute(
        select(func.count()).select_from(JournalEntry).where(
            JournalEntry.student_id == student_id,
            JournalEntry.created_at >= week_ago,
        )
    )).scalar() or 0
    journal_30d = (await db.execute(
        select(func.count()).select_from(JournalEntry).where(
            JournalEntry.student_id == student_id,
            JournalEntry.created_at >= now - timedelta(days=30),
        )
    )).scalar() or 0
    if journal_30d == 0:
        signals["journal_consistency"] = None  # never journals: not penalized
    else:
        signals["journal_consistency"] = (
            min(journal_7d / 4, 1) * 100, f"{journal_7d} journal entr(ies) this week"
        )

    # --- counselor engagement (last 30 days; absence is not penalized) ---
    sessions_30d = (await db.execute(
        select(CounselorSession).where(
            CounselorSession.student_id == student_id,
            CounselorSession.scheduled_at >= now - timedelta(days=30),
        )
    )).scalars().all()
    if sessions_30d:
        completed = any(s.status == "completed" for s in sessions_30d)
        upcoming = any(s.status == "scheduled" for s in sessions_30d)
        score = 100 if completed else (70 if upcoming else 30)
        signals["counselor_engagement"] = (
            float(score),
            "completed a counselor session recently" if completed
            else ("counselor session scheduled" if upcoming else "counselor session missed"),
        )
    else:
        signals["counselor_engagement"] = None

    return signals


async def compute_wellness_score(
    db: AsyncSession,
    student_id: uuid.UUID,
    trigger_source: str,
) -> WellnessScore | None:
    """Compute and persist a wellness score (flushes, no commit).

    Returns None when no component has any data (nothing meaningful to store).
    """
    weights: dict[str, float] = await load_config(db, "wellness_weights")
    signals = await _component_signals(db, student_id)

    prior_scores = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id)
        .order_by(WellnessScore.created_at.desc())
        .limit(10)
    )).scalars().all()

    # Provisional score over data-bearing components (excluding momentum)
    def _weighted(components: dict[str, tuple[float, str]]) -> float | None:
        total_weight = sum(weights.get(name, 0) for name in components)
        if total_weight <= 0:
            return None
        return sum(norm * weights.get(name, 0) for name, (norm, _) in components.items()) / total_weight

    present = {name: sig for name, sig in signals.items() if sig is not None}
    provisional = _weighted(present)
    if provisional is None:
        logger.info("No wellness signals for student %s; skipping score", student_id)
        return None

    # --- recent momentum: provisional vs average of last 3 stored scores ---
    if prior_scores:
        prev_avg = sum(float(s.overall_score) for s in prior_scores[:3]) / min(len(prior_scores), 3)
        delta = provisional - prev_avg
        direction = "improving" if delta > 1 else ("declining" if delta < -1 else "holding steady")
        present["improvement_delta"] = (
            _clamp(50 + delta * 2), f"{direction} vs. recent average ({prev_avg:.0f})"
        )

    overall = _weighted(present)
    confidence = min(sum(weights.get(name, 0) for name in present), 1.0)

    # --- trend vs the score ~7 days ago ---
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    baseline = next((s for s in reversed(prior_scores) if s.created_at <= week_ago), None)
    if baseline is None and prior_scores:
        baseline = prior_scores[-1]  # oldest available
    if baseline is None:
        trend = "stable"
    else:
        diff = overall - float(baseline.overall_score)
        trend = "improving" if diff > TREND_BAND else ("declining" if diff < -TREND_BAND else "stable")

    # --- component breakdown ---
    effective_total = sum(weights.get(name, 0) for name in present)
    components = {
        name: {
            "normalized": round(norm, 1),
            "weight": weights.get(name, 0),
            "contribution": round(norm * weights.get(name, 0) / effective_total, 1),
            "detail": detail,
        }
        for name, (norm, detail) in present.items()
    }

    # --- templated explanation: top positives, top drags, biggest mover ---
    ranked = sorted(present.items(), key=lambda item: item[1][0], reverse=True)
    positives = [COMPONENT_LABELS[n] for n, (v, _) in ranked[:2] if v >= 55]
    drags = [COMPONENT_LABELS[n] for n, (v, _) in ranked[-2:] if v < 50]
    parts = [f"Wellness is {overall:.0f} and {trend}."]
    if positives:
        parts.append(f"Strongest areas: {' and '.join(positives)}.")
    if drags:
        parts.append(f"Main pressure points: {' and '.join(drags)}.")
    if prior_scores:
        prev_components = prior_scores[0].components or {}
        movers = [
            (name, components[name]["normalized"] - float(prev_components[name].get("normalized", 0)))
            for name in components if name in prev_components
        ]
        if movers:
            mover, change = max(movers, key=lambda m: abs(m[1]))
            if abs(change) >= 5:
                parts.append(
                    f"Biggest change since last update: {COMPONENT_LABELS[mover]} "
                    f"{'improved' if change > 0 else 'dropped'}."
                )
    explanation = " ".join(parts)

    score = WellnessScore(
        student_id=student_id,
        overall_score=round(overall, 2),
        trend=trend,
        confidence=round(confidence, 2),
        components=components,
        explanation=explanation,
        trigger_source=trigger_source,
    )
    db.add(score)

    profile = (await db.execute(
        select(StudentProfile).where(StudentProfile.student_id == student_id)
    )).scalar_one_or_none()
    if profile is not None:
        profile.wellness_score = score.overall_score

    await db.flush()
    logger.info(
        "Wellness score for student %s: %.0f (%s, confidence %.2f, trigger=%s)",
        student_id, overall, trend, confidence, trigger_source,
    )
    return score
