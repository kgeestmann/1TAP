from pydantic import BaseModel, ConfigDict

from database.models import MuteMode


class GuildConfigModel(BaseModel):
    """Validated, typed view of a guild's configuration (with sane defaults)."""

    model_config = ConfigDict(from_attributes=True)

    log_channel_id: int | None = None
    mute_mode: MuteMode = MuteMode.TIMEOUT
    muted_role_id: int | None = None
