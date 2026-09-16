"""
Platform AI runtime configuration: which supported provider/model is active.

Precedence, highest first:

    1. An ACTIVE per-feature route (ai_feature_routes)   -- deliberate override
    2. The platform runtime config (ai_runtime_config)   -- admin's global choice
    3. Environment defaults (AI_PRIMARY_* in settings)   -- startup baseline

Layer 1 already existed and is kept: a future need to run risk_detection on a
different model than chat is real, and that is what it is for. What changed is
that the seven seeded rows are no longer active by default (migration 019) --
they were seeded *defaults*, not admin decisions, and leaving them active meant
a platform-level switch would silently apply to nothing. An override is now
something an admin turns on deliberately, and the admin UI labels it as such.

Caching: the resolved config is held in-process and invalidated on save. Kio
runs WEB_CONCURRENCY=1 by default and already documents its rate limiter as
per-process, so this matches the deployment rather than inventing shared state
for it. See "Multi-worker" below.

This module deliberately imports nothing from app.auth. Changing the AI
configuration is not an authentication event, and the only way to be sure of
that is for this code to have no way of reaching session state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import registry
from app import config as app_config
from app.ai.errors import AIConfigurationError
from database.models import AIRuntimeConfig

logger = logging.getLogger(__name__)

#: There is exactly one platform AI configuration. A fixed primary key makes
#: that a property of the schema rather than a convention the code has to
#: remember, so "which row is active" can never become ambiguous.
SINGLETON_ID = 1


@dataclass(frozen=True)
class ResolvedAIConfig:
    """The active platform AI configuration.

    Frozen: a request resolves this once and carries it for its lifetime, so a
    concurrent admin save cannot change the provider out from under a call that
    is already in flight.
    """

    primary_provider: str
    primary_model: str
    fallback_provider: str | None
    fallback_model: str | None
    fallback_enabled: bool
    #: "environment" or "database" -- surfaced to the admin UI so it is clear
    #: whether a saved override exists or the env baseline is in effect.
    source: str = "environment"

    @property
    def fallback_active(self) -> bool:
        """Whether a fallback should actually be attempted."""
        return bool(
            self.fallback_enabled and self.fallback_provider and self.fallback_model
        )


def _from_environment() -> ResolvedAIConfig:
    # Read through the module, not an import-time binding -- see the same note
    # in app/ai/registry.py.
    settings = app_config.settings
    return ResolvedAIConfig(
        primary_provider=settings.AI_PRIMARY_PROVIDER,
        primary_model=settings.AI_PRIMARY_MODEL,
        fallback_provider=settings.AI_FALLBACK_PROVIDER or None,
        fallback_model=settings.AI_FALLBACK_MODEL or None,
        fallback_enabled=settings.AI_FALLBACK_ENABLED,
        source="environment",
    )


# In-process cache of the resolved configuration. None = not yet loaded.
_cached: ResolvedAIConfig | None = None


def invalidate_cache() -> None:
    """Drop the cached configuration so the next request re-reads the DB.

    Called after a successful admin save. Touches only this module's cache --
    no session, token, or user state is involved in an AI configuration change.
    """
    global _cached
    _cached = None


async def get_active_config(db: AsyncSession) -> ResolvedAIConfig:
    """The active platform configuration, from cache, DB, or environment.

    A DB row that is no longer valid (a model removed from the registry in a
    later release, or a credential taken out of the environment) is logged and
    ignored in favour of the environment baseline. Kio keeps answering with
    whatever is still usable rather than failing every AI request because a
    stored preference went stale.
    """
    global _cached
    if _cached is not None:
        return _cached

    row = (
        await db.execute(
            select(AIRuntimeConfig).where(AIRuntimeConfig.config_id == SINGLETON_ID)
        )
    ).scalar_one_or_none()

    if row is None:
        _cached = _from_environment()
        return _cached

    candidate = ResolvedAIConfig(
        primary_provider=row.primary_provider,
        primary_model=row.primary_model,
        fallback_provider=row.fallback_provider,
        fallback_model=row.fallback_model,
        fallback_enabled=row.fallback_enabled,
        source="database",
    )

    try:
        validate_config(candidate)
    except AIConfigurationError as exc:
        logger.error(
            "Stored AI configuration is no longer usable (%s); "
            "falling back to environment defaults",
            exc.safe_message,
        )
        _cached = _from_environment()
        return _cached

    _cached = candidate
    return _cached


def validate_config(config: ResolvedAIConfig) -> None:
    """Assert a configuration is coherent and usable, or raise AIConfigurationError.

    The same function guards the admin save path and the DB read path, so a
    configuration can never be stored that the request path would then refuse.
    Checks, in order:

      1-3. primary provider supported, model supported, model belongs to it
      4.   primary credential present on this server
      5.   the same three checks for the fallback, when enabled
      6.   primary and fallback are not the identical provider+model
      7.   fallback is fully specified when enabled
    """
    # 1-4: registry.assert_usable covers provider support, model support,
    # provider/model pairing, and credential presence.
    registry.assert_usable(config.primary_provider, config.primary_model)

    if not config.fallback_enabled:
        return

    if not config.fallback_provider or not config.fallback_model:
        raise AIConfigurationError(
            "Fallback is enabled but no fallback provider/model is selected."
        )

    registry.assert_usable(config.fallback_provider, config.fallback_model)

    if (
        config.fallback_provider == config.primary_provider
        and config.fallback_model == config.primary_model
    ):
        raise AIConfigurationError(
            "The fallback must differ from the primary provider and model. "
            "Retrying the same model is what the retry limit is for."
        )


async def save_config(
    db: AsyncSession,
    *,
    primary_provider: str,
    primary_model: str,
    fallback_provider: str | None,
    fallback_model: str | None,
    fallback_enabled: bool,
    actor_user_id,
) -> tuple[ResolvedAIConfig, ResolvedAIConfig]:
    """Validate and persist a new platform AI configuration.

    Returns (previous, new) so the caller can audit the transition.

    Validation happens BEFORE any write, so a rejected configuration leaves
    both the database row and the in-process cache untouched and the currently
    active provider serving traffic. There is no partial save: it is one row,
    written inside the caller's transaction.

    The cache is invalidated only after the write is staged. If the caller's
    transaction later rolls back, the cache is merely cold -- the next request
    re-reads the DB and sees the unchanged row, which is correct.
    """
    previous = await get_active_config(db)

    candidate = ResolvedAIConfig(
        primary_provider=primary_provider,
        primary_model=primary_model,
        fallback_provider=fallback_provider,
        fallback_model=fallback_model,
        fallback_enabled=fallback_enabled,
        source="database",
    )
    validate_config(candidate)  # raises -> nothing below runs

    row = (
        await db.execute(
            select(AIRuntimeConfig).where(AIRuntimeConfig.config_id == SINGLETON_ID)
        )
    ).scalar_one_or_none()

    if row is None:
        row = AIRuntimeConfig(config_id=SINGLETON_ID)
        db.add(row)

    row.primary_provider = candidate.primary_provider
    row.primary_model = candidate.primary_model
    row.fallback_provider = candidate.fallback_provider
    row.fallback_model = candidate.fallback_model
    row.fallback_enabled = candidate.fallback_enabled
    row.updated_by = actor_user_id

    await db.flush()
    invalidate_cache()

    return previous, replace(candidate)
