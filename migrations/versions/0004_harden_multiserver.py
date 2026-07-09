"""harden schema for multi-server: rename mod_logs -> actions, index, timers.guild_id

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # mod_logs -> actions: drop orphan rows, rename, tighten, index
    op.execute("DELETE FROM mod_logs WHERE guild_id IS NULL")
    op.rename_table("mod_logs", "actions")
    with op.batch_alter_table("actions") as batch:
        batch.alter_column("timestamp", new_column_name="created_at")
        batch.alter_column("guild_id", existing_type=sa.BigInteger(), nullable=False)
    op.create_index("ix_actions_guild_created", "actions", ["guild_id", "created_at"])

    # timers: add queryable guild_id (+ index) for per-guild cleanup
    with op.batch_alter_table("timers") as batch:
        batch.add_column(sa.Column("guild_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_timers_guild_id", "timers", ["guild_id"])


def downgrade() -> None:
    op.drop_index("ix_timers_guild_id", table_name="timers")
    with op.batch_alter_table("timers") as batch:
        batch.drop_column("guild_id")

    op.drop_index("ix_actions_guild_created", table_name="actions")
    with op.batch_alter_table("actions") as batch:
        batch.alter_column("guild_id", existing_type=sa.BigInteger(), nullable=True)
        batch.alter_column("created_at", new_column_name="timestamp")
    op.rename_table("actions", "mod_logs")
