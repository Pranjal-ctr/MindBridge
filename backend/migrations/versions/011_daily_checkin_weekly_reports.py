"""Daily check-in fields on wellness_records + cached weekly AI reports.

Revision ID: 011_daily_checkin_weekly_reports
Revises: 010_intelligence_layer
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "011_daily_checkin_weekly_reports"
down_revision = "010_intelligence_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- wellness_records: official daily check-in fields (all nullable/additive).
    # A record whose mood_label is set is the day's official check-in; the
    # legacy one-tap /mood endpoint keeps updating mood_score only.
    op.add_column("wellness_records", sa.Column("mood_label", sa.String(20), nullable=True))
    op.add_column("wellness_records", sa.Column("mood_reason", sa.String(30), nullable=True))
    op.add_column("wellness_records", sa.Column("reflection", sa.Text(), nullable=True))

    # --- weekly_reports: one cached AI report per student/audience/ISO week ---
    op.create_table(
        "weekly_reports",
        sa.Column("report_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id", UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("audience", sa.String(20), nullable=False),  # student | parent | counselor
        sa.Column("week_start", sa.Date(), nullable=False),    # Monday of the ISO week
        sa.Column("content", JSONB, nullable=False),
        sa.Column("generated_by", sa.String(30), nullable=True),  # llm | fallback
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "audience", "week_start", name="uq_weekly_report_scope"),
    )
    op.create_index("ix_weekly_reports_student", "weekly_reports", ["student_id", "week_start"])


def downgrade() -> None:
    op.drop_index("ix_weekly_reports_student", table_name="weekly_reports")
    op.drop_table("weekly_reports")
    op.drop_column("wellness_records", "reflection")
    op.drop_column("wellness_records", "mood_reason")
    op.drop_column("wellness_records", "mood_label")
