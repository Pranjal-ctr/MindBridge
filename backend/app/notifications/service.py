"""
MindBridge Notifications Service
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.schemas import NotificationResponse
from database.models import Notification


async def list_notifications(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[NotificationResponse], int, int]:
    """List user notifications and unread count."""
    count_result = await db.execute(
        select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
    )
    total = count_result.scalar() or 0

    unread_result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
    )
    unread_count = unread_result.scalar() or 0

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    notifications = result.scalars().all()

    return [NotificationResponse.model_validate(n) for n in notifications], total, unread_count


async def notify_users(
    db: AsyncSession,
    user_ids: list[uuid.UUID],
    title: str,
    message: str,
) -> int:
    """Create one notification per user (fan-out helper for system events).

    Flushes but does not commit -- the caller owns the transaction.
    """
    unique_ids = set(user_ids)
    for user_id in unique_ids:
        db.add(Notification(user_id=user_id, title=title, message=message))
    if unique_ids:
        await db.flush()
    return len(unique_ids)


async def mark_as_read(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Mark a single notification as read."""
    await db.execute(
        update(Notification)
        .where(Notification.notification_id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.flush()


async def mark_all_as_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Mark all notifications as read for a user."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    await db.flush()
