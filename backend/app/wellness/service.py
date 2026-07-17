"""
Kio Wellness Service
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.wellness.schemas import (
    DailyCheckinInfo,
    DailyCheckinRequest,
    DailyCheckinResponse,
    DailyCheckinStatusResponse,
    EmotionSummaryResponse,
    EmotionTimelinePoint,
    EmotionTrendPoint,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    JournalEntryCreate,
    JournalEntryResponse,
    MoodCalendarDay,
    MoodCalendarResponse,
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


# -------------------------------------------------------------------
# Mood Check-in (official, per 12-hour window, max 2 submissions)
# -------------------------------------------------------------------

# 5-level mood scale -> 1-10 mood_score (keeps engine math unchanged).
# API identifiers are stable; the frontend renders its own display labels.
DAILY_MOOD_VALUES = {"amazing": 10, "good": 8, "okay": 5, "low": 3, "very_difficult": 1}

# Initial check-in + at most one update per 12-hour window
MAX_CHECKINS_PER_WINDOW = 2


def _current_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """The current 12-hour window in UTC: [00:00, 12:00) or [12:00, 24:00)."""
    now = now or datetime.now(timezone.utc)
    if now.hour < 12:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=12)
    else:
        start = now.replace(hour=12, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=12)
    return start, end


async def _window_checkins(
    db: AsyncSession, student_id: uuid.UUID
) -> tuple[list[WellnessRecord], datetime]:
    """Official check-ins (mood_label set) in the current window, oldest first."""
    window_start, window_end = _current_window()
    records = (await db.execute(
        select(WellnessRecord).where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.mood_label.isnot(None),
            WellnessRecord.created_at >= window_start,
        ).order_by(WellnessRecord.created_at.asc())
    )).scalars().all()
    return list(records), window_end


def _checkin_info(record: WellnessRecord) -> DailyCheckinInfo:
    return DailyCheckinInfo(
        date=record.date_recorded,
        mood=record.mood_label,
        reason=record.mood_reason or "other",
        reflection=record.reflection,
        created_at=record.created_at,
    )


async def get_daily_checkin_status(
    db: AsyncSession, student_id: uuid.UUID
) -> DailyCheckinStatusResponse:
    """Check-in state for the current 12-hour window (latest entry is current)."""
    records, window_end = await _window_checkins(db, student_id)
    if not records:
        return DailyCheckinStatusResponse(
            completed_today=False,
            updates_remaining=MAX_CHECKINS_PER_WINDOW,
            window_ends_at=window_end,
        )
    return DailyCheckinStatusResponse(
        completed_today=True,
        checkin=_checkin_info(records[-1]),
        updates_remaining=max(0, MAX_CHECKINS_PER_WINDOW - len(records)),
        window_ends_at=window_end,
    )


async def submit_daily_checkin(
    db: AsyncSession, student_id: uuid.UUID, payload: DailyCheckinRequest
) -> DailyCheckinResponse:
    """Record an official mood check-in for the current 12-hour window.

    Each submission is stored as its own row (history is kept); the latest one
    is the current mood. At most 2 per window (initial + one update) -- 409 after.
    """
    existing, _window_end = await _window_checkins(db, student_id)

    if len(existing) >= MAX_CHECKINS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mood already updated for this session",
        )

    record = WellnessRecord(
        student_id=student_id,
        date_recorded=date.today(),
        mood_score=DAILY_MOOD_VALUES[payload.mood],
        mood_label=payload.mood,
        mood_reason=payload.reason,
        reflection=payload.reflection or None,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    is_update = len(existing) > 0
    db.add(StudentTimeline(
        student_id=student_id,
        event_type="daily_checkin",
        reference_id=record.record_id,
        event_description=(
            f"Mood {'update' if is_update else 'check-in'}: {payload.mood} ({payload.reason})"
        ),
    ))

    await _recalculate_wellness(db, student_id, "daily_checkin")

    score = (await db.execute(
        select(WellnessScore)
        .where(WellnessScore.student_id == student_id)
        .order_by(WellnessScore.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    streak = await _checkin_streak_days(db, student_id)

    return DailyCheckinResponse(
        checkin=_checkin_info(record),
        wellness=_score_response(score, streak),
        updates_remaining=max(0, MAX_CHECKINS_PER_WINDOW - len(existing) - 1),
    )


# -------------------------------------------------------------------
# Mood Calendar
# -------------------------------------------------------------------

async def get_mood_calendar(
    db: AsyncSession,
    student_id: uuid.UUID,
    month: str,
    include_reason: bool = True,
) -> MoodCalendarResponse:
    """One entry per day of the month that has data (official label preferred)."""
    try:
        first = datetime.strptime(month, "%Y-%m").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="month must be formatted YYYY-MM",
        )
    next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)

    records = (await db.execute(
        select(WellnessRecord)
        .where(
            WellnessRecord.student_id == student_id,
            WellnessRecord.date_recorded >= first,
            WellnessRecord.date_recorded < next_month,
        )
        .order_by(WellnessRecord.date_recorded.asc(), WellnessRecord.created_at.asc())
    )).scalars().all()

    # Latest record per day; a record carrying the official label wins.
    by_day: dict[date, WellnessRecord] = {}
    for r in records:
        current = by_day.get(r.date_recorded)
        if current is None or r.mood_label is not None or current.mood_label is None:
            if current is None or current.mood_label is None or r.mood_label is not None:
                by_day[r.date_recorded] = r

    return MoodCalendarResponse(
        month=month,
        days=[
            MoodCalendarDay(
                date=day,
                mood=rec.mood_label,
                mood_score=rec.mood_score,
                reason=rec.mood_reason if include_reason else None,
                note=rec.reflection if include_reason else None,
            )
            for day, rec in sorted(by_day.items())
            if rec.mood_label is not None or rec.mood_score is not None
        ],
    )
