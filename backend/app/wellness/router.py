"""
MindBridge Wellness Router
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
    EmotionSummaryResponse,
    GoalCreate,
    GoalListResponse,
    GoalResponse,
    GoalUpdate,
    JournalEntryCreate,
    JournalEntryResponse,
    JournalListResponse,
    MoodCheckinRequest,
    MoodCheckinResponse,
    WellnessListResponse,
    WellnessRecordCreate,
    WellnessRecordResponse,
    WellnessScoreHistoryResponse,
    WellnessScoreResponse,
)
from app.wellness.service import (
    create_goal,
    create_journal_entry,
    create_wellness_record,
    get_emotion_summary,
    get_wellness_score,
    get_wellness_score_history,
    list_goals,
    list_journal_entries,
    list_wellness_records,
    log_mood_checkin,
    update_goal,
)
from database.session import get_db

router = APIRouter()


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
