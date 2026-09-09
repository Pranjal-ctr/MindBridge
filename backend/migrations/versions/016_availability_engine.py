"""Recurring availability engine and a real double-booking guard.

Replaces the row-per-bookable-slot model with recurring weekly schedules plus
dated exceptions. Concrete slots are computed for the range being viewed
rather than stored, so a counselor working 9-5 costs three rows instead of
thousands.

What this adds:
  * counselor_sessions.ends_at   — the load-bearing change. Overlap detection
                                   needs an end: with only scheduled_at, the
                                   question "does 10:00-10:45 clash with
                                   10:30-11:00?" cannot be asked, and the old
                                   booking path could only compare identical
                                   start times. Backfilled from the counselor's
                                   duration so historical rows stay truthful.
  * an EXCLUDE constraint       — one counselor cannot hold two overlapping
                                   live sessions, enforced by the database
                                   rather than by whoever remembers to check.
                                   Cancelled and no-show rows are excluded from
                                   the constraint: they must not keep blocking
                                   a time nobody is attending.
  * counselor_schedules         — recurring weekly availability.
  * counselor_schedule_exceptions — time off and one-off extra availability.
  * counselor_profiles settings — duration, buffer, timezone. Slot length was
                                   previously implicit in the UI, and timezone
                                   was not represented at all.

counselor_availability (the old per-slot table) is deliberately LEFT IN PLACE
and left populated. It is deprecated, not dropped: those rows are the record
of how existing bookings came to exist, and dropping them would destroy that
history for no benefit. The new engine is authoritative for new bookings.

Revision ID: 016_availability_engine
Revises: 015_consent_and_age_gate
Create Date: 2026-09-09
"""

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "016_availability_engine"
down_revision = "015_consent_and_age_gate"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

# Name kept in one place: the service layer probes for it to decide whether the
# database is enforcing overlaps or whether it must rely on row locking alone.
EXCLUSION_CONSTRAINT = "excl_counselor_session_overlap"

# Statuses that do not occupy the counselor's calendar. A cancelled session
# must free its time immediately, which the old is_booked flag never did.
INACTIVE_STATUSES = ("cancelled", "no_show")


