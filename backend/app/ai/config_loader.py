"""
DB-first AI feature routing config, with hardcoded fallback.

Mirrors the existing ai_prompt_versions pattern (app/ai/service.py::_load_active_prompt):
load the active route from the DB, falling back to a hardcoded Gemini route if no
row is configured for a given feature yet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from database.models import AIFeatureRoute

logger = logging.getLogger(__name__)


@dataclass
class FeatureRoute:
    feature_name: str
    primary_provider: str
    primary_model: str
    fallback_provider: str | None
    fallback_model: str | None
    max_retries: int


def _default_route(feature_name: str) -> FeatureRoute:
    return FeatureRoute(
        feature_name=feature_name,
        primary_provider="gemini",
        primary_model=settings.GEMINI_MODEL,
        fallback_provider=None,
        fallback_model=None,
        max_retries=settings.AI_DEFAULT_MAX_RETRIES,
    )


async def load_feature_route(db: AsyncSession, feature_name: str) -> FeatureRoute:
    result = await db.execute(
        select(AIFeatureRoute).where(
            AIFeatureRoute.feature_name == feature_name,
            AIFeatureRoute.is_active == True,  # noqa: E712
        )
    )
    route = result.scalar_one_or_none()

    if route is None:
        logger.info("No DB route for feature %s, using default Gemini route", feature_name)
        return _default_route(feature_name)

    return FeatureRoute(
        feature_name=route.feature_name,
        primary_provider=route.primary_provider,
        primary_model=route.primary_model,
        fallback_provider=route.fallback_provider,
        fallback_model=route.fallback_model,
        max_retries=route.max_retries,
    )
