"""
Refresh-token sessions: issue, rotate, revoke.

The design is the smallest one that makes logout mean something:

  * A refresh token names a row. No row, no refresh.
  * Refreshing rotates -- the presented token is spent and a successor issued
    in the same family.
  * A token presented after it was spent is a replay. The whole family is
    revoked, because either it was stolen or the legitimate client is racing
    itself, and continuing either quietly is worse than ending both.
  * Logging out revokes the family, so every rotation descended from that
    login dies with it.

Access tokens stay stateless and short-lived. Verifying them against the
database on every request would add a query to every single call in exchange
for cutting off an already brief window a few minutes sooner.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from database.models import RefreshSession

logger = logging.getLogger(__name__)

# Reasons are short codes rather than prose so they can be counted in a query:
# a rise in `replay` is a security signal, a rise in `logout` is just Friday.
REASON_LOGOUT = "logout"
REASON_ROTATED = "rotated"
REASON_REPLAY = "replay"
REASON_LOGOUT_ALL = "logout_all"


async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    family_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> RefreshSession:
    """Record a new refresh session, continuing a family when rotating."""
    now = datetime.now(timezone.utc)
    session = RefreshSession(
        session_id=uuid.uuid4(),
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        issued_at=now,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    if request is not None:
        agent = request.headers.get("user-agent")
        session.user_agent = agent[:255] if agent else None
        session.ip_address = request.client.host if request.client else None
    db.add(session)
    await db.flush()
    return session


async def revoke_family(
    db: AsyncSession, family_id: uuid.UUID, reason: str
) -> int:
    """Revoke every live session descended from one login."""
    result = await db.execute(
        update(RefreshSession)
        .where(RefreshSession.family_id == family_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc), revoked_reason=reason)
    )
    await db.flush()
    return result.rowcount or 0


async def revoke_all_for_user(db: AsyncSession, user_id: uuid.UUID, reason: str) -> int:
    """
    Sign out everywhere.

    The case this exists for is a student who used a shared school machine and
    wants every session gone, not just the one in front of them.
    """
    result = await db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc), revoked_reason=reason)
    )
    await db.flush()
    return result.rowcount or 0


async def consume_session(
    db: AsyncSession, session_id: uuid.UUID
) -> RefreshSession:
    """
    Validate and spend a refresh session, or refuse and explain nothing.

    Every failure returns the same message. Distinguishing "no such session"
    from "revoked" from "expired" would tell someone holding a stolen token
    exactly which one they hold.
    """
    generic = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    result = await db.execute(
        select(RefreshSession)
        .where(RefreshSession.session_id == session_id)
        # Serialise concurrent refreshes of the same row so two requests
        # cannot both observe it as live and both rotate it.
        .with_for_update()
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise generic

    if session.revoked_at is not None:
        # Replay. Whoever holds this token, the family is no longer trustworthy.
        revoked = await revoke_family(db, session.family_id, REASON_REPLAY)
        logger.warning(
            "Refresh token replay detected: user=%s family=%s sessions_revoked=%s",
            session.user_id,
            session.family_id,
            revoked,
        )
        raise generic

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise generic

    session.revoked_at = datetime.now(timezone.utc)
    session.revoked_reason = REASON_ROTATED
    await db.flush()
    return session


async def purge_expired(db: AsyncSession) -> int:
    """
    Delete sessions that expired long ago.

    Revoked rows are kept for a while on purpose: a replay can only be
    detected while the row it names still exists. Deleting eagerly would turn
    a detectable theft back into an ordinary "unknown token".
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    from sqlalchemy import delete

    result = await db.execute(
        delete(RefreshSession).where(RefreshSession.expires_at < cutoff)
    )
    await db.flush()
    return result.rowcount or 0
