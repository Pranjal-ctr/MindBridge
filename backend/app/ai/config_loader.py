"""
Route resolution for one AI feature.

Precedence, highest first:

    1. An ACTIVE row in ai_feature_routes  -- a deliberate per-feature override
    2. The platform runtime config          -- the admin's global choice
    3. Environment defaults                 -- the startup baseline

Layer 1 predates this module and is kept: running risk detection on a different
model than chat is a real need, and this is the mechanism for it. What changed
(migration 019) is that the seven seeded rows are no longer active. They were
seeded *defaults*, identical in intent to layer 2 -- and while they were active,
a platform-level provider switch would have applied to nothing, because every
feature had a row shadowing it. An override is now something an admin turns on
deliberately, and the admin UI labels which features have one.

Nothing here reads an API key. Whether a provider is usable is the registry's
question, asked by the router immediately before the call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.runtime_config import get_active_config
from app import config as app_config
from database.models import AIFeatureRoute

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeatureRoute:
    """The provider/model a single feature will use for one call.

    Frozen and resolved once per call: an admin saving a new configuration
    mid-request cannot change where that request is already going.
    """

    feature_name: str
    primary_provider: str
    primary_model: str
    fallback_provider: str | None
    fallback_model: str | None
    max_retries: int
    #: "feature_override" | "platform_config" | "environment" -- which layer
    #: supplied this. Surfaced in the admin UI and useful in an incident.
    source: str


async def load_feature_route(db: AsyncSession, feature_name: str) -> FeatureRoute:
    override = (
        await db.execute(
            select(AIFeatureRoute).where(
                AIFeatureRoute.feature_name == feature_name,
                AIFeatureRoute.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()

    if override is not None:
        return FeatureRoute(
            feature_name=feature_name,
            primary_provider=override.primary_provider,
            primary_model=override.primary_model,
            fallback_provider=override.fallback_provider,
            fallback_model=override.fallback_model,
            max_retries=override.max_retries,
            source="feature_override",
        )

    config = await get_active_config(db)
    return FeatureRoute(
        feature_name=feature_name,
        primary_provider=config.primary_provider,
        primary_model=config.primary_model,
        # A fallback that is configured but disabled must not be routed to.
        fallback_provider=config.fallback_provider if config.fallback_active else None,
        fallback_model=config.fallback_model if config.fallback_active else None,
        max_retries=app_config.settings.AI_DEFAULT_MAX_RETRIES,
        source="platform_config" if config.source == "database" else "environment",
    )
