"""
AIRouter: the single entry point every AI feature calls through.

Responsibilities, in order:

1. Apply Kio-side guardrails BEFORE any provider is chosen -- input size, output
   bound, per-user/per-feature/global rates, concurrency, token ceilings. These
   are provider-neutral on purpose: a fallback provider must not be a way around
   a ceiling the primary hit.
2. Resolve the route ONCE per call (per-feature override -> platform runtime
   config -> environment) and carry it for the lifetime of the request, so an
   admin changing the configuration mid-flight cannot swap the provider out from
   under a call already in progress.
3. Call the primary provider with bounded retry on transient errors.
4. Fall back to the configured secondary provider only when the failure is
   fallback-eligible, at most once, with no path back to the primary.
5. Write one AIUsageLog row per attempt and one structured log line per attempt.
6. Raise the final error so each caller keeps its existing, feature-specific
   safe-failure behaviour.

What this module does NOT do is decide anything about safety. It returns text;
every caller then runs it through the existing pipeline (parse -> schema
validate -> safety floor -> derive level -> crisis). A fallback response takes
exactly the same path as a primary one, and a response that fails validation is
never re-asked of another model.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import factory, guardrails, registry
from app.ai.config_loader import FeatureRoute, load_feature_route
from app.ai.errors import AIError, AIGuardrailError, AIProviderUnavailableError
from app.ai.providers.base import ProviderResponse
from app.ai.usage import log_usage
from app import config as app_config
from app.observability import get_request_id

logger = logging.getLogger(__name__)

_BASE_RETRY_DELAY = 2.0

#: Hard ceiling on retries regardless of what a route asks for. A DB row with
#: max_retries=99 would otherwise be a way to bill the platform.
_MAX_RETRIES_CEILING = 3


async def _call_once(
    provider_name: str,
    *,
    model: str,
    system_prompt: str,
    contents: list[dict],
    temperature: float,
    max_output_tokens: int,
    response_schema: dict | None,
) -> ProviderResponse:
    provider = factory.get_provider(provider_name)
    response = await provider.generate(
        model=model,
        system_prompt=system_prompt,
        contents=contents,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_schema=response_schema,
        timeout_seconds=app_config.settings.AI_REQUEST_TIMEOUT_SECONDS,
    )
    response.provider = provider_name
    return response


async def _call_with_retry(
    provider_name: str,
    *,
    model: str,
    system_prompt: str,
    contents: list[dict],
    temperature: float,
    max_output_tokens: int,
    max_retries: int,
    response_schema: dict | None,
) -> ProviderResponse:
    """Call one provider, retrying only errors that are marked retryable.

    Retry is decided by the error class, never by matching exception text, so a
    provider rewording a message cannot silently change failover behaviour.
    Permanent failures (bad key, unsupported model, malformed request) raise on
    the first attempt -- retrying them only spends time and money to be told the
    same thing again.
    """
    attempts = min(max_retries, _MAX_RETRIES_CEILING)
    for attempt in range(attempts + 1):
        try:
            return await _call_once(
                provider_name,
                model=model,
                system_prompt=system_prompt,
                contents=contents,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_schema=response_schema,
            )
        except AIError as exc:
            if exc.retryable and attempt < attempts:
                delay = _BASE_RETRY_DELAY * (2**attempt)
                logger.info(
                    "ai_retry provider=%s model=%s category=%s attempt=%d/%d delay_s=%.1f",
                    provider_name, model, exc.category, attempt + 1, attempts + 1, delay,
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
    response_schema: dict | None = None,
) -> tuple[str, dict]:
    """
    Run a generation through the configured route for `feature`.

    Returns (text, metadata). Raises the final AIError if the primary and (if
    eligible and configured) the fallback both fail -- callers keep their own
    feature-specific error handling.
    """
    # --- 1. Guardrails, before a provider is even chosen ----------------
    max_output_tokens = guardrails.clamp_output_tokens(max_output_tokens)
    guardrails.assert_input_within_limit(system_prompt, contents)

    user_key = str(student_id) if student_id else None
    admitted = guardrails.assert_request_rates(feature=feature, user_key=user_key)
    try:
        await guardrails.assert_token_ceilings(db)
    except AIGuardrailError:
        guardrails.release_admissions(admitted)
        raise

    # --- 2. Resolve the route once; this call keeps it ------------------
    route = await load_feature_route(db, feature)

    with guardrails.ConcurrencySlot(user_key):
        response, metadata = await _attempt(
            db, route, feature,
            system_prompt=system_prompt,
            contents=contents,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_schema=response_schema,
            conversation_id=conversation_id,
            student_id=student_id,
        )
    return response, metadata


async def _attempt(
    db: AsyncSession,
    route: FeatureRoute,
    feature: str,
    *,
    system_prompt: str,
    contents: list[dict],
    temperature: float,
    max_output_tokens: int,
    response_schema: dict | None,
    conversation_id: uuid.UUID | None,
    student_id: uuid.UUID | None,
) -> tuple[str, dict]:
    """Primary, then at most one fallback. Never back to the primary."""
    text, metadata, primary_error = await _try_provider(
        db, route.primary_provider, route.primary_model,
        feature=feature,
        system_prompt=system_prompt,
        contents=contents,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        max_retries=route.max_retries,
        response_schema=response_schema,
        conversation_id=conversation_id,
        student_id=student_id,
        fallback_used=False,
    )
    if text is not None:
        return text, metadata

    if not (route.fallback_provider and route.fallback_model):
        raise primary_error

    # Fallback is a cost decision as much as an availability one. A rate limit
    # or a bad credential is NOT a reason to redirect traffic at a second paid
    # provider -- see app/ai/errors.py for why each category is classified as
    # it is.
    if not primary_error.fallback_eligible:
        logger.info(
            "ai_no_fallback feature=%s provider=%s category=%s reason=not_eligible",
            feature, route.primary_provider, primary_error.category,
        )
        raise primary_error

    logger.warning(
        "ai_fallback feature=%s from=%s to=%s category=%s request_id=%s",
        feature, route.primary_provider, route.fallback_provider,
        primary_error.category, get_request_id(),
    )

    fallback_text, fallback_metadata, fallback_error = await _try_provider(
        db, route.fallback_provider, route.fallback_model,
        feature=feature,
        system_prompt=system_prompt,
        contents=contents,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        max_retries=route.max_retries,
        response_schema=response_schema,
        conversation_id=conversation_id,
        student_id=student_id,
        fallback_used=True,
    )
    if fallback_text is not None:
        return fallback_text, fallback_metadata

    # Both failed. The fallback's error is the more recent, but the primary's
    # is usually the more diagnostic -- it is the provider that was supposed to
    # serve this. Raise the primary's, having logged both.
    raise primary_error


async def _try_provider(
    db: AsyncSession,
    provider_name: str,
    model: str,
    *,
    feature: str,
    system_prompt: str,
    contents: list[dict],
    temperature: float,
    max_output_tokens: int,
    max_retries: int,
    response_schema: dict | None,
    conversation_id: uuid.UUID | None,
    student_id: uuid.UUID | None,
    fallback_used: bool,
) -> tuple[str | None, dict, AIError | None]:
    """One provider, with retries. Returns (text|None, metadata, error|None)."""
    start_time = time.monotonic()

    try:
        # Support + credential, then breaker. Both raise AIError subclasses
        # with the right eligibility flags, so an unusable provider is handled
        # by exactly the same path as a failing one.
        registry.assert_usable(provider_name, model)
        guardrails.assert_circuit_closed(provider_name)

        response = await _call_with_retry(
            provider_name,
            model=model,
            system_prompt=system_prompt,
            contents=contents,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            max_retries=max_retries,
            response_schema=response_schema,
        )
    except AIError as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Only transient failures count toward the breaker. Five configuration
        # errors in a row are still a configuration error, and tripping a
        # cooldown for them would outlast the operator's fix.
        if exc.retryable or exc.fallback_eligible:
            guardrails.record_provider_failure(provider_name, exc.category)

        logger.warning(
            "ai_call provider=%s model=%s feature=%s success=false "
            "failure_category=%s fallback_used=%s latency_ms=%d request_id=%s",
            provider_name, model, feature, exc.category, fallback_used,
            elapsed_ms, get_request_id(),
        )
        await log_usage(
            db,
            feature_name=feature,
            provider=provider_name,
            model=model,
            latency_ms=elapsed_ms,
            input_tokens=None,
            output_tokens=None,
            success=False,
            error=exc,
            fallback_used=fallback_used,
            conversation_id=conversation_id,
            student_id=student_id,
        )
        return None, {}, exc
    except Exception as exc:  # noqa: BLE001
        # An unmapped exception is a Kio bug, not a provider failure. Wrapped
        # so callers only ever handle AIError, and logged without its text --
        # which is unreviewed and could contain anything in scope where it was
        # raised, including the prompt.
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        wrapped = AIProviderUnavailableError(
            f"unmapped {type(exc).__name__} from {provider_name}", provider=provider_name
        )
        logger.exception(
            "ai_call provider=%s model=%s feature=%s success=false "
            "failure_category=unmapped request_id=%s",
            provider_name, model, feature, get_request_id(),
        )
        await log_usage(
            db,
            feature_name=feature, provider=provider_name, model=model,
            latency_ms=elapsed_ms, input_tokens=None, output_tokens=None,
            success=False, error=exc, fallback_used=fallback_used,
            conversation_id=conversation_id, student_id=student_id,
        )
        return None, {}, wrapped

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    guardrails.record_provider_success(provider_name)

    logger.info(
        "ai_call provider=%s model=%s feature=%s success=true "
        "latency_ms=%d input_tokens=%s output_tokens=%s fallback_used=%s request_id=%s",
        provider_name, model, feature, elapsed_ms,
        response.input_tokens, response.output_tokens, fallback_used, get_request_id(),
    )
    await log_usage(
        db,
        feature_name=feature,
        provider=provider_name,
        model=model,
        latency_ms=elapsed_ms,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        success=True,
        fallback_used=fallback_used,
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
    return response.text, metadata, None
