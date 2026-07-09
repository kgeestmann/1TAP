import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UtcDateTime(TypeDecorator):
    """Stores naive UTC, always returns timezone-aware UTC.

    SQLite drops tzinfo, so without this, values read back are naive and can't be
    compared with aware datetimes. Normalising here keeps every datetime in the
    app aware-UTC, and stays correct on Postgres too.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class MuteMode(str, enum.Enum):
    TIMEOUT = "timeout"
    ROLE = "role"


class GuildConfig(Base):
    __tablename__ = "guild_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    log_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mute_mode: Mapped[str] = mapped_column(String, nullable=False, default=MuteMode.TIMEOUT.value)
    muted_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Action(Base):
    """A moderation action taken on a member (kick / mute / unmute / …).

    Keyed by guild for multi-server use; indexed on (guild_id, created_at) for
    per-guild history queries.
    """

    __tablename__ = "actions"
    __table_args__ = (Index("ix_actions_guild_created", "guild_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String, nullable=True)
    moderator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    moderator_name: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class Timer(Base):
    """A generic scheduled job that fires at ``expires_at``.

    The scheduler stores every future action here (auto-unmute, temp-ban
    expiry, reminders, …). ``event`` names the timer type; when it fires the
    scheduler dispatches ``on_<event>_timer_complete`` with the timer, and
    ``payload`` carries whatever the handler needs (e.g. guild/user/role IDs).
    """

    __tablename__ = "timers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String, nullable=False)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
