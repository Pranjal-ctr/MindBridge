"""Schema improvements — FK, updated_at, UNIQUE, JSONB metadata

Revision ID: 002_schema_improvements
Revises: 001_initial
Create Date: 2026-06-14

Changes:
1. FK: conversation_summaries.last_message_id -> messages.message_id
2. Add updated_at to memory_items + trigger
3. Add UNIQUE(prompt_name, prompt_version) to ai_prompt_versions
4. Add metadata JSONB column to messages
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision: str = "002_schema_improvements"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add metadata JSONB column to messages
    # ------------------------------------------------------------------
    op.add_column(
        "messages",
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb")),
    )

    # ------------------------------------------------------------------
    # 2. Add FK: conversation_summaries.last_message_id -> messages
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_conversation_summaries_last_message_id",
        "conversation_summaries",
        "messages",
        ["last_message_id"],
        ["message_id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # 3. Add updated_at to memory_items
    # ------------------------------------------------------------------
    op.add_column(
        "memory_items",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create updated_at trigger for memory_items
    op.execute("""
        CREATE TRIGGER update_memory_items_updated_at
            BEFORE UPDATE ON memory_items
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # ------------------------------------------------------------------
    # 4. Add UNIQUE(prompt_name, prompt_version) to ai_prompt_versions
    # ------------------------------------------------------------------
    op.create_unique_constraint(
        "uq_prompt_name_version",
        "ai_prompt_versions",
        ["prompt_name", "prompt_version"],
    )


def downgrade() -> None:
    # 4. Remove UNIQUE constraint
    op.drop_constraint("uq_prompt_name_version", "ai_prompt_versions", type_="unique")

    # 3. Remove updated_at + trigger from memory_items
    op.execute("DROP TRIGGER IF EXISTS update_memory_items_updated_at ON memory_items;")
    op.drop_column("memory_items", "updated_at")

    # 2. Remove FK on last_message_id
    op.drop_constraint(
        "fk_conversation_summaries_last_message_id",
        "conversation_summaries",
        type_="foreignkey",
    )

    # 1. Remove metadata column from messages
    op.drop_column("messages", "metadata")
