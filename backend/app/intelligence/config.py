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
        # Added July 2026 -- shallow merge in load_config surfaces these even
        # when an older DB row predates them (weighted mean renormalizes).
        "activity_completion": 0.05,
        "mood_recovery": 0.05,
    },
    "risk_level_bands": {"yellow": 40, "red": 65, "critical": 85},
    "crisis": {
        "trigger_score": 65,
        "notify_parents": True,
        "tripwire_level": "red",
        "deescalate_after": 3,
        # Email staff (counselors + school admins) in addition to the in-app
        # notification. Without this an acute alert only reaches someone who
        # happens to already be signed in and looking at the risk queue.
        "email_staff": True,
        # Emailing a parent that their child's risk level changed is a
        # different kind of act from an in-app badge: it lands in a shared
        # inbox, cannot be unsent, and can out a student who has not chosen to
        # tell anyone. Left OFF pending an explicit product decision — parents
        # still get the content-free in-app notification and the refreshed
        # insight either way.
        "email_parents": False,
    },
    # Safety floors: a *credible* acute signal from the LLM forces the overall
    # risk to at least `enforced_overall`, so an under-scored `overall` can never
    # hide self-harm/abuse. Deterministic guarantee on top of the prompt.
    # All values are pilot-tunable from the DB (Admin/Playground) with no deploy.
    "safety_floors": {
        "self_harm": 60,          # category score (0-100) that trips the floor
        "suicidal_ideation": 60,
        "abuse": 65,
        "enforced_overall": 70,   # overall risk is raised to at least this
        "min_confidence": 0.55,   # below this an assessment reads "inconclusive"
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


# Severity order for escalation/de-escalation comparisons
RISK_LEVEL_RANK = {"green": 0, "yellow": 1, "red": 2, "critical": 3}


def derive_risk_level(overall_score: float, bands: dict) -> str:
    """Map a 0-100 risk score to a level using configured bands (server-side, never the LLM)."""
    if overall_score >= bands["critical"]:
        return "critical"
    if overall_score >= bands["red"]:
        return "red"
    if overall_score >= bands["yellow"]:
        return "yellow"
    return "green"
