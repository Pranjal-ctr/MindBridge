"""Persistent per-student activity suggestions and completions.

Revision ID: 012_student_activities
Revises: 011_daily_checkin_weekly_reports
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "012_student_activities"
down_revision = "011_daily_checkin_weekly_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_activities",
        sa.Column("student_activity_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id", UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("activity_id", sa.String(60), nullable=False),   # stable slug for de-duplication
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),        # llm | catalog
        sa.Column("kind", sa.String(10), nullable=False),          # weekly | daily
        sa.Column("week_start", sa.Date(), nullable=False),        # Monday of the ISO week
        sa.Column("suggested_on", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_student_activities_week", "student_activities", ["student_id", "week_start"]
    )
    op.create_index(
        "ix_student_activities_suggested", "student_activities", ["student_id", "suggested_on"]
    )


def downgrade() -> None:
    op.drop_index("ix_student_activities_suggested", table_name="student_activities")
    op.drop_index("ix_student_activities_week", table_name="student_activities")
    op.drop_table("student_activities")
