"""
Add confidence_score, is_pinned, source_conversation_id to memory_items.

Revision ID: 004_memory_enhancements
Revises: 003_parent_invite_codes
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "004_memory_enhancements"
down_revision = "003_parent_invite_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory_items",
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
    )
    op.add_column(
        "memory_items",
        sa.Column("is_pinned", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "memory_items",
        sa.Column("source_conversation_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("memory_items", "source_conversation_id")
    op.drop_column("memory_items", "is_pinned")
    op.drop_column("memory_items", "confidence_score")
