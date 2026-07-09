from datetime import datetime

from sqlalchemy import delete, select

from database.models import Action, GuildConfig, Timer
from database.schemas import GuildConfigModel, TimerModel
from database.session import async_session

_ALLOWED_CONFIG_KEYS = {"log_channel_id", "mute_mode", "muted_role_id"}


async def get_config(guild_id: int) -> GuildConfigModel:
    async with async_session() as session:
        obj = await session.get(GuildConfig, guild_id)
        if obj is None:
            return GuildConfigModel()
        return GuildConfigModel.model_validate(obj)


async def set_config(guild_id: int, **fields) -> None:
    invalid = set(fields) - _ALLOWED_CONFIG_KEYS
    if invalid:
        raise ValueError(f"Invalid config keys: {invalid}")
    async with async_session() as session:
        obj = await session.get(GuildConfig, guild_id)
        if obj is None:
            obj = GuildConfig(guild_id=guild_id)
            session.add(obj)
        for key, value in fields.items():
            setattr(obj, key, value)
        await session.commit()


async def add_log(guild_id, action, user, moderator, reason=None) -> int:
    """Record a moderation action and return its row id."""
    async with async_session() as session:
        entry = Action(
            guild_id=guild_id,
            action=action,
            user_id=getattr(user, "id", None),
            user_name=str(user) if user is not None else None,
            moderator_id=getattr(moderator, "id", None),
            moderator_name=str(moderator) if moderator is not None else None,
            reason=reason,
        )
        session.add(entry)
        await session.commit()
        return entry.id


# ---- scheduled timers ----
async def create_timer(event: str, expires_at: datetime, payload: dict, created_at: datetime,
                       guild_id: int | None = None) -> TimerModel:
    async with async_session() as session:
        timer = Timer(
            event=event, guild_id=guild_id, expires_at=expires_at,
            created_at=created_at, payload=payload,
        )
        session.add(timer)
        await session.commit()
        await session.refresh(timer)
        return TimerModel.model_validate(timer)


async def get_next_timer(before: datetime) -> TimerModel | None:
    """The earliest timer due at or before `before` (past-due included), if any."""
    async with async_session() as session:
        timer = await session.scalar(
            select(Timer).where(Timer.expires_at <= before).order_by(Timer.expires_at.asc()).limit(1)
        )
        return TimerModel.model_validate(timer) if timer else None


async def get_timers_by_event(event: str) -> list[TimerModel]:
    async with async_session() as session:
        rows = await session.scalars(select(Timer).where(Timer.event == event))
        return [TimerModel.model_validate(row) for row in rows]


async def delete_timer(timer_id: int) -> None:
    async with async_session() as session:
        await session.execute(delete(Timer).where(Timer.id == timer_id))
        await session.commit()


async def delete_timers_by_guild(guild_id: int) -> int:
    """Remove all timers for a guild (e.g. when the bot leaves it)."""
    async with async_session() as session:
        result = await session.execute(delete(Timer).where(Timer.guild_id == guild_id))
        await session.commit()
        return result.rowcount or 0
