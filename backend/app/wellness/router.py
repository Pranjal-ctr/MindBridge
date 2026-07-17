"""
Kio Wellness Router
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.service import get_student_id_for_user
from app.dependencies import CurrentUser
from app.wellness.schemas import (
    ActivitiesResponse,
    ActivityCompleteRequest,
    DailyCheckinRequest,
    DailyCheckinResponse,
    DailyCheckinStatusResponse,
    EmotionSummaryResponse,
    GoalCreate,
    GoalListResponse,
    GoalResponse,
    GoalUpdate,
    JournalEntryCreate,
    JournalEntryResponse,
    JournalListResponse,
    MoodCalendarResponse,
    MoodCheckinRequest,
    MoodCheckinResponse,
    PersonalInsightsResponse,
    WeeklyReportResponse,
    WellnessListResponse,
    WellnessRecordCreate,
    WellnessRecordResponse,
    WellnessScoreHistoryResponse,
    WellnessScoreResponse,
    weekly_report_response,
)
from app.wellness.service import (
    create_goal,
    create_journal_entry,
    create_wellness_record,
    get_daily_checkin_status,
    get_emotion_summary,
    get_mood_calendar,
    get_wellness_score,
    get_wellness_score_history,
    list_goals,
    list_journal_entries,
    list_wellness_records,
    log_mood_checkin,
    submit_daily_checkin,
    update_goal,
)
from database.session import get_db

router = APIRouter()


# -------------------------------------------------------------------
# Daily Check-in (official, once per calendar day)
# -------------------------------------------------------------------

@router.get("/checkin/today", response_model=DailyCheckinStatusResponse)
async def checkin_status(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Check-in state for the current 12-hour window (gates the dashboard)."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await get_daily_checkin_status(db, student_id)


@router.post("/checkin", response_model=DailyCheckinResponse, status_code=201)
async def daily_checkin(
    payload: DailyCheckinRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit an official mood check-in (mood + reason, optional reflection).

    Max 2 per 12-hour window (initial + one update) -- 409 after that.
    """
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await submit_daily_checkin(db, student_id, payload)


@router.get("/mood-calendar", response_model=MoodCalendarResponse)
async def mood_calendar(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
):
    """Per-day mood entries for a month (official check-in labels preferred)."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await get_mood_calendar(db, student_id, month)


# -------------------------------------------------------------------
# Personal Insights, Activities & Weekly Report (intelligence layer)
# -------------------------------------------------------------------

@router.get("/insights", response_model=PersonalInsightsResponse)
async def personal_insights(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Pattern-mined personal observations; empty until enough history exists."""
    from app.intelligence.personal_insights import mine_personal_insights

    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await mine_personal_insights(db, student_id)


@router.get("/activities", response_model=ActivitiesResponse)
async def personalized_activities(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Personalized activity suggestions (AI-tailored, signal-based fallback)."""
    from app.intelligence.activities import get_personalized_activities

    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await get_personalized_activities(db, student_id)


@router.post("/activities/complete", status_code=201)
async def complete_activity(
    payload: ActivityCompleteRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Persist an activity completion (409 if already completed)."""
    from app.intelligence.activities import complete_activity as complete

    student_id = await get_student_id_for_user(db, current_user.user_id)
    await complete(db, student_id, payload.activity_id, payload.title)
    return {"status": "logged"}


@router.get("/weekly-report", response_model=WeeklyReportResponse)
async def student_weekly_report(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """This week's AI summary written for the student (cached per ISO week)."""
    from app.intelligence.reports import get_weekly_report

    student_id = await get_student_id_for_user(db, current_user.user_id)
    report = await get_weekly_report(db, student_id, "student")
    return weekly_report_response(report)


# -------------------------------------------------------------------
# Wellness Score & Emotions (computed by the intelligence layer)
# -------------------------------------------------------------------

@router.get("/score", response_model=WellnessScoreResponse)
async def get_score(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Latest computed wellness score with breakdown, explanation, and streak."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await get_wellness_score(db, student_id)


@router.get("/score/history", response_model=WellnessScoreHistoryResponse)
async def get_score_history(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(30, ge=1, le=365),
):
    """Wellness score timeline for charts."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await get_wellness_score_history(db, student_id, days)


@router.post("/mood", response_model=MoodCheckinResponse, status_code=201)
async def mood_checkin(
    payload: MoodCheckinRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """One-tap mood check-in (happy/okay/down); updates today's record and the score."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await log_mood_checkin(db, student_id, payload)


@router.get("/emotions", response_model=EmotionSummaryResponse)
async def get_emotions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    window: int = Query(7, ge=1, le=30),
):
    """Current/dominant emotion, stability, and weekly/monthly trends."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await get_emotion_summary(db, student_id, window)


# -------------------------------------------------------------------
# Wellness Records
# -------------------------------------------------------------------

@router.post("/records", response_model=WellnessRecordResponse, status_code=201)
async def log_wellness(
    payload: WellnessRecordCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Log a daily wellness check-in."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await create_wellness_record(db, student_id, payload)


@router.get("/records", response_model=WellnessListResponse)
async def get_wellness_records(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """Get wellness history with optional date range filter."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    records, total = await list_wellness_records(db, student_id, start_date, end_date)
    return WellnessListResponse(records=records, total=total)


# -------------------------------------------------------------------
# Goals
# -------------------------------------------------------------------

@router.post("/goals", response_model=GoalResponse, status_code=201)
async def create_new_goal(
    payload: GoalCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new wellness goal."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await create_goal(db, student_id, payload)


@router.get("/goals", response_model=GoalListResponse)
async def get_goals(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None, pattern=r"^(active|completed|paused|abandoned)$"),
):
    """List the student's goals with optional status filter."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    goals, total = await list_goals(db, student_id, status)
    return GoalListResponse(goals=goals, total=total)


@router.put("/goals/{goal_id}", response_model=GoalResponse)
async def update_goal_endpoint(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a goal's status or details."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await update_goal(db, goal_id, student_id, payload)


# -------------------------------------------------------------------
# Journal
# -------------------------------------------------------------------

@router.post("/journal", response_model=JournalEntryResponse, status_code=201)
async def create_journal(
    payload: JournalEntryCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new journal entry."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    return await create_journal_entry(db, student_id, payload)


@router.get("/journal", response_model=JournalListResponse)
async def get_journal_entries(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List journal entries."""
    student_id = await get_student_id_for_user(db, current_user.user_id)
    entries, total = await list_journal_entries(db, student_id, page, page_size)
    return JournalListResponse(entries=entries, total=total)
