"""
Central audit-log helper.

Every sensitive platform-admin mutation should call log_audit() so the action,
actor, target, structured details, and request context (IP + user agent) land
in the immutable audit_logs table. Rows are added to the caller's session and
committed with it, so an audit entry never outlives a rolled-back mutation.

There are two ways in, and the choice is a deliberate failure policy:

    log_audit()          -- joins the caller's transaction. If the audit write
                            fails, the mutation fails with it. Use for
                            security, RBAC, and admin actions, where an
                            unrecorded change is worse than a failed one.

    log_audit_detached() -- opens its own session and commits immediately,
                            swallowing any error. Use where the audit row must
                            survive a rollback of the surrounding request
                            (a safety signal), or where a failed insert must
                            never take the product down with it (a login, a
                            crisis notification). Never lets an audit problem
                            block a crisis alert reaching a counselor.

Privacy: this is a mental-health product used by minors. Audit rows record
*that* something happened and to which record -- never what was said. See
scrub_details() and docs/audit-logging.md.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit_actions import AuditResult, AuditSeverity
from app.observability import get_request_id
from database.models import AuditLog, User

logger = logging.getLogger(__name__)

# Substrings that must never appear as a details key. Matching is on the
# lowercased key, so "student_password" and "PasswordHash" are both caught.
#
# This is a backstop, not the guarantee. The guarantee is that call sites pass
# references and short enums rather than content, and the tests in
# test_audit.py assert that no secret or message text reaches the table. A
# denylist alone would always be one new field name behind.
_REDACT_KEY_SUBSTRINGS = (
    "password", "passwd", "secret", "token", "jwt", "credential",
    "api_key", "apikey", "authorization", "auth_header", "otp",
    "oauth_code", "authorization_code", "access_code", "private_key",
    "session_key", "signature",
    # Free-form content that could carry what a student actually said.
    "message_text", "student_message", "transcript", "conversation_text",
    "chat_text", "narrative", "explanation", "reflection", "journal",
    "note_text", "body_text", "raw_text", "excerpt", "snippet",
)

REDACTED = "[redacted]"

# Details are metadata, not prose. Anything longer than this is either a bug
# or someone about to paste a conversation into the audit trail.
_MAX_STRING_LEN = 200
_MAX_KEYS = 40


def scrub_details(details: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Strip anything that looks like a secret or like free-form content.

    Redacts by key name, caps string length, and bounds the number of keys.
    Nested dicts and lists are walked, because a details payload assembled
    from a model dump can nest a password hash two levels down.
    """
    if not details:
        return details
    return _scrub_value(details, depth=0)


def _scrub_value(value: Any, depth: int) -> Any:
    if depth > 4:
        return REDACTED
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for i, (key, val) in enumerate(value.items()):
            if i >= _MAX_KEYS:
                out["_truncated"] = True
                break
            lowered = str(key).lower()
            if any(bad in lowered for bad in _REDACT_KEY_SUBSTRINGS):
                out[str(key)] = REDACTED
            else:
                out[str(key)] = _scrub_value(val, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_scrub_value(v, depth + 1) for v in value[:20]]
    if isinstance(value, str) and len(value) > _MAX_STRING_LEN:
        return value[:_MAX_STRING_LEN] + "…[truncated]"
    return value


def _request_context(request: Request | None) -> tuple[str | None, str | None]:
    """IP and user agent, both bounded to their column widths."""
    if request is None:
        return None, None
    ip_address = request.client.host if request.client is not None else None
    user_agent = request.headers.get("user-agent")
    if user_agent:
        user_agent = user_agent[:255]
    return (ip_address[:50] if ip_address else None), user_agent


def build_audit_row(
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    actor: User | None = None,
    actor_role: str | None = None,
    tenant_id: uuid.UUID | None = None,
    result: str = AuditResult.SUCCESS,
    severity: str = AuditSeverity.INFO,
) -> AuditLog:
    """
    Construct (but do not persist) an audit row.

    `actor` is a convenience: pass the authenticated User and the role and
    school scope are taken from it, so a caller cannot accidentally attribute
    an event to the wrong school by hand. An explicit actor_role/tenant_id
    still wins, which is what platform-admin actions need -- the event belongs
    to the school being acted *on*, not to the admin's own tenant.
    """
    ip_address, user_agent = _request_context(request)

    if actor is not None:
        if user_id is None:
            user_id = actor.user_id
        if actor_role is None:
            actor_role = actor.role
        if tenant_id is None:
            tenant_id = actor.tenant_id

    request_id = get_request_id()
    # "-" is the ContextVar's out-of-request sentinel; store NULL instead so a
    # background job's row does not look like it belongs to a request.
    if request_id == "-":
        request_id = None

    return AuditLog(
        audit_id=uuid.uuid4(),
        user_id=user_id,
        action=action[:100],
        entity_type=entity_type[:50] if entity_type else None,
        entity_id=entity_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=scrub_details(details),
        actor_role=actor_role[:50] if actor_role else None,
        tenant_id=tenant_id,
        result=result,
        severity=severity,
        request_id=request_id[:64] if request_id else None,
    )


async def log_audit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    actor: User | None = None,
    actor_role: str | None = None,
    tenant_id: uuid.UUID | None = None,
    result: str = AuditResult.SUCCESS,
    severity: str = AuditSeverity.INFO,
) -> None:
    """
    Add an audit row to the current session (flushed, committed by caller).

    Fails closed: if this raises, the caller's transaction is poisoned and the
    mutation it was recording does not happen either. That is the intended
    behaviour for admin and RBAC changes.
    """
    db.add(build_audit_row(
        user_id=user_id, action=action, entity_type=entity_type,
        entity_id=entity_id, details=details, request=request,
        actor=actor, actor_role=actor_role, tenant_id=tenant_id,
        result=result, severity=severity,
    ))
    await db.flush()


async def log_audit_detached(
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    actor_role: str | None = None,
    tenant_id: uuid.UUID | None = None,
    result: str = AuditResult.SUCCESS,
    severity: str = AuditSeverity.INFO,
) -> None:
    """
    Write an audit row in its own session, committed immediately.

    Fails open: any error is logged and reported, never raised. Used where the
    surrounding request is expected to roll back (a rejected login) or where
    the product action must proceed regardless (a crisis notification).

    Takes no `actor` object because the caller's User may belong to a session
    that is about to be rolled back; pass the scalar ids instead.
    """
    from database.session import async_session_factory

    row = build_audit_row(
        user_id=user_id, action=action, entity_type=entity_type,
        entity_id=entity_id, details=details, request=request,
        actor_role=actor_role, tenant_id=tenant_id,
        result=result, severity=severity,
    )
    try:
        async with async_session_factory() as db:
            db.add(row)
            await db.commit()
    except Exception:
        # An audit failure must not become a product outage on this path.
        # It is logged with the request id, so the gap is itself traceable.
        logger.exception(
            "audit write failed action=%s entity=%s", action, entity_type
        )
