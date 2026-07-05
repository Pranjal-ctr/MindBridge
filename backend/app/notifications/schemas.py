"""
MindBridge Notifications Schemas
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """Notification response."""
    notification_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    message: str
    is_read: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    unread_count: int
