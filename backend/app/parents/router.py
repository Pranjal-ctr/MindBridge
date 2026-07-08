"""
MindBridge Parents Router
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, require_role
from app.parents.schemas import ChildInsightResponse, ChildrenListResponse
from app.parents.service import get_child_insights, get_linked_children
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
