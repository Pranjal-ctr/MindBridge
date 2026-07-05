"""Security hardening: indexes, email normalization, verification flag,
cheaper models for auxiliary AI features.

Revision ID: 006_security_and_admin
Revises: 005_ai_provider_architecture
Create Date: 2026-07-05
"""

from alembic import op
import sqlalchemy as sa

revision = "006_security_and_admin"
down_revision = "005_ai_provider_architecture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hot-path index: student memories are loaded twice per chat message
    op.create_index("ix_memory_items_student", "memory_items", ["student_id"])

    # Active invite-code lookups
    op.create_index(
        "ix_invite_student_active",
        "parent_invite_codes",
        ["student_id"],
        postgresql_where=sa.text("NOT is_used"),
    )

    # Email verification scaffold
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
    )

    # Normalize existing emails (app layer now lowercases on signup/login)
    op.execute("UPDATE users SET email = lower(email)")

    # Route auxiliary AI features to the cheaper model
    op.execute(
        """
        UPDATE ai_feature_routes
        SET primary_model = 'gemini-2.5-flash-lite'
        WHERE feature_name IN ('memory_extraction', 'title_generation')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE ai_feature_routes
        SET primary_model = 'gemini-2.5-flash'
        WHERE feature_name IN ('memory_extraction', 'title_generation')
        """
    )
    op.drop_column("users", "is_verified")
    op.drop_index("ix_invite_student_active", table_name="parent_invite_codes")
    op.drop_index("ix_memory_items_student", table_name="memory_items")
