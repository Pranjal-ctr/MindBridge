"""Consent records and the age gate.

Kio processes mental-health data belonging largely to minors. Two things were
missing entirely: any record that a user agreed to anything, and any knowledge
of how old they are.

What this adds:
  * users.date_of_birth   — the age gate needs a birth date, not the snapshot
                            integer on student_profiles.age, which goes stale
                            and was optional and self-reported anyway.
  * users.guardian_consent_status — denormalised onto the user because it gates
                            every request; joining user_consents on each one
                            would be wasteful.
  * user_consents         — append-only record of each grant. Consent is a
                            claim about a moment in time, so rows are never
                            updated: withdrawing writes revoked_at, and a new
                            policy version writes a new row. That history is
                            the evidence a regulator asks for.

All columns are nullable / defaulted, so existing rows keep working: accounts
created before this migration have no DOB and no consent record, which is
itself the accurate statement of their status.

Revision ID: 015_consent_and_age_gate
Revises: 014_counselor_verdict_capture
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "015_consent_and_age_gate"
down_revision = "014_counselor_verdict_capture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users -------------------------------------------------------
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))

    # not_required (adult) | pending | granted | denied.
    # Existing rows get NULL, meaning "unknown" — deliberately distinct from
    # not_required, so a backfill can find them rather than silently treating
    # every legacy account as an adult.
    op.add_column(
        "users",
        sa.Column("guardian_consent_status", sa.String(20), nullable=True),
    )

    # --- user_consents ----------------------------------------------
    op.create_table(
        "user_consents",
        sa.Column(
            "consent_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # terms | privacy | guardian
        sa.Column("consent_type", sa.String(20), nullable=False),
        # Which published version was agreed to. Without this, a consent record
        # proves nothing once the policy text changes.
        sa.Column("policy_version", sa.String(20), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Evidence of the grant. IP/user-agent are what makes an online consent
        # record defensible after the fact.
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        # For guardian consent: who actually granted it, and how they were
        # verified (email_link is the only method implemented today).
        sa.Column("granted_by_email", sa.String(255), nullable=True),
        sa.Column("verification_method", sa.String(30), nullable=True),
        # Withdrawal. Never delete a consent row — the fact that consent
        # existed and was later withdrawn is itself the record.
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_user_consents_user_type",
        "user_consents",
        ["user_id", "consent_type"],
    )
    # "Show me everyone still on the superseded privacy policy" — the query
    # that drives a re-consent campaign when the text changes.
    op.create_index(
        "ix_user_consents_active",
        "user_consents",
        ["consent_type", "policy_version"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_user_consents_active", table_name="user_consents")
    op.drop_index("ix_user_consents_user_type", table_name="user_consents")
    op.drop_table("user_consents")
    op.drop_column("users", "guardian_consent_status")
    op.drop_column("users", "date_of_birth")
