"""
MindBridge Wellness Service
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.wellness.schemas import (
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    JournalEntryCreate,
    JournalEntryResponse,
    WellnessRecordCreate,
    WellnessRecordResponse,
)
from database.models import Goal, JournalEntry, WellnessRecord


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
