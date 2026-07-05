"""Seed AI feature routes for risk detection and parent insight.

Revision ID: 009_ai_routes_seed
Revises: 008_platform_counselors
Create Date: 2026-07-06
"""

from alembic import op

revision = "009_ai_routes_seed"
down_revision = "008_platform_counselors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO ai_feature_routes
            (feature_name, primary_provider, primary_model, fallback_provider, fallback_model, max_retries, is_active)
        VALUES
            ('risk_detection', 'gemini', 'gemini-2.5-flash', NULL, NULL, 1, true),
            ('parent_insight', 'gemini', 'gemini-2.5-flash', NULL, NULL, 1, true)
        ON CONFLICT (feature_name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM ai_feature_routes WHERE feature_name IN ('risk_detection', 'parent_insight')"
    )
