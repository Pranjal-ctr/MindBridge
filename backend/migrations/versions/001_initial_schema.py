"""Initial schema — all 27 tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-06-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Read and execute the full schema SQL
    # In production, use individual table creates; for initial setup, we use the DDL directly.

    # --- TENANTS ---
    op.create_table(
        "tenants",
        sa.Column("tenant_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_name", sa.String(255), nullable=False),
        sa.Column("tenant_type", sa.String(50), nullable=False, server_default="school"),
        sa.Column("school_code", sa.String(50), unique=True),
        sa.Column("subscription_plan", sa.String(50), server_default="free"),
        sa.Column("student_limit", sa.Integer, server_default="100"),
        sa.Column("active_students", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- SCHOOL SETTINGS ---
    op.create_table(
        "school_settings",
        sa.Column("setting_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("school_logo", sa.Text),
        sa.Column("primary_color", sa.String(20)),
        sa.Column("wellness_threshold", sa.Numeric(5, 2)),
        sa.Column("allow_parent_notifications", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- USERS ---
    op.create_table(
        "users",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("profile_image", sa.Text),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_tenant_role", "users", ["tenant_id", "role"])

    # --- CLASSES ---
    op.create_table(
        "classes",
        sa.Column("class_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_name", sa.String(100), nullable=False),
        sa.Column("section", sa.String(20)),
        sa.Column("academic_year", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- STUDENT PROFILES ---
    op.create_table(
        "student_profiles",
        sa.Column("student_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.class_id", ondelete="SET NULL")),
        sa.Column("admission_number", sa.String(50)),
        sa.Column("age", sa.Integer),
        sa.Column("gender", sa.String(30)),
        sa.Column("wellness_score", sa.Numeric(5, 2)),
        sa.Column("risk_level", sa.String(20), server_default="green"),
        sa.Column("joined_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_student_profiles_risk", "student_profiles", ["risk_level"])

    # --- PARENT PROFILES ---
    op.create_table(
        "parent_profiles",
        sa.Column("parent_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("occupation", sa.String(100)),
        sa.Column("relationship_type", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- COUNSELOR PROFILES ---
    op.create_table(
        "counselor_profiles",
        sa.Column("counselor_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("specialization", sa.String(100)),
        sa.Column("experience_years", sa.Integer),
        sa.Column("license_number", sa.String(100)),
        sa.Column("rating", sa.Numeric(3, 2)),
        sa.Column("bio", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- SCHOOL ADMIN PROFILES ---
    op.create_table(
        "school_admin_profiles",
        sa.Column("admin_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("designation", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- STUDENT PARENT LINKS ---
    op.create_table(
        "student_parent_links",
        sa.Column("link_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("parent_profiles.parent_id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "parent_id", name="uq_student_parent"),
    )

    # --- CONVERSATIONS ---
    op.create_table(
        "conversations",
        sa.Column("conversation_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("ai_generated_title", sa.Boolean, server_default="false"),
        sa.Column("is_archived", sa.Boolean, server_default="false"),
        sa.Column("total_messages", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversations_student", "conversations", ["student_id", "created_at"])

    # --- MESSAGES ---
    op.create_table(
        "messages",
        sa.Column("message_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_type", sa.String(10), nullable=False),
        sa.Column("sender_id", UUID(as_uuid=True)),
        sa.Column("message_text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer),
        sa.Column("sentiment", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_conversation", "messages", ["conversation_id", "created_at"])

    # --- CONVERSATION TAGS ---
    op.create_table(
        "conversation_tags",
        sa.Column("tag_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_name", sa.String(100), nullable=False),
        sa.Column("confidence_score", sa.Numeric(3, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- CONVERSATION SUMMARIES ---
    op.create_table(
        "conversation_summaries",
        sa.Column("summary_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("key_topics", sa.Text),
        sa.Column("sentiment", sa.String(20)),
        sa.Column("last_message_id", UUID(as_uuid=True)),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- RISK ASSESSMENTS ---
    op.create_table(
        "risk_assessments",
        sa.Column("risk_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.conversation_id", ondelete="SET NULL")),
        sa.Column("risk_score", sa.Numeric(5, 2)),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("trigger_reason", sa.Text),
        sa.Column("generated_by", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_risk_student_level", "risk_assessments", ["student_id", "risk_level"])

    # --- MEMORY ITEMS ---
    op.create_table(
        "memory_items",
        sa.Column("memory_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("importance_score", sa.Numeric(3, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- WELLNESS RECORDS ---
    op.create_table(
        "wellness_records",
        sa.Column("record_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("mood_score", sa.Integer),
        sa.Column("stress_score", sa.Integer),
        sa.Column("confidence_score", sa.Integer),
        sa.Column("anxiety_score", sa.Integer),
        sa.Column("energy_score", sa.Integer),
        sa.Column("date_recorded", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_wellness_student_date", "wellness_records", ["student_id", "date_recorded"])

    # --- GOALS ---
    op.create_table(
        "goals",
        sa.Column("goal_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_title", sa.String(255), nullable=False),
        sa.Column("goal_description", sa.Text),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("target_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- JOURNAL ENTRIES ---
    op.create_table(
        "journal_entries",
        sa.Column("journal_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("mood_score", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- PARENT INSIGHT HISTORY ---
    op.create_table(
        "parent_insight_history",
        sa.Column("insight_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("wellness_score", sa.Numeric(5, 2)),
        sa.Column("risk_level", sa.String(20)),
        sa.Column("summary", sa.Text),
        sa.Column("recommendations", sa.Text),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- COUNSELOR SESSIONS ---
    op.create_table(
        "counselor_sessions",
        sa.Column("counselor_session_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("counselor_id", UUID(as_uuid=True), sa.ForeignKey("counselor_profiles.counselor_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="scheduled"),
        sa.Column("ai_summary", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sessions_counselor", "counselor_sessions", ["counselor_id", "scheduled_at"])

    # --- COUNSELOR NOTES ---
    op.create_table(
        "counselor_notes",
        sa.Column("note_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("counselor_session_id", UUID(as_uuid=True), sa.ForeignKey("counselor_sessions.counselor_session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("counselor_id", UUID(as_uuid=True), sa.ForeignKey("counselor_profiles.counselor_id", ondelete="CASCADE"), nullable=False),
        sa.Column("note_text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- STUDENT TIMELINE ---
    op.create_table(
        "student_timeline",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("reference_id", UUID(as_uuid=True)),
        sa.Column("event_description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_timeline_student", "student_timeline", ["student_id", "created_at"])

    # --- ANALYTICS SNAPSHOTS ---
    op.create_table(
        "analytics_snapshots",
        sa.Column("snapshot_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_month", sa.Date, nullable=False),
        sa.Column("total_students", sa.Integer, server_default="0"),
        sa.Column("avg_wellness", sa.Numeric(5, 2)),
        sa.Column("avg_risk", sa.Numeric(5, 2)),
        sa.Column("engagement_rate", sa.Numeric(5, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "snapshot_month", name="uq_tenant_snapshot_month"),
    )

    # --- NOTIFICATIONS ---
    op.create_table(
        "notifications",
        sa.Column("notification_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])

    # --- SUBSCRIPTIONS ---
    op.create_table(
        "subscriptions",
        sa.Column("subscription_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_name", sa.String(50), nullable=False),
        sa.Column("student_limit", sa.Integer, server_default="100"),
        sa.Column("active_students", sa.Integer, server_default="0"),
        sa.Column("billing_cycle", sa.String(20), server_default="monthly"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("renewal_date", sa.Date),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- PAYMENT TRANSACTIONS ---
    op.create_table(
        "payment_transactions",
        sa.Column("transaction_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("subscription_id", UUID(as_uuid=True), sa.ForeignKey("subscriptions.subscription_id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_provider", sa.String(50)),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="USD"),
        sa.Column("payment_status", sa.String(20), server_default="pending"),
        sa.Column("transaction_reference", sa.String(255)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
    )

    # --- AUDIT LOGS ---
    op.create_table(
        "audit_logs",
        sa.Column("audit_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", UUID(as_uuid=True)),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_user_action", "audit_logs", ["user_id", "action"])

    # --- FILES ---
    op.create_table(
        "files",
        sa.Column("file_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("student_profiles.student_id", ondelete="SET NULL")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.conversation_id", ondelete="SET NULL")),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(50)),
        sa.Column("file_url", sa.Text, nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- AI PROMPT VERSIONS ---
    op.create_table(
        "ai_prompt_versions",
        sa.Column("prompt_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("prompt_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("prompt_content", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- UTILITY FUNCTION: auto-update updated_at ---
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Triggers for tables with updated_at
    op.execute("""
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("""
        CREATE TRIGGER update_conversations_updated_at
            BEFORE UPDATE ON conversations
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;")
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    tables = [
        "ai_prompt_versions", "files", "audit_logs", "payment_transactions",
        "subscriptions", "notifications", "analytics_snapshots", "student_timeline",
        "counselor_notes", "counselor_sessions", "parent_insight_history",
        "journal_entries", "goals", "wellness_records", "memory_items",
        "risk_assessments", "conversation_summaries", "conversation_tags",
        "messages", "conversations", "student_parent_links",
        "school_admin_profiles", "counselor_profiles", "parent_profiles",
        "student_profiles", "classes", "users", "school_settings", "tenants",
    ]
    for table in tables:
        op.drop_table(table)
