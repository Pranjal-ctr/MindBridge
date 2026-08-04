"""Counselor verdict capture: record the human judgment alongside the AI's
assessment so AI-vs-counselor agreement can be measured and a labeled dataset
accumulates from day one.

All columns are nullable -> fully backward compatible; existing rows and the
old {review_status} review payload keep working unchanged.

Revision ID: 014_counselor_verdict_capture
Revises: 013_admin_dashboard_p0
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa

revision = "014_counselor_verdict_capture"
down_revision = "013_admin_dashboard_p0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The counselor's own level for this assessment (green|yellow|red|critical).
    op.add_column(
        "risk_assessments",
        sa.Column("counselor_risk_level", sa.String(20), nullable=True),
    )
    # Whether the counselor agreed with the AI level (agree|disagree).
    op.add_column("risk_assessments", sa.Column("verdict", sa.String(20), nullable=True))
    # What happened (no_action_needed|monitoring|counseling_scheduled|
    # parent_contacted|escalated|referred_external|false_positive).
    op.add_column("risk_assessments", sa.Column("outcome", sa.String(40), nullable=True))
    # Index the labeled rows for the future evaluation/analytics queries.
    op.create_index(
        "ix_risk_assessments_verdict",
        "risk_assessments",
        ["verdict"],
        postgresql_where=sa.text("verdict IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_risk_assessments_verdict", table_name="risk_assessments")
    op.drop_column("risk_assessments", "outcome")
    op.drop_column("risk_assessments", "verdict")
    op.drop_column("risk_assessments", "counselor_risk_level")
