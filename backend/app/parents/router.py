"""
Kio Parents Router
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, require_role
from app.parents.schemas import (
    ChildInsightResponse,
    ChildrenListResponse,
    WellnessTrendPoint,
)
from app.parents.service import (
    _verify_parent_child_link,
    get_child_insights,
    get_linked_children,
    get_wellness_trend_range,
)
from app.wellness.schemas import (
    MoodCalendarResponse,
    WeeklyReportResponse,
    weekly_report_response,
)
from database.session import get_db

router = APIRouter()


@router.get(
    "/children",
    response_model=ChildrenListResponse,
    dependencies=[Depends(require_role("parent"))],
)
async def list_children(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all children linked to the current parent."""
    children = await get_linked_children(db, current_user.user_id)
    return ChildrenListResponse(children=children)


@router.get(
    "/children/{student_id}/insights",
    response_model=ChildInsightResponse,
    dependencies=[Depends(require_role("parent"))],
)
async def get_insights(
    student_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """
    Get aggregated wellness insights for a child.

    Returns live wellness/risk/mood/stress data plus the latest AI narrative.
    Raw conversations are never exposed. A stale narrative is served as-is
    and regenerated in the background.
    """
    from app.intelligence.insights import refresh_parent_insight_task

    response, stale = await get_child_insights(db, current_user.user_id, student_id)
    if stale:
        background_tasks.add_task(refresh_parent_insight_task, student_id)
    return response


@router.get(
    "/children/{student_id}/wellness-trend",
    response_model=list[WellnessTrendPoint],
    dependencies=[Depends(require_role("parent"))],
)
async def child_wellness_trend(
    student_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=365),
):
    """Wellness trend over 7/30/90 days (daily latest computed score, ISO dates)."""
    return await get_wellness_trend_range(db, current_user.user_id, student_id, days)


@router.get(
    "/children/{student_id}/mood-calendar",
    response_model=MoodCalendarResponse,
    dependencies=[Depends(require_role("parent"))],
)
async def child_mood_calendar(
    student_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
):
    """Monthly mood calendar (mood labels only -- reasons/reflections stay private)."""
    from app.wellness.service import get_mood_calendar

    await _verify_parent_child_link(db, current_user.user_id, student_id)
    return await get_mood_calendar(db, student_id, month, include_reason=False)


@router.get(
    "/children/{student_id}/weekly-report",
    response_model=WeeklyReportResponse,
    dependencies=[Depends(require_role("parent"))],
)
async def child_weekly_report(
    student_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """This week's AI summary written for the parent (cached per ISO week)."""
    from app.intelligence.reports import get_weekly_report

    await _verify_parent_child_link(db, current_user.user_id, student_id)
    report = await get_weekly_report(db, student_id, "parent")
    return weekly_report_response(report)
