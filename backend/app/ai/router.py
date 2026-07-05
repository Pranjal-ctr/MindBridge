"""
AIRouter: the single entry point every AI feature calls through.

Responsibilities:
1. Resolve the feature's provider/model route (DB-first, see config_loader.py).
2. Call the primary provider with retry/backoff on transient errors.
3. Fall back to a secondary provider/model if the primary is exhausted and a
   fallback is configured.
4. Log one AIUsageLog row per provider outcome (primary and, if attempted,
   fallback) -- provider, model, latency, tokens, estimated cost, success.
5. Raise the final exception on total failure so each caller in app/ai/service.py
   keeps its existing, feature-specific error handling (friendly chat fallback
   text, silent no-op for memory extraction/title generation, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import factory
from app.ai.config_loader import FeatureRoute, load_feature_route
from app.ai.providers.base import AIProvider, ProviderResponse
from app.ai.usage import log_usage

logger = logging.getLogger(__name__)

_BASE_RETRY_DELAY = 2.0


async def _call_with_retry(
    provider: AIProvider,
    *,
    model: str,
    system_prompt: str,
    contents: list[dict],
    temperature: float,
    max_output_tokens: int,
    max_retries: int,
) -> ProviderResponse:
    for attempt in range(max_retries + 1):
        try:
            return await provider.generate(
                model=model,
                system_prompt=system_prompt,
                contents=contents,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except Exception as e:
            if provider.is_retryable(e) and attempt < max_retries:
                delay = _BASE_RETRY_DELAY * (2 ** attempt)
                logger.info(
                    "%s rate limited (attempt %d/%d), retrying in %.1fs",
                    provider.name, attempt + 1, max_retries + 1, delay,
                )
                await asyncio.sleep(delay)
                continue
            raise


async def run(
    db: AsyncSession,
    *,
    feature: str,
    system_prompt: str,
    contents: list[dict],
    temperature: float = 0.7,
    max_output_tokens: int = 1024,
    conversation_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
) -> tuple[str, dict]:
    """
    Run a generation through the configured route for `feature`.

    Returns (text, metadata). Raises the final exception if both the primary
    and (if configured) fallback provider fail -- callers keep their own
    feature-specific error handling.
    """
    route = await load_feature_route(db, feature)

    text, metadata = await _try_provider(
        db, route, route.primary_provider, route.primary_model,
        system_prompt, contents, temperature, max_output_tokens,
        feature, conversation_id, student_id,
    )
    if text is not None:
        return text, metadata

    if route.fallback_provider and route.fallback_model:
        logger.warning(
            "Primary provider %s failed for feature %s, trying fallback %s",
            route.primary_provider, feature, route.fallback_provider,
        )
        fallback_text, fallback_metadata = await _try_provider(
            db, route, route.fallback_provider, route.fallback_model,
            system_prompt, contents, temperature, max_output_tokens,
            feature, conversation_id, student_id,
            fallback_used=True,
        )
        if fallback_text is not None:
            return fallback_text, fallback_metadata

    # Both primary and fallback (if any) failed -- re-raise the last error.
    raise metadata["_exception"]


async def _try_provider(
    db: AsyncSession,
    route: FeatureRoute,
    provider_name: str,
    model: str,
    system_prompt: str,
    contents: list[dict],
    temperature: float,
    max_output_tokens: int,
    feature: str,
    conversation_id: uuid.UUID | None,
    student_id: uuid.UUID | None,
    fallback_used: bool = False,
) -> tuple[str | None, dict]:
    provider = factory.get_provider(provider_name)
    start_time = time.monotonic()
    try:
        response = await _call_with_retry(
            provider,
            model=model,
            system_prompt=system_prompt,
            contents=contents,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            max_retries=route.max_retries,
        )
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        await log_usage(
            db,
            feature_name=feature,
            provider=provider_name,
            model=model,
            latency_ms=elapsed_ms,
            input_tokens=None,
            output_tokens=None,
            success=False,
            error_message=str(e),
            conversation_id=conversation_id,
            student_id=student_id,
        )
        return None, {"_exception": e}

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    await log_usage(
        db,
        feature_name=feature,
        provider=provider_name,
        model=model,
        latency_ms=elapsed_ms,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        success=True,
        conversation_id=conversation_id,
        student_id=student_id,
    )

    from app.ai.pricing import estimate_cost_usd

    metadata = {
        "provider": provider_name,
        "model": model,
        "response_time_ms": elapsed_ms,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "estimated_cost_usd": float(
            estimate_cost_usd(provider_name, model, response.input_tokens, response.output_tokens)
        ),
        "fallback_used": fallback_used,
    }
    return response.text, metadata
