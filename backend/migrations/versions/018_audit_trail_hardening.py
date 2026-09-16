"""Audit trail: actor role, school scope, result, severity, correlation id.

The audit table has carried actor/action/target since migration 001, which is
enough to answer "what happened" but not "who were they acting as", "which
school does this belong to", "did it actually succeed", or "which request was
this". All four come up in the first minute of a real incident.

Columns added (all additive; nothing is dropped or renamed):

  actor_role  The actor's role at the time of the event, denormalised. A role
              change later must not rewrite what someone was permitted to do
              when they did it.
  tenant_id   School scope. Also denormalised, and deliberately *not* always
              the actor's own school: when a platform admin acts on a school,
              the event belongs to the school acted upon.
  result      success | failure. Backfilled to 'success' -- every row written
              before this migration was written after its action succeeded,
              because log_audit() was only ever called on the success path.
  severity    info | notice | warning | critical, for triage.
  request_id  Correlation id from app.observability, joining an audit row to
              the structured log lines and the Sentry event for that request.

Also installs an append-only trigger. The application has no code path that
updates or deletes an audit row; this makes that a property of the database
instead of a property of nobody having written the code yet. Safe because
user and tenant deletion in this codebase are both soft, so the ON DELETE SET
NULL on user_id never fires from the application path.

The same trigger is installed by an after_create hook in database/models.py,
so it also exists under create_all -- the test suite builds its schema from
the models, so a migration-only trigger would leave the append-only test
asserting against a table that has none.

Revision ID: 018_audit_trail_hardening
Revises: 017_refresh_sessions_and_drift
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '018_audit_trail_hardening'
down_revision: Union[str, None] = '017_refresh_sessions_and_drift'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# One statement per entry: asyncpg sends DDL as a prepared statement, which
# refuses multiple commands in a single execute.
APPEND_ONLY_DDL = (
    """
    CREATE OR REPLACE FUNCTION kio_audit_logs_append_only() RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'audit_logs is append-only: % is not permitted', TG_OP
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs",
    """
    CREATE TRIGGER audit_logs_append_only
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION kio_audit_logs_append_only()
    """,
    "DROP TRIGGER IF EXISTS audit_logs_no_truncate ON audit_logs",
    """
    CREATE TRIGGER audit_logs_no_truncate
        BEFORE TRUNCATE ON audit_logs
        FOR EACH STATEMENT EXECUTE FUNCTION kio_audit_logs_append_only()
    """,
)


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('actor_role', sa.String(length=50), nullable=True))
    op.add_column('audit_logs', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.add_column('audit_logs', sa.Column('request_id', sa.String(length=64), nullable=True))

    # server_default on the way in so the backfill of existing rows is the
    # same statement as the NOT NULL. Kept on the column afterwards: the
    # model has a Python-side default, and a row inserted by anything else
    # (a psql session during an incident) should still be well-formed.
    op.add_column('audit_logs', sa.Column(
        'result', sa.String(length=20), nullable=False, server_default='success'))
    op.add_column('audit_logs', sa.Column(
        'severity', sa.String(length=20), nullable=False, server_default='info'))

    op.create_foreign_key(
        'fk_audit_logs_tenant_id', 'audit_logs', 'tenants',
        ['tenant_id'], ['tenant_id'], ondelete='SET NULL',
    )

    op.create_index('ix_audit_logs_action_created', 'audit_logs', ['action', 'created_at'])
    op.create_index('ix_audit_logs_tenant_created', 'audit_logs', ['tenant_id', 'created_at'])
    op.create_index('ix_audit_logs_request_id', 'audit_logs', ['request_id'])

    for statement in APPEND_ONLY_DDL:
        op.execute(statement)


def downgrade() -> None:
    # Triggers before the function they call, or the DROP FUNCTION is refused
    # as still-depended-on. (Row triggers do not fire on DDL, so the column
    # drops below would succeed either way.)
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_truncate ON audit_logs")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS kio_audit_logs_append_only()")

    op.drop_index('ix_audit_logs_request_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_tenant_created', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action_created', table_name='audit_logs')
    op.drop_constraint('fk_audit_logs_tenant_id', 'audit_logs', type_='foreignkey')
    op.drop_column('audit_logs', 'severity')
    op.drop_column('audit_logs', 'result')
    op.drop_column('audit_logs', 'request_id')
    op.drop_column('audit_logs', 'tenant_id')
    op.drop_column('audit_logs', 'actor_role')
