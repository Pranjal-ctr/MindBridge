"""Google auth, student onboarding, and guardian management.

Revision ID: 007_google_onboarding_guardians
Revises: 006_security_and_admin
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "007_google_onboarding_guardians"
down_revision = "006_security_and_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Users: Google auth support ---
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(20), server_default="password", nullable=False),
    )
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    # Google-only accounts have no local password
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)

    # --- Student guardians ---
    op.create_table(
        "student_guardians",
        sa.Column("guardian_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id", UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("relationship", sa.String(30), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column(
            "linked_parent_id", UUID(as_uuid=True),
            sa.ForeignKey("parent_profiles.parent_id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
    )
    # At most one primary guardian per student
    op.create_index(
        "uq_guardian_one_primary", "student_guardians", ["student_id"],
        unique=True, postgresql_where=sa.text("is_primary"),
    )

    # --- Parent invite codes: optional tie to a guardian record ---
    op.add_column(
        "parent_invite_codes",
        sa.Column(
            "guardian_id", UUID(as_uuid=True),
            sa.ForeignKey("student_guardians.guardian_id", ondelete="CASCADE"), nullable=True,
        ),
    )

    # --- Student onboarding questionnaire ---
    op.create_table(
        "student_onboarding",
        sa.Column(
            "student_id", UUID(as_uuid=True),
            sa.ForeignKey("student_profiles.student_id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("class_level", sa.String(30), nullable=True),
        sa.Column("help_goals", JSONB, server_default="[]"),
        sa.Column("hobbies", JSONB, server_default="[]"),
        sa.Column("strengths", JSONB, server_default="[]"),
        sa.Column("interaction_style", sa.String(50), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("student_onboarding")
    op.drop_column("parent_invite_codes", "guardian_id")
    op.drop_index("uq_guardian_one_primary", table_name="student_guardians")
    op.drop_table("student_guardians")
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "google_sub")
