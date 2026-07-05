"""Parent invite codes table

Revision ID: 003_parent_invite_codes
Revises: 002_schema_improvements
Create Date: 2026-06-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "003_parent_invite_codes"
down_revision = "002_schema_improvements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parent_invite_codes",
        sa.Column("code_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(10), nullable=False, unique=True),
        sa.Column("is_used", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "used_by",
            UUID(as_uuid=True),
            sa.ForeignKey("parent_profiles.parent_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_invite_code", "parent_invite_codes", ["code"])


def downgrade() -> None:
    op.drop_index("ix_invite_code", table_name="parent_invite_codes")
    op.drop_table("parent_invite_codes")
