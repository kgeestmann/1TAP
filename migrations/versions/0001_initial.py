"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guild_config",
        sa.Column("guild_id", sa.BigInteger(), primary_key=True, autoincrement=False, nullable=False),
        sa.Column("log_channel_id", sa.BigInteger(), nullable=True),
        sa.Column("mute_mode", sa.String(), nullable=False),
        sa.Column("muted_role_id", sa.BigInteger(), nullable=True),
    )
    op.create_table(
        "mod_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("user_name", sa.String(), nullable=True),
        sa.Column("moderator_id", sa.BigInteger(), nullable=True),
        sa.Column("moderator_name", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mod_logs")
    op.drop_table("guild_config")
