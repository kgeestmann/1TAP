from database.models import GuildConfig, ModLog
from database.schemas import GuildConfigModel
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


async def add_log(guild_id, action, user, moderator, reason=None) -> ModLog:
    async with async_session() as session:
        log = ModLog(
            guild_id=guild_id,
            action=action,
            user_id=getattr(user, "id", None),
            user_name=str(user) if user is not None else None,
            moderator_id=getattr(moderator, "id", None),
            moderator_name=str(moderator) if moderator is not None else None,
            reason=reason,
        )
        session.add(log)
        await session.commit()
        return log
