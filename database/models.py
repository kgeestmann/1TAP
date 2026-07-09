import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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


class ModLog(Base):
    __tablename__ = "mod_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String, nullable=True)
    moderator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    moderator_name: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
