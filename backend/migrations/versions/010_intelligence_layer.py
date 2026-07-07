"""Intelligence layer: AI risk fields, emotion/wellness/stress history, platform config.

Revision ID: 010_intelligence_layer
Revises: 009_ai_routes_seed
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "010_intelligence_layer"
down_revision = "009_ai_routes_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- risk_assessments: AI analysis fields + counselor review queue ---
    op.add_column(
        "risk_assessments",
        sa.Column(
            "message_id", UUID(as_uuid=True),
            sa.ForeignKey("messages.message_id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.add_column("risk_assessments", sa.Column("categories", JSONB, server_default="{}"))
    op.add_column("risk_assessments", sa.Column("confidence", sa.Numeric(3, 2), nullable=True))
    op.add_column("risk_assessments", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("risk_assessments", sa.Column("review_status", sa.String(20), nullable=True))
    op.add_column(
        "risk_assessments",
        sa.Column(
            "reviewed_by", UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.add_column(
        "risk_assessments",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_risk_review_pending",
        "risk_assessments",
        ["review_status"],
        postgresql_where=sa.text("review_status = 'pending'"),
    )

    # --- emotion_history ---
    op.create_table(
        "emotion_history",
        sa.Column("emotion_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id", UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "conversation_id", UUID(as_uuid=True),
            sa.ForeignKey("conversations.conversation_id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("current_emotion", sa.String(30), nullable=False),
        sa.Column("intensity", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("secondary_emotions", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_emotion_student_created", "emotion_history", ["student_id", "created_at"])

    # --- wellness_scores ---
    op.create_table(
        "wellness_scores",
        sa.Column("wellness_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id", UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("trend", sa.String(20), server_default="stable", nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("components", JSONB, server_default="{}"),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("trigger_source", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_wellness_scores_student_created", "wellness_scores", ["student_id", "created_at"]
    )

    # --- stress_distributions ---
    op.create_table(
        "stress_distributions",
        sa.Column("distribution_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id", UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "conversation_id", UUID(as_uuid=True),
            sa.ForeignKey("conversations.conversation_id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("categories", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_stress_student_created", "stress_distributions", ["student_id", "created_at"])

    # --- platform_config ---
    op.create_table(
        "platform_config",
        sa.Column("config_key", sa.String(100), primary_key=True),
        sa.Column("config_value", JSONB, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- parent_insight_history: structured AI payload ---
    op.add_column("parent_insight_history", sa.Column("insights_json", JSONB, server_default="{}"))

    # Seed default config (values mirror the code fallbacks in app/intelligence/config.py)
    op.execute(
        """
        INSERT INTO platform_config (config_key, config_value, description) VALUES
        ('wellness_weights',
         '{"checkin_engagement": 0.10, "mood_level": 0.15, "mood_stability": 0.10,
           "conversation_sentiment": 0.15, "stress_trend": 0.15, "risk_signal": 0.15,
           "goal_progress": 0.05, "journal_consistency": 0.05,
           "counselor_engagement": 0.05, "improvement_delta": 0.05}',
         'Component weights for the deterministic wellness score (must sum to 1.0).'),
        ('risk_level_bands',
         '{"yellow": 40, "red": 65, "critical": 85}',
         'Minimum overall risk score (0-100) for each level; below yellow = green.'),
        ('crisis',
         '{"trigger_score": 65, "notify_parents": true, "tripwire_level": "red", "deescalate_after": 3}',
         'Crisis workflow: trigger threshold, parent notification, keyword-tripwire level, consecutive lower assessments needed to de-escalate.'),
        ('parent_insight',
         '{"ttl_hours": 6, "regen_on_risk_change": true}',
         'Parent insight narrative regeneration: staleness TTL and risk-change trigger.'),
        ('analysis',
         '{"context_messages": 20, "stress_smoothing": 0.6}',
         'Combined message analysis: history window and stress-distribution smoothing factor (new-value share).')
        ON CONFLICT (config_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_column("parent_insight_history", "insights_json")
    op.drop_table("platform_config")
    op.drop_index("ix_stress_student_created", table_name="stress_distributions")
    op.drop_table("stress_distributions")
    op.drop_index("ix_wellness_scores_student_created", table_name="wellness_scores")
    op.drop_table("wellness_scores")
    op.drop_index("ix_emotion_student_created", table_name="emotion_history")
    op.drop_table("emotion_history")
    op.drop_index("ix_risk_review_pending", table_name="risk_assessments")
    op.drop_column("risk_assessments", "reviewed_at")
    op.drop_column("risk_assessments", "reviewed_by")
    op.drop_column("risk_assessments", "review_status")
    op.drop_column("risk_assessments", "summary")
    op.drop_column("risk_assessments", "confidence")
    op.drop_column("risk_assessments", "categories")
    op.drop_column("risk_assessments", "message_id")
