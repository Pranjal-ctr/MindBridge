"""
DB-first platform configuration with code-fallback defaults.

Mirrors the ai_feature_routes pattern (app/ai/config_loader.py): read the
value from the platform_config table, fall back to the defaults below when no
row exists. DB values are shallow-merged over the defaults so adding a new
sub-key in code never breaks an older stored row.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import PlatformConfig

logger = logging.getLogger(__name__)

# Keep in sync with the seed in migrations/versions/010_intelligence_layer.py.
DEFAULTS: dict[str, dict] = {
    "wellness_weights": {
        "checkin_engagement": 0.10,
        "mood_level": 0.15,
        "mood_stability": 0.10,
        "conversation_sentiment": 0.15,
        "stress_trend": 0.15,
        "risk_signal": 0.15,
        "goal_progress": 0.05,
        "journal_consistency": 0.05,
        "counselor_engagement": 0.05,
        "improvement_delta": 0.05,
    },
    "risk_level_bands": {"yellow": 40, "red": 65, "critical": 85},
    "crisis": {
        "trigger_score": 65,
        "notify_parents": True,
        "tripwire_level": "red",
        "deescalate_after": 3,
    },
    "parent_insight": {"ttl_hours": 6, "regen_on_risk_change": True},
    "analysis": {"context_messages": 20, "stress_smoothing": 0.6},
}


async def load_config(db: AsyncSession, config_key: str) -> dict:
    """Load one config value, DB-first with code fallback. Raises KeyError for unknown keys."""
    default = DEFAULTS[config_key]

    result = await db.execute(
        select(PlatformConfig).where(PlatformConfig.config_key == config_key)
    )
    row = result.scalar_one_or_none()
    if row is None or not isinstance(row.config_value, dict):
        return dict(default)

    return {**default, **row.config_value}


def derive_risk_level(overall_score: float, bands: dict) -> str:
    """Map a 0-100 risk score to a level using configured bands (server-side, never the LLM)."""
    if overall_score >= bands["critical"]:
        return "critical"
    if overall_score >= bands["red"]:
        return "red"
    if overall_score >= bands["yellow"]:
        return "yellow"
    return "green"
