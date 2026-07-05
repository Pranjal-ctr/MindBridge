"""Platform-wide counselors: profile fields + availability slots.

Revision ID: 008_platform_counselors
Revises: 007_google_onboarding_guardians
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "008_platform_counselors"
down_revision = "007_google_onboarding_guardians"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("counselor_profiles", sa.Column("qualification", sa.String(200), nullable=True))
    op.add_column("counselor_profiles", sa.Column("specializations", JSONB, server_default="[]"))
    op.add_column("counselor_profiles", sa.Column("languages", JSONB, server_default="[]"))
    op.add_column(
        "counselor_profiles",
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "counselor_profiles",
        sa.Column("is_available", sa.Boolean(), server_default="true", nullable=False),
    )

    op.create_table(
        "counselor_availability",
        sa.Column("slot_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "counselor_id", UUID(as_uuid=True),
            sa.ForeignKey("counselor_profiles.counselor_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_booked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_availability_counselor_start", "counselor_availability", ["counselor_id", "start_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_availability_counselor_start", table_name="counselor_availability")
    op.drop_table("counselor_availability")
    op.drop_column("counselor_profiles", "is_available")
    op.drop_column("counselor_profiles", "is_verified")
    op.drop_column("counselor_profiles", "languages")
    op.drop_column("counselor_profiles", "specializations")
    op.drop_column("counselor_profiles", "qualification")