def upgrade() -> None:
    # --- counselor_profiles: session settings ------------------------
    op.add_column(
        "counselor_profiles",
        sa.Column(
            "session_duration_minutes",
            sa.SmallInteger(),
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "counselor_profiles",
        sa.Column("buffer_minutes", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "counselor_profiles",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Asia/Kolkata",
        ),
    )

    # --- counselor_sessions: the end of a session --------------------
    op.add_column(
        "counselor_sessions",
        sa.Column("ends_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "counselor_sessions",
        sa.Column("booked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "counselor_sessions",
        sa.Column("cancelled_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "counselor_sessions",
        sa.Column("cancelled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "counselor_sessions",
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
    )
    op.create_foreign_key(
        "fk_sessions_booked_by",
        "counselor_sessions",
        "users",
        ["booked_by_user_id"],
        ["user_id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_sessions_cancelled_by",
        "counselor_sessions",
        "users",
        ["cancelled_by_user_id"],
        ["user_id"],
        ondelete="SET NULL",
    )

    # Backfill from the owning counselor's configured duration. Every existing
    # row predates configurable durations, so this resolves to 30 minutes --
    # but reading it from the column keeps the statement correct if a default
    # is ever changed before this migration runs somewhere new.
    op.execute(
        """
        UPDATE counselor_sessions cs
           SET ends_at = cs.scheduled_at
                       + make_interval(mins => cp.session_duration_minutes)
          FROM counselor_profiles cp
         WHERE cp.counselor_id = cs.counselor_id
           AND cs.ends_at IS NULL
        """
    )
    # Any session whose counselor row has since disappeared still needs an end.
    op.execute(
        """
        UPDATE counselor_sessions
           SET ends_at = scheduled_at + interval '30 minutes'
         WHERE ends_at IS NULL
        """
    )
    op.alter_column("counselor_sessions", "ends_at", nullable=False)

    op.create_check_constraint(
        "ck_session_ends_after_start",
        "counselor_sessions",
        "ends_at > scheduled_at",
    )

    # --- the overlap guard -------------------------------------------
    #
    # An EXCLUDE constraint over tstzrange is the correct tool: it makes the
    # database refuse a second live session that intersects an existing one,
    # regardless of which application path inserts it or how many processes
    # race. It needs btree_gist for the equality half of the key.
    #
    # Some managed Postgres hosts restrict CREATE EXTENSION. Rather than fail
    # the deploy, fall back to a plain index and let the service layer's
    # row-lock path carry the guarantee -- correct, just less defence in depth.
    # The service checks for this constraint by name at runtime and says which
    # mode it is in, so the weaker mode can never pass unnoticed.
    exclusion_created = False
    try:
        with op.get_context().autocommit_block():
            op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        op.execute(
            f"""
            ALTER TABLE counselor_sessions
              ADD CONSTRAINT {EXCLUSION_CONSTRAINT}
              EXCLUDE USING gist (
                counselor_id WITH =,
                tstzrange(scheduled_at, ends_at, '[)') WITH &&
              )
              WHERE (status NOT IN {INACTIVE_STATUSES})
            """
        )
        exclusion_created = True
    except Exception as exc:  # noqa: BLE001 - the fallback is the whole point
        logger.warning(
            "Could not create the %s exclusion constraint (%s). Falling back to "
            "an index; overlap prevention then rests on the booking service's "
            "row lock. Grant btree_gist and re-run to restore the database-level "
            "guarantee.",
            EXCLUSION_CONSTRAINT,
            exc,
        )

    if not exclusion_created:
        op.create_index(
            "ix_sessions_counselor_range",
            "counselor_sessions",
            ["counselor_id", "scheduled_at", "ends_at"],
        )

    # --- counselor_schedules -----------------------------------------
    op.create_table(
        "counselor_schedules",
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("counselor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(timezone=False), nullable=False),
        sa.Column("end_time", sa.Time(timezone=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["counselor_id"], ["counselor_profiles.counselor_id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6", name="ck_schedule_day_of_week"
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name="ck_schedule_effective_range",
        ),
    )
    op.create_index(
        "ix_schedules_counselor_day", "counselor_schedules", ["counselor_id", "day_of_week"]
    )

    # --- counselor_schedule_exceptions -------------------------------
    op.create_table(
        "counselor_schedule_exceptions",
        sa.Column(
            "exception_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("counselor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exception_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(timezone=False), nullable=True),
        sa.Column("end_time", sa.Time(timezone=False), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["counselor_id"], ["counselor_profiles.counselor_id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "(start_time IS NULL AND end_time IS NULL) "
            "OR (start_time IS NOT NULL AND end_time IS NOT NULL)",
            name="ck_exception_partial_window",
        ),
        sa.CheckConstraint(
            "is_available = false OR start_time IS NOT NULL",
            name="ck_exception_additional_needs_window",
        ),
    )
    op.create_index(
        "ix_exceptions_counselor_date",
        "counselor_schedule_exceptions",
        ["counselor_id", "exception_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_exceptions_counselor_date", table_name="counselor_schedule_exceptions")
    op.drop_table("counselor_schedule_exceptions")
    op.drop_index("ix_schedules_counselor_day", table_name="counselor_schedules")
    op.drop_table("counselor_schedules")

    # Whichever guard upgrade() managed to install.
    op.execute(
        f"ALTER TABLE counselor_sessions DROP CONSTRAINT IF EXISTS {EXCLUSION_CONSTRAINT}"
    )
    op.execute("DROP INDEX IF EXISTS ix_sessions_counselor_range")
    op.execute(
        "ALTER TABLE counselor_sessions DROP CONSTRAINT IF EXISTS ck_session_ends_after_start"
    )

    op.drop_constraint("fk_sessions_cancelled_by", "counselor_sessions", type_="foreignkey")
    op.drop_constraint("fk_sessions_booked_by", "counselor_sessions", type_="foreignkey")
    op.drop_column("counselor_sessions", "cancellation_reason")
    op.drop_column("counselor_sessions", "cancelled_by_user_id")
    op.drop_column("counselor_sessions", "cancelled_at")
    op.drop_column("counselor_sessions", "booked_by_user_id")
    op.drop_column("counselor_sessions", "ends_at")

    op.drop_column("counselor_profiles", "timezone")
    op.drop_column("counselor_profiles", "buffer_minutes")
    op.drop_column("counselor_profiles", "session_duration_minutes")

    # btree_gist is intentionally left installed: other things may rely on it,
    # and dropping an extension is not this migration's business.
