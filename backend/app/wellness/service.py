"""
MindBridge Wellness Service
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.wellness.schemas import (
    EmotionSummaryResponse,
    EmotionTimelinePoint,
    EmotionTrendPoint,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    JournalEntryCreate,
    JournalEntryResponse,
    MoodCheckinRequest,
    MoodCheckinResponse,
    WellnessRecordCreate,
    WellnessRecordResponse,
    WellnessScoreHistoryResponse,
    WellnessScorePoint,
    WellnessScoreResponse,
)
from database.models import (
    EmotionSnapshot,
    Goal,
    JournalEntry,
    StudentTimeline,
    WellnessRecord,
    WellnessScore,
)

# One-tap mood buttons -> 1-10 mood_score
MOOD_VALUES = {"happy": 8, "okay": 5, "down": 2}


# -------------------------------------------------------------------
# Wellness Records
# -------------------------------------------------------------------

async def create_wellness_record(
    db: AsyncSession, student_id: uuid.UUID, payload: WellnessRecordCreate
) -> WellnessRecordResponse:
    """Log a daily wellness check-in."""
    record = WellnessRecord(
        student_id=student_id,
        mood_score=payload.mood_score,
        stress_score=payload.stress_score,
        confidence_score=payload.confidence_score,
        anxiety_score=payload.anxiety_score,
        energy_score=payload.energy_score,
        date_recorded=payload.date_recorded or date.today(),
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    await _recalculate_wellness(db, student_id, "checkin")
    return WellnessRecordResponse.model_validate(record)


async def list_wellness_records(
    db: AsyncSession,
    student_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[list[WellnessRecordResponse], int]:
    """Get wellness history with optional date range."""
    query = select(WellnessRecord).where(WellnessRecord.student_id == student_id)
    count_query = select(func.count()).select_from(WellnessRecord).where(
        WellnessRecord.student_id == student_id
    )

    if start_date:
        query = query.where(WellnessRecord.date_recorded >= start_date)
        count_query = count_query.where(WellnessRecord.date_recorded >= start_date)
    if end_date:
        query = query.where(WellnessRecord.date_recorded <= end_date)
        count_query = count_query.where(WellnessRecord.date_recorded <= end_date)

    query = query.order_by(WellnessRecord.date_recorded.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query)
    records = result.scalars().all()

    return [WellnessRecordResponse.model_validate(r) for r in records], total


# -------------------------------------------------------------------
# Goals
# -------------------------------------------------------------------

async def create_goal(
    db: AsyncSession, student_id: uuid.UUID, payload: GoalCreate
) -> GoalResponse:
    """Create a new student goal."""
    goal = Goal(
        student_id=student_id,
        goal_title=payload.goal_title,
        goal_description=payload.goal_description,
        target_date=payload.target_date,
    )
    db.add(goal)
    await db.flush()
    await db.refresh(goal)
    return GoalResponse.model_validate(goal)


async def list_goals(
    db: AsyncSession, student_id: uuid.UUID, status_filter: str | None = None
) -> tuple[list[GoalResponse], int]:
    """List goals for a student."""
    query = select(Goal).where(Goal.student_id == student_id)
    count_query = select(func.count()).select_from(Goal).where(Goal.student_id == student_id)

    if status_filter:
        query = query.where(Goal.status == status_filter)
        count_query = count_query.where(Goal.status == status_filter)

    query = query.order_by(Goal.created_at.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query)
    goals = result.scalars().all()

    return [GoalResponse.model_validate(g) for g in goals], total


async def update_goal(
    db: AsyncSession, goal_id: uuid.UUID, student_id: uuid.UUID, payload: GoalUpdate
) -> GoalResponse:
    """Update a student goal."""
    result = await db.execute(
        select(Goal).where(Goal.goal_id == goal_id, Goal.student_id == student_id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(goal, field, value)

    await db.flush()
    await db.refresh(goal)

    if "status" in update_data:
        if update_data["status"] == "completed":
            db.add(StudentTimeline(
                student_id=student_id,
                event_type="goal_completed",
                reference_id=goal.goal_id,
                event_description=f"Completed goal: {goal.goal_title}",
            ))
        await _recalculate_wellness(db, student_id, "goal")

    return GoalResponse.model_validate(goal)


# -------------------------------------------------------------------
# Journal
# -------------------------------------------------------------------

async def create_journal_entry(
    db: AsyncSession, student_id: uuid.UUID, payload: JournalEntryCreate
) -> JournalEntryResponse:
    """Create a new journal entry."""
    entry = JournalEntry(
        student_id=student_id,
        title=payload.title,
        content=payload.content,
        mood_score=payload.mood_score,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return JournalEntryResponse.model_validate(entry)


async def list_journal_entries(
    db: AsyncSession, student_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[JournalEntryResponse], int]:
    """List journal entries for a student."""
    count_result = await db.execute(
        select(func.count()).select_from(JournalEntry).where(JournalEntry.student_id == student_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(JournalEntry)
        .where(JournalEntry.student_id == student_id)
        .order_by(JournalEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    entries = result.scalars().all()

    return [JournalEntryResponse.model_validate(e) for e in entries], total


# -------------------------------------------------------------------
# Wellness Score (intelligence layer)
# -------------------------------------------------------------------

async def _recalculate_wellness(db: AsyncSession, student_id: uuid.UUID, trigger: str) -> None:
    """Deterministic recalc (pure SQL, no LLM) -- cheap enough to run inline."""
    import logging

    from app.intelligence.wellness import compute_wellness_score

    try:
        await compute_wellness_score(db, student_id, trigger_source=trigger)
    except Exception as e:
        logging.getLogger(__name__).warning("Wellness recalc failed (non-fatal): %s", str(e))


async def _checkin_streak_days(db: AsyncSession, student_id: uuid.UUID) -> int:
    """Consecutive days with a wellness record, ending today or yesterday."""
    result = await db.execute(
        select(WellnessRecord.date_recorded)
        .where(WellnessRecord.student_id == student_id)
        .distinct()
        .order_by(WellnessRecord.date_recorded.desc())
        .limit(90)
    )
    days = [row[0] for row in result.all()]
    if not days:
        return 0

    today = date.today()
    if days[0] not in (today, today - timedelta(days=1)):
        return 0

    streak = 1
    for previous, current in zip(days, days[1:]):
        if (previous - current).days == 1:
            streak += 1
        else:
            break
    return streak


def _score_response(score: WellnessScore | None, streak: int) -> WellnessScoreResponse:
    if score is None:
        return WellnessScoreResponse(has_data=False, streak_days=streak)
    return WellnessScoreResponse(
        has_data=True,
        overall=float(score.overall_score),
        trend=score.trend,
        confidence=float(score.confidence) if score.confidence is not None else None,
        components=score.components,
        explanation=score.explanation,
        streak_days=streak,
        calculated_at=score.created_at,
    )


async def get_wellness_score(db: AsyncSession, student_id: uuid.UUID) -> WellnessScoreResponse:
    """Latest computed wellness score + check-in streak."""
    score = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id)
        .order_by(WellnessScore.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    streak = await _checkin_streak_days(db, student_id)
    return _score_response(score, streak)


async def get_wellness_score_history(
    db: AsyncSession, student_id: uuid.UUID, days: int = 30
) -> WellnessScoreHistoryResponse:
    """Score timeline for charts (one point per stored score, oldest first)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    scores = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id, WellnessScore.created_at >= cutoff)
        .order_by(WellnessScore.created_at.asc())
    )).scalars().all()

    return WellnessScoreHistoryResponse(points=[
        WellnessScorePoint(date=s.created_at, score=float(s.overall_score), trend=s.trend)
        for s in scores
    ])


