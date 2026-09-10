"""Refresh-token sessions, and the schema drift audit.

Two unrelated things that both had to happen before a pilot, kept in one
migration because splitting them would mean two deploys for one audit.

1. refresh_sessions
   Refresh tokens were stateless JWTs. Logging out deleted the client's copy
   and nothing else, so a token captured beforehand kept minting sessions
   until it expired -- days, on the shared school laptops this product is
   used from. The refresh token now names a row here; refreshing rotates it,
   logging out revokes it, and presenting a revoked one revokes its whole
   family on the assumption that it was stolen.

2. Nullable drift
   `alembic check` failed against models.py: roughly forty columns were
   declared NOT NULL in the models and created nullable back in migration
   001, so a fresh database built by create_all (which the test suite uses)
   did not match one built by the migration chain. Every affected column has
   a server default and was verified to contain zero NULLs before tightening.

   Not included, deliberately: four indexes autogenerate wanted to DROP
   (ix_audit_logs_created_at, ix_risk_assessments_assigned,
   ix_risk_assessments_verdict, ix_invite_code). They exist in the database
   and are used; the fix was to declare them in models.py, not to delete them.

Revision ID: 017_refresh_sessions_and_drift
Revises: 016_availability_engine
Create Date: 2026-09-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '017_refresh_sessions_and_drift'
down_revision: Union[str, None] = '016_availability_engine'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('refresh_sessions',
    sa.Column('session_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('family_id', sa.UUID(), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_reason', sa.String(length=40), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('session_id')
    )
    op.create_index('ix_refresh_sessions_family', 'refresh_sessions', ['family_id'], unique=False)
    op.create_index('ix_refresh_sessions_user', 'refresh_sessions', ['user_id'], unique=False)
    op.alter_column('ai_prompt_versions', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('true'))
    op.alter_column('analytics_snapshots', 'total_students',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('0'))
    op.alter_column('conversations', 'ai_generated_title',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('false'))
    op.alter_column('conversations', 'is_archived',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('false'))
    op.alter_column('conversations', 'total_messages',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('0'))
    op.alter_column('counselor_sessions', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'scheduled'::character varying"))
    op.alter_column('goals', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'active'::character varying"))
    op.alter_column('notifications', 'is_read',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('false'))
    op.alter_column('payment_transactions', 'currency',
               existing_type=sa.VARCHAR(length=10),
               nullable=False,
               existing_server_default=sa.text("'USD'::character varying"))
    op.alter_column('payment_transactions', 'payment_status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'pending'::character varying"))
    op.alter_column('school_settings', 'allow_parent_notifications',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('true'))
    op.alter_column('student_profiles', 'risk_level',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'green'::character varying"))
    op.alter_column('subscriptions', 'student_limit',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('100'))
    op.alter_column('subscriptions', 'active_students',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('0'))
    op.alter_column('subscriptions', 'billing_cycle',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'monthly'::character varying"))
    op.alter_column('subscriptions', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'active'::character varying"))
    op.alter_column('tenants', 'subscription_plan',
               existing_type=sa.VARCHAR(length=50),
               nullable=False,
               existing_server_default=sa.text("'free'::character varying"))
    op.alter_column('tenants', 'student_limit',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('100'))
    op.alter_column('tenants', 'active_students',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('0'))
    op.alter_column('tenants', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'active'::character varying"))
    op.alter_column('users', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('true'))


def downgrade() -> None:
    op.alter_column('users', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('true'))
    op.alter_column('tenants', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'active'::character varying"))
    op.alter_column('tenants', 'active_students',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=sa.text('0'))
    op.alter_column('tenants', 'student_limit',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=sa.text('100'))
    op.alter_column('tenants', 'subscription_plan',
               existing_type=sa.VARCHAR(length=50),
               nullable=True,
               existing_server_default=sa.text("'free'::character varying"))
    op.alter_column('subscriptions', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'active'::character varying"))
    op.alter_column('subscriptions', 'billing_cycle',
               existing_type=sa.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'monthly'::character varying"))
    op.alter_column('subscriptions', 'active_students',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=sa.text('0'))
    op.alter_column('subscriptions', 'student_limit',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=sa.text('100'))
    op.alter_column('student_profiles', 'risk_level',
               existing_type=sa.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'green'::character varying"))
    op.alter_column('school_settings', 'allow_parent_notifications',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('true'))
    op.alter_column('payment_transactions', 'payment_status',
               existing_type=sa.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'pending'::character varying"))
    op.alter_column('payment_transactions', 'currency',
               existing_type=sa.VARCHAR(length=10),
               nullable=True,
               existing_server_default=sa.text("'USD'::character varying"))
    op.alter_column('notifications', 'is_read',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('false'))
    op.alter_column('goals', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'active'::character varying"))
    op.alter_column('counselor_sessions', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'scheduled'::character varying"))
    op.alter_column('conversations', 'total_messages',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=sa.text('0'))
    op.alter_column('conversations', 'is_archived',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('false'))
    op.alter_column('conversations', 'ai_generated_title',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('false'))
    op.alter_column('analytics_snapshots', 'total_students',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=sa.text('0'))
    op.alter_column('ai_prompt_versions', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('true'))
    op.drop_index('ix_refresh_sessions_user', table_name='refresh_sessions')
    op.drop_index('ix_refresh_sessions_family', table_name='refresh_sessions')
    op.drop_table('refresh_sessions')
