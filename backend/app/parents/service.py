"""
Kio Parents Service
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.parents.schemas import (
    ChildInsightResponse,
    ChildSummary,
    MoodTrendPoint,
    RecommendationResponse,
    RiskTrendPoint,
    StressFactor,
    TodayInsightCard,
    WeeklyMoodSummary,
    WellbeingDimension,
    WellnessBreakdown,
    WellnessTrendPoint,
)
from database.models import (
    Conversation,
    EmotionSnapshot,
    Goal,
    Message,
    ParentInsightHistory,
    ParentProfile,
    RiskAssessment,
    StressDistribution,
    StudentParentLink,
    StudentProfile,
    User,
    WellnessRecord,
    WellnessScore,
)


async def get_linked_children(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ChildSummary]:
    """Get all children linked to a parent."""
    # Get parent profile
    result = await db.execute(
        select(ParentProfile).where(ParentProfile.user_id == user_id)
    )
    parent = result.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found")

    # Get linked students
    links_result = await db.execute(
        select(StudentParentLink, StudentProfile, User)
        .join(StudentProfile, StudentParentLink.student_id == StudentProfile.student_id)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(StudentParentLink.parent_id == parent.parent_id)
    )
    rows = links_result.all()

    children = []
    for link, student, user in rows:
        children.append(
            ChildSummary(
                student_id=student.student_id,
                first_name=user.first_name,
                last_name=user.last_name,
                age=student.age,
                wellness_score=float(student.wellness_score) if student.wellness_score else None,
                risk_level=student.risk_level or "green",
                relationship=link.relationship_,
            )
        )

    return children


async def _wellness_trend(db: AsyncSession, student_id: uuid.UUID) -> list[WellnessTrendPoint]:
    """Daily latest computed wellness score, last 7 days.

    Falls back to the legacy check-in formula when no computed scores exist yet.
    """
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    scores = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id, WellnessScore.created_at >= week_ago)
        .order_by(WellnessScore.created_at.asc())
    )).scalars().all()

    if scores:
        daily_latest: dict[str, WellnessScore] = {}
        for s in scores:
            daily_latest[s.created_at.date().isoformat()] = s
        return [
            WellnessTrendPoint(
                date=datetime.fromisoformat(day).strftime("%a"),
                score=float(daily_latest[day].overall_score),
            )
            for day in sorted(daily_latest)
        ]

    # Legacy fallback: derive from raw check-ins
    records = list((await db.execute(
        select(WellnessRecord)
        .where(WellnessRecord.student_id == student_id)
        .order_by(WellnessRecord.date_recorded.desc())
        .limit(7)
    )).scalars().all())
    records.reverse()
    return [
        WellnessTrendPoint(
            date=r.date_recorded.strftime("%a"),
            score=float(
                (r.mood_score + r.energy_score + r.confidence_score) / 3 * 10
                if r.mood_score and r.energy_score and r.confidence_score
                else 0
            ),
        )
        for r in records
    ]


_MOOD_FRIENDLY = {
    "amazing": "Very Happy", "good": "Happy", "okay": "Neutral",
    "low": "Sad", "very_difficult": "Very Low",
}

# Check-in reasons -> stress factor names (positive reasons are skipped)
_REASON_TO_FACTOR = {
    "academics": "Academic", "family": "Family", "friends": "Friends",
    "relationship": "Relationships", "health": "Health", "career": "Career",
    "financial": "Financial", "social_media": "Screen Time",
}

# AI risk categories -> stress factor names
_RISK_TO_FACTOR = {
    "academic_pressure": "Academic", "family_conflict": "Family",
    "loneliness": "Loneliness", "bullying": "Bullying", "sleep_issues": "Sleep",
}


def _weekly_mood_summary(records: list[WellnessRecord]) -> WeeklyMoodSummary | None:
    """Aggregate the last 7 days of mood check-ins (one reading per day, latest wins)."""
    daily: dict = {}
    for r in sorted(records, key=lambda r: (r.date_recorded, r.created_at)):
        if r.mood_score is not None:
            daily[r.date_recorded] = r
    if not daily:
        return None

    days = sorted(daily)
    scores = [daily[d].mood_score for d in days]
    labels = [daily[d].mood_label for d in days if daily[d].mood_label]

    dominant = Counter(labels).most_common(1)[0][0] if labels else None
    low_days = sum(1 for s in scores if s <= 3)

    trend = "stable"
    if len(scores) >= 4:
        half = len(scores) // 2
        delta = sum(scores[half:]) / len(scores[half:]) - sum(scores[:half]) / half
        trend = "improving" if delta >= 0.75 else ("declining" if delta <= -0.75 else "stable")

    if dominant:
        headline = f"Mostly {_MOOD_FRIENDLY[dominant]}"
    else:
        avg = sum(scores) / len(scores)
        headline = "A good week overall" if avg >= 6.5 else (
            "A mixed week" if avg >= 4 else "A tough week"
        )

    return WeeklyMoodSummary(
        headline=headline,
        dominant_mood=dominant,
        low_days=low_days,
        trend=trend,
        days_recorded=len(days),
    )


def _wellbeing_dimensions(
    components: dict,
    stress_categories: dict,
    risk_categories: dict,
) -> list[WellbeingDimension]:
    """Preferred radar dimensions, each derived from a real stored signal.

    Only dimensions whose source signal exists are included; values are 0-100
    where higher is better (stress/risk sources are inverted).
    """
    def clamp(v: float) -> int:
        return int(max(0, min(100, round(v))))

    dims: list[WellbeingDimension] = []

    def from_stress(name: str, category: str):
        if stress_categories and category in stress_categories:
            dims.append(WellbeingDimension(
                dimension=name, value=clamp(100 - float(stress_categories[category]))
            ))

    def from_component(name: str, component: str):
        if component in components:
            dims.append(WellbeingDimension(
                dimension=name, value=clamp(float(components[component]["normalized"]))
            ))

    from_stress("Academic", "Academic")
    from_component("Emotional", "mood_level")
    from_stress("Social", "Friends")
    from_stress("Family", "Family")
    if risk_categories and "sleep_issues" in risk_categories:
        dims.append(WellbeingDimension(
            dimension="Sleep", value=clamp(100 - float(risk_categories["sleep_issues"]))
        ))
    from_stress("Confidence", "Self-Confidence")
    from_component("Motivation", "goal_progress")
    from_component("Resilience", "mood_stability")
    from_component("Engagement", "checkin_engagement")
    from_component("Support", "counselor_engagement")

    return dims


def _blend_stress_factors(
    stress_categories: dict,
    checkin_records: list[WellnessRecord],
    risk_categories: dict,
) -> list[StressFactor]:
    """Realistic stress ranking from three real sources:
    the AI conversation analysis, the student's own check-in reasons, and the
    latest AI risk categories. Each factor keeps the strongest signal (max)."""
    factors: dict[str, float] = {
        name: float(value)
        for name, value in (stress_categories or {}).items()
        if value and value > 0
    }

    # Check-in reasons: how often a topic is "the main thing on my mind"
    reason_counts = Counter(
        r.mood_reason for r in checkin_records
        if r.mood_reason in _REASON_TO_FACTOR
    )
    for reason, count in reason_counts.items():
        name = _REASON_TO_FACTOR[reason]
        value = min(count * 15, 70)
        factors[name] = max(factors.get(name, 0), value)

    # AI risk categories that map to stress topics
    for category, name in _RISK_TO_FACTOR.items():
        value = float((risk_categories or {}).get(category, 0) or 0)
        if value > 0:
            factors[name] = max(factors.get(name, 0), value)

    ranked = sorted(factors.items(), key=lambda kv: kv[1], reverse=True)[:8]
    return [StressFactor(name=name, value=int(value)) for name, value in ranked]


async def get_child_insights(
    db: AsyncSession, user_id: uuid.UUID, student_id: uuid.UUID
) -> tuple[ChildInsightResponse, bool]:
    """Detailed insights for a parent's child (aggregates only, never messages).

    Returns (response, insight_is_stale) -- the router schedules a background
    narrative regeneration when stale.
    """
    from app.intelligence.config import load_config

    # Verify parent-child link
    await _verify_parent_child_link(db, user_id, student_id)

    # Get student info
    result = await db.execute(
        select(StudentProfile, User)
        .join(User, StudentProfile.user_id == User.user_id)
        .where(StudentProfile.student_id == student_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    student, user = row
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # Latest AI-generated narrative
    latest_insight = (await db.execute(
        select(ParentInsightHistory)
        .where(ParentInsightHistory.student_id == student_id)
        .order_by(ParentInsightHistory.generated_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    # Latest computed wellness score + breakdown
    latest_score = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id)
        .order_by(WellnessScore.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    breakdown = None
    if latest_score is not None:
        breakdown = WellnessBreakdown(
            trend=latest_score.trend,
            confidence=float(latest_score.confidence) if latest_score.confidence is not None else None,
            components=latest_score.components or {},
            explanation=latest_score.explanation,
            calculated_at=latest_score.created_at,
        )

    # Risk trend: worst level per day, last 7 days (levels only)
    assessments = (await db.execute(
        select(RiskAssessment)
        .where(RiskAssessment.student_id == student_id, RiskAssessment.created_at >= week_ago)
        .order_by(RiskAssessment.created_at.asc())
    )).scalars().all()
    severity = {"green": 0, "yellow": 1, "red": 2, "critical": 3}
    daily_risk: dict[str, RiskAssessment] = {}
    for a in assessments:
        day = a.created_at.date().isoformat()
        if day not in daily_risk or severity.get(a.risk_level, 0) > severity.get(
            daily_risk[day].risk_level, 0
        ):
            daily_risk[day] = a
    risk_trend = [
        RiskTrendPoint(
            date=day,
            level=daily_risk[day].risk_level,
            score=float(daily_risk[day].risk_score) if daily_risk[day].risk_score is not None else None,
        )
        for day in sorted(daily_risk)
    ]

    # Mood trend: dominant emotion per day, last 7 days
    snapshots = (await db.execute(
        select(EmotionSnapshot)
        .where(EmotionSnapshot.student_id == student_id, EmotionSnapshot.created_at >= week_ago)
        .order_by(EmotionSnapshot.created_at.asc())
    )).scalars().all()
    daily_emotions: dict[str, Counter] = {}
    for s in snapshots:
        daily_emotions.setdefault(s.created_at.date().isoformat(), Counter())[s.current_emotion] += 1
    mood_trend = [
        MoodTrendPoint(date=day, emotion=counter.most_common(1)[0][0])
        for day, counter in sorted(daily_emotions.items())
    ]
    emotional_state = (
        Counter(s.current_emotion for s in snapshots).most_common(1)[0][0]
        if snapshots else "Stable"
    )

    # Stress factors: AI distribution blended with check-in reasons + risk categories
    stress_row = (await db.execute(
        select(StressDistribution)
        .where(StressDistribution.student_id == student_id)
        .order_by(StressDistribution.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    month_ago = now - timedelta(days=30)
    checkin_records_30d = list((await db.execute(
        select(WellnessRecord).where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.created_at >= month_ago,
        )
    )).scalars().all())

    latest_assessment = assessments[-1] if assessments else (await db.execute(
        select(RiskAssessment)
        .where(RiskAssessment.student_id == student_id)
        .order_by(RiskAssessment.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    risk_categories = (latest_assessment.categories or {}) if latest_assessment else {}

    stress_factors = _blend_stress_factors(
        (stress_row.categories if stress_row else {}) or {},
        checkin_records_30d,
        risk_categories,
    )

    # Weekly mood summary (aggregate -- daily mood icons stay with the student)
    week_records = [r for r in checkin_records_30d if r.created_at >= week_ago]
    weekly_mood = _weekly_mood_summary(week_records)

    # Wellbeing dimensions for the radar, from real signals only
    wellbeing_dims = _wellbeing_dimensions(
        (latest_score.components or {}) if latest_score else {},
        (stress_row.categories if stress_row else {}) or {},
        risk_categories,
    )

    # Weekly progress counters
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
        select(func.count(func.distinct(WellnessRecord.date_recorded)))
        .select_from(WellnessRecord)
        .where(WellnessRecord.student_id == student_id, WellnessRecord.created_at >= week_ago)
    )).scalar() or 0
    goals_completed_7d = (await db.execute(
        select(func.count()).select_from(Goal).where(
            Goal.student_id == student_id,
            Goal.status == "completed",
            Goal.created_at >= week_ago,
        )
    )).scalar() or 0

    # Structured narrative payload
    insights_json = (latest_insight.insights_json or {}) if latest_insight else {}
    today_insights = [
        TodayInsightCard(**card) for card in insights_json.get("today_insights", [])
        if isinstance(card, dict) and card.get("title") and card.get("body")
    ]

    # Staleness for background regeneration
    stale = latest_insight is None
    if not stale:
        cfg = await load_config(db, "parent_insight")
        stale = (now - latest_insight.generated_at) > timedelta(hours=float(cfg["ttl_hours"]))

    response = ChildInsightResponse(
        student_id=student.student_id,
        student_name=f"{user.first_name} {user.last_name}",
        wellness_score=(
            float(latest_score.overall_score) if latest_score is not None
            else (float(student.wellness_score) if student.wellness_score else None)
        ),
        risk_level=student.risk_level or "green",
        emotional_state=emotional_state,
        summary=latest_insight.summary if latest_insight else None,
        wellness_trend=await _wellness_trend(db, student_id),
        stress_factors=stress_factors,
        recommendations=(
            latest_insight.recommendations.split("|")
            if latest_insight and latest_insight.recommendations else []
        ),
        last_updated=latest_insight.generated_at if latest_insight else None,
        wellness_breakdown=breakdown,
        risk_trend=risk_trend,
        mood_trend=mood_trend,
        today_insights=today_insights,
        improvements=insights_json.get("improvements", []),
        concerns=insights_json.get("concerns", []),
        weekly_progress={
            "messages": messages_7d,
            "checkin_days": checkins_7d,
            "goals_completed": goals_completed_7d,
        },
        family_communication=insights_json.get("family_communication", []),
        family_activities=insights_json.get("family_activities", []),
        weekly_mood_summary=weekly_mood,
        wellbeing_dimensions=wellbeing_dims,
        protective_factors=insights_json.get("protective_factors", []),
        risk_factors=insights_json.get("risk_factors", []),
    )
    return response, stale


async def get_wellness_trend_range(
    db: AsyncSession, user_id: uuid.UUID, student_id: uuid.UUID, days: int
) -> list[WellnessTrendPoint]:
    """Daily latest computed wellness score over the requested window (ISO dates)."""
    await _verify_parent_child_link(db, user_id, student_id)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    scores = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id, WellnessScore.created_at >= cutoff)
        .order_by(WellnessScore.created_at.asc())
    )).scalars().all()

    daily_latest: dict[str, WellnessScore] = {}
    for s in scores:
        daily_latest[s.created_at.date().isoformat()] = s
    return [
        WellnessTrendPoint(date=day, score=float(daily_latest[day].overall_score))
        for day in sorted(daily_latest)
    ]


async def _verify_parent_child_link(
    db: AsyncSession, user_id: uuid.UUID, student_id: uuid.UUID
) -> None:
    """Verify that the parent has a link to the child."""
    result = await db.execute(
        select(ParentProfile).where(ParentProfile.user_id == user_id)
    )
    parent = result.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a parent")

    link_result = await db.execute(
        select(StudentParentLink).where(
            StudentParentLink.parent_id == parent.parent_id,
            StudentParentLink.student_id == student_id,
        )
    )
    if not link_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this student's data",
        )
