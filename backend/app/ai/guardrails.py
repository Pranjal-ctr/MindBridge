"""
Guardrails applied around every AI call, whichever provider serves it.

These are cost and availability controls, NOT safety controls. Nothing here
decides whether a response is safe to show a student -- that remains entirely
in the existing pipeline (parse -> validate -> safety floor -> derive level ->
crisis). A guardrail refusing a call produces Kio's existing safe-failure
behaviour for that feature; it never produces a substitute answer.

Two properties are deliberate:

  * Guardrails run BEFORE provider selection, so a fallback provider cannot be
    used to get around a ceiling the primary hit. "Gemini is out of quota, send
    it all to OpenAI instead" is precisely the failure this prevents.

  * Guardrails raise AIGuardrailError, which is neither retryable nor
    fallback-eligible. Retrying a quota refusal is just a second refusal.

Scope: in-process. Counters and breaker state live in this module's dicts, so
they are per-worker. Kio runs WEB_CONCURRENCY=1 by default and its HTTP rate
limiter already has the same property and the same caveat. With N workers,
every limit here is effectively N times looser and each worker keeps its own
breaker. Making these global needs shared state (the existing rate limiter
would move at the same time); until then the single-worker default is what
they are calibrated for. Token ceilings are the exception -- they are counted
in SQL against ai_usage_logs and so are already global.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AICircuitOpenError, AIGuardrailError
from app import config as app_config
from database.models import AIUsageLog

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60.0

# scope key -> timestamps of calls admitted within the rolling window
_windows: dict[str, deque[float]] = defaultdict(deque)
# user key -> number of provider calls currently in flight
_in_flight: dict[str, int] = defaultdict(int)


def _admit(key: str, limit: int) -> bool:
    """Sliding-window admission. True if the call fits under `limit`."""
    now = time.monotonic()
    window = _windows[key]
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


def _release_one(key: str) -> None:
    """Undo an admission, for when a later guardrail in the same check refuses."""
    window = _windows.get(key)
    if window:
        window.pop()


# -------------------------------------------------------------------
# Provider circuit breaker
# -------------------------------------------------------------------

@dataclass
class _BreakerState:
    consecutive_failures: int = 0
    open_until: float = 0.0
    last_failure_category: str | None = None


_breakers: dict[str, _BreakerState] = defaultdict(_BreakerState)


def circuit_is_open(provider: str) -> bool:
    """Whether this provider is in cooldown after repeated transient failures."""
    state = _breakers[provider]
    if state.open_until and time.monotonic() < state.open_until:
        return True
    if state.open_until:
        # Cooldown elapsed: close the breaker and let one call through. If it
        # fails, the counter is already at the threshold, so it reopens
        # immediately -- a half-open probe without the extra machinery.
        state.open_until = 0.0
        state.consecutive_failures = 0
    return False


def record_provider_success(provider: str) -> None:
    state = _breakers[provider]
    state.consecutive_failures = 0
    state.open_until = 0.0
    state.last_failure_category = None


def record_provider_failure(provider: str, category: str) -> None:
    """Count a transient failure; trip the breaker at the threshold.

    Only transient failures are counted by the caller. A configuration error
    repeated five times is still a configuration error, and putting a provider
    in cooldown for it would convert an operator mistake into an outage that
    outlasts the fix.
    """
    state = _breakers[provider]
    state.consecutive_failures += 1
    state.last_failure_category = category

    if state.consecutive_failures >= app_config.settings.AI_CIRCUIT_FAILURE_THRESHOLD:
        state.open_until = time.monotonic() + app_config.settings.AI_CIRCUIT_COOLDOWN_SECONDS
        logger.warning(
            "AI circuit opened provider=%s consecutive_failures=%d cooldown_s=%.0f "
            "last_category=%s",
            provider,
            state.consecutive_failures,
            app_config.settings.AI_CIRCUIT_COOLDOWN_SECONDS,
            category,
        )


def assert_circuit_closed(provider: str) -> None:
    if circuit_is_open(provider):
        raise AICircuitOpenError(
            f"{provider} is in cooldown after repeated failures", provider=provider
        )


def breaker_snapshot() -> dict[str, dict]:
    """Breaker state per provider, for the admin status panel."""
    now = time.monotonic()
    return {
        provider: {
            "consecutive_failures": state.consecutive_failures,
            "open": bool(state.open_until and now < state.open_until),
            "cooldown_remaining_seconds": (
                max(0, int(state.open_until - now)) if state.open_until else 0
            ),
            "last_failure_category": state.last_failure_category,
        }
        for provider, state in _breakers.items()
    }


# -------------------------------------------------------------------
# Request-shape bounds
# -------------------------------------------------------------------

def clamp_output_tokens(requested: int) -> int:
    """Bound max_output_tokens to the configured ceiling.

    Clamps rather than refuses: every existing caller passes a sane value
    (20 for titles, 512 for memory, 1024 elsewhere), so the ceiling exists to
    stop a future caller passing something unbounded, not to break today's.
    """
    ceiling = app_config.settings.AI_MAX_OUTPUT_TOKENS_CEILING
    if requested <= 0:
        return ceiling
    return min(requested, ceiling)


def assert_input_within_limit(system_prompt: str, contents: list[dict]) -> int:
    """Refuse a call whose payload exceeds AI_MAX_INPUT_CHARS. Returns the size.

    Refuses rather than truncates, deliberately. The largest inputs Kio builds
    are conversation context for risk detection, and silently dropping the
    oldest or newest part of that could remove the very message that indicates
    danger while still returning a confident-looking low-risk score. A refusal
    reaches the caller's safe-failure path, which is visible; a truncation
    would not be.

    Kio's own limits already make this unreachable in practice (messages are
    capped at 4000 chars and context at 20 messages) -- it is a backstop
    against a future caller that builds a payload some other way.
    """
    size = len(system_prompt or "")
    for item in contents:
        for part in item.get("parts") or []:
            if isinstance(part, dict):
                size += len(part.get("text") or "")

    if size > app_config.settings.AI_MAX_INPUT_CHARS:
        raise AIGuardrailError(
            f"AI request payload is {size} characters, over the "
            f"{app_config.settings.AI_MAX_INPUT_CHARS} limit",
            guardrail="input_size",
        )
    return size


# -------------------------------------------------------------------
# Rate and usage ceilings
# -------------------------------------------------------------------

async def _tokens_used_since(db: AsyncSession, truncate_to: str) -> int:
    """Total reported tokens since the start of the current day/month.

    Sums only what providers actually reported. Rows with NULL token counts
    contribute nothing rather than an estimate -- a ceiling enforced against
    invented numbers is worse than no ceiling.
    """
    # date_trunc on a timestamptz truncates in the *session* timezone, so on a
    # non-UTC server "today" would start at the wrong instant -- the same bug
    # that silently emptied the analytics trend chart. Both sides are pinned to
    # UTC here for the same reason.
    period_start = func.date_trunc(
        truncate_to, func.timezone("UTC", func.now())
    )
    result = await db.execute(
        select(
            func.coalesce(func.sum(AIUsageLog.input_tokens), 0)
            + func.coalesce(func.sum(AIUsageLog.output_tokens), 0)
        ).where(func.timezone("UTC", AIUsageLog.created_at) >= period_start)
    )
    return int(result.scalar() or 0)


async def assert_token_ceilings(db: AsyncSession) -> None:
    """Refuse if a configured daily/monthly token ceiling is already reached.

    Both default to 0 (disabled). They are platform-wide and provider-neutral,
    so enabling the fallback cannot be used to spend past them.
    """
    if app_config.settings.AI_DAILY_TOKEN_CEILING > 0:
        used = await _tokens_used_since(db, "day")
        if used >= app_config.settings.AI_DAILY_TOKEN_CEILING:
            raise AIGuardrailError(
                f"daily token ceiling reached ({used})", guardrail="daily_token_ceiling"
            )

    if app_config.settings.AI_MONTHLY_TOKEN_CEILING > 0:
        used = await _tokens_used_since(db, "month")
        if used >= app_config.settings.AI_MONTHLY_TOKEN_CEILING:
            raise AIGuardrailError(
                f"monthly token ceiling reached ({used})",
                guardrail="monthly_token_ceiling",
            )


def assert_request_rates(*, feature: str, user_key: str | None) -> list[str]:
    """Per-user, per-feature and global rolling-minute ceilings.

    Returns the admission keys that were consumed, so the caller can release
    them if a later guardrail refuses -- otherwise a request blocked by the
    token ceiling would still burn a slot in all three windows.
    """
    admitted: list[str] = []

    def _try(key: str, limit: int, guardrail: str) -> None:
        if not _admit(key, limit):
            for consumed in admitted:
                _release_one(consumed)
            raise AIGuardrailError(
                f"{guardrail} limit of {limit}/min reached",
                guardrail=guardrail,
                retry_after_seconds=60,
            )
        admitted.append(key)

    if user_key:
        _try(f"ai:user:{user_key}", app_config.settings.AI_USER_REQUESTS_PER_MINUTE, "per_user")
    _try(
        f"ai:feature:{feature}",
        app_config.settings.AI_FEATURE_REQUESTS_PER_MINUTE,
        "per_feature",
    )
    _try("ai:global", app_config.settings.AI_GLOBAL_REQUESTS_PER_MINUTE, "global")
    return admitted


def release_admissions(keys: list[str]) -> None:
    for key in keys:
        _release_one(key)


# -------------------------------------------------------------------
# Concurrency
# -------------------------------------------------------------------

class ConcurrencySlot:
    """Context manager bounding one user's simultaneous in-flight AI calls.

    Stops a single client from opening many parallel requests to multiply its
    effective rate, which a per-minute window alone does not prevent. Released
    in __exit__ so a provider exception cannot leak a slot.
    """

    def __init__(self, user_key: str | None) -> None:
        self._key = user_key
        self._held = False

    def __enter__(self) -> "ConcurrencySlot":
        if self._key is None:
            return self
        limit = app_config.settings.AI_MAX_CONCURRENT_PER_USER
        if _in_flight[self._key] >= limit:
            raise AIGuardrailError(
                f"more than {limit} AI requests in flight",
                guardrail="concurrency",
                retry_after_seconds=5,
            )
        _in_flight[self._key] += 1
        self._held = True
        return self

    def __exit__(self, *exc_info) -> None:
        if self._held and self._key is not None:
            _in_flight[self._key] = max(0, _in_flight[self._key] - 1)
            self._held = False


def reset_state() -> None:
    """Clear all guardrail state. For tests."""
    _windows.clear()
    _in_flight.clear()
    _breakers.clear()