async def log_mood_checkin(
    db: AsyncSession, student_id: uuid.UUID, payload: MoodCheckinRequest
) -> MoodCheckinResponse:
    """One-tap mood check-in: upsert today's record, timeline event, recalc."""
    mood_score = MOOD_VALUES[payload.mood]

    record = (await db.execute(
        select(WellnessRecord).where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.date_recorded == date.today(),
        ).order_by(WellnessRecord.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    if record is None:
        record = WellnessRecord(
            student_id=student_id,
            mood_score=mood_score,
            date_recorded=date.today(),
        )
        db.add(record)
    else:
        record.mood_score = mood_score
    await db.flush()
    await db.refresh(record)

    db.add(StudentTimeline(
        student_id=student_id,
        event_type="mood_log",
        reference_id=record.record_id,
        event_description=f"Mood check-in: {payload.mood}",
    ))

    await _recalculate_wellness(db, student_id, "mood")

    score = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id)
        .order_by(WellnessScore.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    streak = await _checkin_streak_days(db, student_id)

    return MoodCheckinResponse(
        record=WellnessRecordResponse.model_validate(record),
        wellness=_score_response(score, streak),
    )


# -------------------------------------------------------------------
# Emotion summary (computed on read from emotion_history)
# -------------------------------------------------------------------

async def get_emotion_summary(
    db: AsyncSession, student_id: uuid.UUID, window_days: int = 7
) -> EmotionSummaryResponse:
    """Current/dominant emotion, stability, and trends over rolling windows."""
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)

    snapshots = (await db.execute(
        select(EmotionSnapshot)
        .where(EmotionSnapshot.student_id == student_id, EmotionSnapshot.created_at >= month_ago)
        .order_by(EmotionSnapshot.created_at.desc())
    )).scalars().all()

    if not snapshots:
        return EmotionSummaryResponse(has_data=False)

    window_cutoff = now - timedelta(days=window_days)
    window = [s for s in snapshots if s.created_at >= window_cutoff] or snapshots[:1]

    counts = Counter(s.current_emotion for s in window)
    dominant, dominant_count = counts.most_common(1)[0]
    confidences = [float(s.confidence) for s in window if s.confidence is not None]

    def _dominant_per_bucket(bucket_key) -> list[EmotionTrendPoint]:
        buckets: dict[str, Counter] = {}
        for s in snapshots:
            buckets.setdefault(bucket_key(s.created_at), Counter())[s.current_emotion] += 1
        return [
            EmotionTrendPoint(period=period, emotion=counter.most_common(1)[0][0])
            for period, counter in sorted(buckets.items())
        ]

    weekly = _dominant_per_bucket(lambda dt: dt.date().isoformat())[-7:]
    monthly = _dominant_per_bucket(
        lambda dt: (dt.date() - timedelta(days=dt.weekday())).isoformat()
    )[-5:]

    return EmotionSummaryResponse(
        has_data=True,
        current_emotion=snapshots[0].current_emotion,
        dominant_emotion=dominant,
        stability=round(dominant_count / len(window), 2),
        confidence=round(sum(confidences) / len(confidences), 2) if confidences else None,
        weekly_trend=weekly,
        monthly_trend=monthly,
        timeline=[
            EmotionTimelinePoint(
                created_at=s.created_at, emotion=s.current_emotion, intensity=s.intensity
            )
            for s in snapshots[:20]
        ],
    )
