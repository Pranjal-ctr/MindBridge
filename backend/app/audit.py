"""
Central audit-log helper.

Every sensitive platform-admin mutation should call log_audit() so the action,
actor, target, structured details, and request context (IP + user agent) land
in the immutable audit_logs table. Rows are added to the caller's session and
committed with it, so an audit entry never outlives a rolled-back mutation.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuditLog


async def log_audit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Add an audit row to the current session (flushed, committed by caller)."""
    ip_address: str | None = None
    user_agent: str | None = None
    if request is not None:
        if request.client is not None:
            ip_address = request.client.host
        user_agent = request.headers.get("user-agent")
        if user_agent:
            user_agent = user_agent[:255]

    db.add(AuditLog(
        audit_id=uuid.uuid4(),
        user_id=user_id,
        action=action[:100],
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    ))
    await db.flush()
