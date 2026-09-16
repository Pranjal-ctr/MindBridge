"""AI runtime configuration, usage telemetry, and seeded-route reclassification.

Three related changes that make the AI layer switchable at runtime.

1. ai_runtime_config
   One row (config_id pinned to 1 by a CHECK) holding the active platform
   provider/model and the fallback selection. Deliberately holds NO API keys:
   credentials stay environment-only, so they never enter a database backup.
   Absent this row, the application uses its environment defaults, which is
   what every existing deployment does today.

2. ai_usage_logs telemetry columns
   failure_category, fallback_used and request_id. Failures could previously
   only be grouped by parsing error_message, and a usage row could not be
   joined to the request that produced it.

3. Seeded per-feature routes are deactivated (is_active = false)
   This is the behavioural change to read carefully.

   ai_feature_routes has always supported per-feature overrides, and migration
   005 and 009 seeded five rows as *defaults*, not as decisions
   anybody made. With the platform runtime configuration now above them in the
   precedence chain, leaving those rows active would mean an admin switching
   the platform provider changed nothing at all: every feature would still be
   pinned by a row nobody remembers creating. That is the worst outcome of the
   three (a control that silently does nothing), so the seeded rows are
   deactivated here.

   Nothing is deleted. The rows, and the per-feature override capability, both
   remain: an admin can re-enable any of them deliberately, and the admin UI
   now labels which features are overridden versus using the platform default.

   One consequence worth stating plainly: memory_extraction and
   title_generation were seeded on gemini-2.5-flash-lite for cost, and after
   this they follow the platform model (gemini-2.5-flash) unless re-enabled.
   That is a small cost increase on two cheap, non-safety-critical features, in
   exchange for the platform switch meaning what it says. Re-enable those two
   rows if the cost matters more than the uniformity.

   Only the five feature names seeded by migrations 005 and 009 are touched,
   named explicitly in SEEDED_DEFAULT_FEATURES below. A per-feature override
   an operator created deliberately for some other feature is left active, and
   the downgrade restores exactly this set.

Revision ID: 019_ai_runtime_config
Revises: 018_audit_trail_hardening
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '019_ai_runtime_config'
down_revision: Union[str, None] = '018_audit_trail_hardening'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The feature routes seeded as defaults by migrations 005 and 009. Named
# explicitly so this migration cannot accidentally deactivate a per-feature
# override that an operator created on purpose.
SEEDED_DEFAULT_FEATURES = ", ".join(
    f"'{name}'"
    for name in (
        "comrade_chat",
        "memory_extraction",
        "title_generation",
        "risk_detection",
        "parent_insight",
    )
)


def upgrade() -> None:
    # --- 1. Platform runtime configuration ------------------------------
    op.create_table(
        'ai_runtime_config',
        sa.Column('config_id', sa.Integer(), nullable=False),
        sa.Column('primary_provider', sa.String(length=50), nullable=False),
        sa.Column('primary_model', sa.String(length=100), nullable=False),
        sa.Column('fallback_provider', sa.String(length=50), nullable=True),
        sa.Column('fallback_model', sa.String(length=100), nullable=True),
        sa.Column('fallback_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('config_id = 1', name='ck_ai_runtime_config_singleton'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('config_id'),
    )
    # Intentionally NOT seeded. No row means "use the environment defaults",
    # which is the correct state for every existing deployment: the row should
    # appear the first time an admin actually chooses something.

    # --- 2. Usage telemetry ---------------------------------------------
    op.add_column('ai_usage_logs', sa.Column('failure_category', sa.String(length=40), nullable=True))
    op.add_column('ai_usage_logs', sa.Column(
        'fallback_used', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('ai_usage_logs', sa.Column('request_id', sa.String(length=64), nullable=True))

    # --- 3. Reclassify the seeded defaults -------------------------------
    # Only the rows seeded by migrations 005 and 009 are touched, named
    # explicitly. A bookkeeping table would have been more general but would
    # have persisted as schema drift (`alembic check` fails on it), and being
    # explicit is better here anyway: a per-feature override an operator
    # created deliberately for some other feature is left alone, and the
    # downgrade restores exactly this set.
    op.execute(f"""
        UPDATE ai_feature_routes SET is_active = false
        WHERE feature_name IN ({SEEDED_DEFAULT_FEATURES})
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE ai_feature_routes SET is_active = true
        WHERE feature_name IN ({SEEDED_DEFAULT_FEATURES})
    """)

    op.drop_column('ai_usage_logs', 'request_id')
    op.drop_column('ai_usage_logs', 'fallback_used')
    op.drop_column('ai_usage_logs', 'failure_category')

    op.drop_table('ai_runtime_config')
