"""AI provider-agnostic architecture: provider configs, feature routes, usage logs.

Seeds Gemini as the sole enabled provider and routes all 3 AI features to it,
exactly reproducing pre-migration behavior.

Revision ID: 005_ai_provider_architecture
Revises: 004_memory_enhancements
Create Date: 2026-07-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "005_ai_provider_architecture"
down_revision = "004_memory_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("provider_name", sa.String(50), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("default_model", sa.String(100), nullable=False),
        sa.Column("extra_config", JSONB, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            onupdate=sa.func.now(), nullable=False,
        ),
    )

    op.create_table(
        "ai_feature_routes",
        sa.Column("feature_name", sa.String(50), primary_key=True),
        sa.Column(
            "primary_provider", sa.String(50),
            sa.ForeignKey("ai_provider_configs.provider_name"), nullable=False,
        ),
        sa.Column("primary_model", sa.String(100), nullable=False),
        sa.Column(
            "fallback_provider", sa.String(50),
            sa.ForeignKey("ai_provider_configs.provider_name"), nullable=True,
        ),
        sa.Column("fallback_model", sa.String(100), nullable=True),
        sa.Column("max_retries", sa.Integer(), server_default="2", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            onupdate=sa.func.now(), nullable=False,
        ),
    )

    op.create_table(
        "ai_usage_logs",
        sa.Column("usage_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("feature_name", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column(
            "conversation_id", UUID(as_uuid=True),
            sa.ForeignKey("conversations.conversation_id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "student_id", UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.student_id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_ai_usage_provider_created", "ai_usage_logs", ["provider", "created_at"]
    )
    op.create_index(
        "ix_ai_usage_feature_created", "ai_usage_logs", ["feature_name", "created_at"]
    )

    # Seed: Gemini as the only enabled provider, all features routed to it.
    op.execute(
        """
        INSERT INTO ai_provider_configs (provider_name, display_name, is_enabled, default_model, extra_config)
        VALUES ('gemini', 'Google Gemini', true, 'gemini-2.5-flash', '{}')
        """
    )
    op.execute(
        """
        INSERT INTO ai_feature_routes
            (feature_name, primary_provider, primary_model, fallback_provider, fallback_model, max_retries, is_active)
        VALUES
            ('comrade_chat', 'gemini', 'gemini-2.5-flash', NULL, NULL, 2, true),
            ('memory_extraction', 'gemini', 'gemini-2.5-flash', NULL, NULL, 1, true),
            ('title_generation', 'gemini', 'gemini-2.5-flash', NULL, NULL, 1, true)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_feature_created", table_name="ai_usage_logs")
    op.drop_index("ix_ai_usage_provider_created", table_name="ai_usage_logs")
    op.drop_table("ai_usage_logs")
    op.drop_table("ai_feature_routes")
    op.drop_table("ai_provider_configs")
