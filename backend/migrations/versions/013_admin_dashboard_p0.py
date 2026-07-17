"""Platform Admin P0: school profile + soft delete, risk assignment, audit context,
counselor-school assignments.

Revision ID: 013_admin_dashboard_p0
Revises: 012_student_activities
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "013_admin_dashboard_p0"
down_revision = "012_student_activities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # School profile fields + soft delete (all nullable — backward compatible)
    op.add_column("tenants", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("contact_email", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("contact_phone", sa.String(30), nullable=True))
    op.add_column("tenants", sa.Column("principal_name", sa.String(150), nullable=True))
    op.add_column("tenants", sa.Column("logo_url", sa.String(500), nullable=True))
    op.add_column("tenants", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # Risk Center: counselor assignment + persisted resolution notes
    op.add_column(
        "risk_assessments",
        sa.Column(
            "assigned_counselor_id", UUID(as_uuid=True),
            sa.ForeignKey("counselor_profiles.counselor_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("risk_assessments", sa.Column("resolution_note", sa.Text(), nullable=True))
    op.create_index(
        "ix_risk_assessments_assigned", "risk_assessments", ["assigned_counselor_id"]
    )

    # Audit context (device + structured details) and fast recent-first listing
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(255), nullable=True))
    op.add_column("audit_logs", sa.Column("details", JSONB, nullable=True))
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # Counselor <-> school directory assignments (informational; booking stays platform-wide)
    op.create_table(
        "counselor_school_assignments",
        sa.Column("assignment_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "counselor_id", UUID(as_uuid=True),
            sa.ForeignKey("counselor_profiles.counselor_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id", UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "assigned_by", UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("counselor_id", "tenant_id", name="uq_counselor_tenant"),
    )


def downgrade() -> None:
    op.drop_table("counselor_school_assignments")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_column("audit_logs", "details")
    op.drop_column("audit_logs", "user_agent")

    op.drop_index("ix_risk_assessments_assigned", table_name="risk_assessments")
    op.drop_column("risk_assessments", "resolution_note")
    op.drop_column("risk_assessments", "assigned_counselor_id")

    op.drop_column("users", "deleted_at")

    op.drop_column("tenants", "deleted_at")
    op.drop_column("tenants", "logo_url")
    op.drop_column("tenants", "principal_name")
    op.drop_column("tenants", "contact_phone")
    op.drop_column("tenants", "contact_email")
    op.drop_column("tenants", "address")
    op.drop_column("tenants", "city")
