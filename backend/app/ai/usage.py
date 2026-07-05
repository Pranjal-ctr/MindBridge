"""
Usage logging: one AIUsageLog row per provider call attempt.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pricing import estimate_cost_usd
from database.models import AIUsageLog


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
    error_message: str | None = None,
    conversation_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
) -> None:
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
        error_message=error_message,
    )
    db.add(entry)
    await db.flush()
