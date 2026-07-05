"""
MindBridge Notifications Router
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser
from app.notifications.schemas import NotificationListResponse
from app.notifications.service import list_notifications, mark_all_as_read, mark_as_read
from database.session import get_db

router = APIRouter()


@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List notifications for the current user."""
    notifications, total, unread_count = await list_notifications(
        db, current_user.user_id, page, page_size
    )
    return NotificationListResponse(
        notifications=notifications, total=total, unread_count=unread_count
    )


@router.put("/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark a notification as read."""
    await mark_as_read(db, notification_id, current_user.user_id)


@router.put("/read-all", status_code=204)
async def mark_all_read(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark all notifications as read."""
    await mark_all_as_read(db, current_user.user_id)
