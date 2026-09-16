"""
Usage logging: one AIUsageLog row per provider call attempt.

This is the telemetry table -- provider, model, latency, tokens, cost, outcome.
It is deliberately not a copy of the conversation: no prompt, no response, no
student message text ever reaches it. A row says that a call to a named model
happened and how it went, which is everything cost and reliability reporting
needs and nothing a counselling transcript would add.

`error_message` is the one field that could leak by accident, because a raw
provider exception can quote the request that caused it -- and the request is
the prompt. Everything written to it goes through _safe_error() first.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIError
from app.ai.pricing import estimate_cost_usd
from app.observability import get_request_id
from database.models import AIUsageLog

#: Upper bound on a stored error string. Long provider errors are the ones
#: most likely to be echoing a request body back.
_MAX_ERROR_CHARS = 200


def _safe_error(exc: Exception | None) -> tuple[str | None, str | None]:
    """(failure_category, redacted_message) for an exception.

    For a mapped AIError the adapter has already constructed a message that
    names no credential and quotes no prompt, so it is used directly. Anything
    else is an unmapped exception -- a Kio bug rather than a provider failure --
    and only its type name is stored, because its text is unreviewed and could
    contain anything that was in scope where it was raised.
    """
    if exc is None:
        return None, None
    if isinstance(exc, AIError):
        return exc.category, str(exc)[:_MAX_ERROR_CHARS]
    return "unknown", f"unmapped {type(exc).__name__}"


async def log_usage(
    db: AsyncSession,
    *,
    feature_name: str,
    provider: str,
    model: str,
    latency_ms: int,
    input_tokens: int | None,
    output_tokens: int | None,
    success: bool,
    error: Exception | None = None,
    fallback_used: bool = False,
    conversation_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
) -> None:
    failure_category, error_message = _safe_error(error)

    request_id = get_request_id()
    if request_id == "-":  # outside an HTTP request (background pipeline)
        request_id = None

    entry = AIUsageLog(
        usage_id=uuid.uuid4(),
        feature_name=feature_name,
        provider=provider,
        model=model,
        conversation_id=conversation_id,
        student_id=student_id,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost_usd(provider, model, input_tokens, output_tokens),
        success=success,
        failure_category=failure_category,
        fallback_used=fallback_used,
        request_id=request_id,
        error_message=error_message,
    )
    db.add(entry)
    await db.flush()
