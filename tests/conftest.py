from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from modules import moderation
from modules.moderation import Moderation
from tests.helpers import GUILD_ID, ROLE_ID, USER_ID


@pytest.fixture
def role():
    return MagicMock(spec=discord.Role, id=ROLE_ID)


@pytest.fixture
def member(role):
    member = MagicMock(id=USER_ID, roles=[role])
    member.remove_roles = AsyncMock()
    member.timeout = AsyncMock()
    member.is_timed_out.return_value = False
    return member


@pytest.fixture
def guild(member, role):
    guild = MagicMock(id=GUILD_ID)
    guild.get_member.side_effect = lambda user_id: member if user_id == USER_ID else None
    guild.get_role.side_effect = lambda role_id: role if role_id == ROLE_ID else None
    return guild


@pytest.fixture
def scheduler():
    return MagicMock(create_timer=AsyncMock(), cancel_timer=AsyncMock())


@pytest.fixture
def cog(guild, scheduler, monkeypatch):
    bot = MagicMock()
    bot.get_guild.side_effect = lambda guild_id: guild if guild_id == GUILD_ID else None
    bot.get_cog.return_value = scheduler
    cog = Moderation(bot)
    cog._log_to_channel = AsyncMock()
    monkeypatch.setattr(moderation.repository, "add_log", AsyncMock())
    return cog
