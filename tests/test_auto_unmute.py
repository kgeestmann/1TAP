"""Auto-unmute handler: fired by the scheduler when a timed role-mute expires."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from modules import moderation
from modules.moderation import UNMUTE_EVENT, UNMUTE_MAX_ATTEMPTS, Moderation

GUILD_ID, USER_ID, ROLE_ID = 1, 2, 3


def make_http_error(cls, status):
    response = MagicMock(status=status, reason="error")
    return cls(response, "boom")


@pytest.fixture
def role():
    return MagicMock(spec=discord.Role, id=ROLE_ID)


@pytest.fixture
def member(role):
    member = MagicMock(id=USER_ID, roles=[role])
    member.remove_roles = AsyncMock()
    return member


@pytest.fixture
def guild(member, role):
    guild = MagicMock(id=GUILD_ID)
    guild.get_member.side_effect = lambda user_id: member if user_id == USER_ID else None
    guild.get_role.side_effect = lambda role_id: role if role_id == ROLE_ID else None
    return guild


@pytest.fixture
def scheduler():
    return MagicMock(create_timer=AsyncMock())


@pytest.fixture
def cog(guild, scheduler, monkeypatch):
    bot = MagicMock()
    bot.get_guild.side_effect = lambda guild_id: guild if guild_id == GUILD_ID else None
    bot.get_cog.return_value = scheduler
    cog = Moderation(bot)
    cog._log_to_channel = AsyncMock()
    monkeypatch.setattr(moderation.repository, "add_log", AsyncMock())
    return cog


def make_timer(**extra):
    payload = {"guild_id": GUILD_ID, "user_id": USER_ID, "role_id": ROLE_ID, **extra}
    return SimpleNamespace(payload=payload)


def logged_action(cog):
    """Title of the single embed posted to the mod-log channel."""
    cog._log_to_channel.assert_awaited_once()
    embed = cog._log_to_channel.await_args.args[1]
    return embed.title


async def test_removes_role_and_logs_unmute(cog, member, role, scheduler):
    await cog.on_unmute_timer_complete(make_timer())

    member.remove_roles.assert_awaited_once_with(role, reason="Mute duration expired")
    moderation.repository.add_log.assert_awaited_once()
    assert moderation.repository.add_log.await_args.args[1] == "unmute"
    assert logged_action(cog) == "Member unmuted"
    scheduler.create_timer.assert_not_awaited()


async def test_role_already_removed_logs_nothing(cog, member):
    member.roles = []

    await cog.on_unmute_timer_complete(make_timer())

    member.remove_roles.assert_not_awaited()
    moderation.repository.add_log.assert_not_awaited()
    cog._log_to_channel.assert_not_awaited()


async def test_member_left_server_does_nothing(cog, guild, member):
    guild.get_member.side_effect = None
    guild.get_member.return_value = None

    await cog.on_unmute_timer_complete(make_timer())

    member.remove_roles.assert_not_awaited()
    moderation.repository.add_log.assert_not_awaited()
    cog._log_to_channel.assert_not_awaited()


@pytest.mark.parametrize("error", [
    make_http_error(discord.Forbidden, 403),
    make_http_error(discord.HTTPException, 500),
])
async def test_failure_schedules_retry_without_logging_success(cog, member, scheduler, error):
    member.remove_roles.side_effect = error
    before = datetime.now(timezone.utc)

    await cog.on_unmute_timer_complete(make_timer())

    scheduler.create_timer.assert_awaited_once()
    event, expires_at, payload = scheduler.create_timer.await_args.args
    assert event == UNMUTE_EVENT
    assert expires_at >= before + moderation.UNMUTE_RETRY_DELAY
    assert payload == {"guild_id": GUILD_ID, "user_id": USER_ID, "role_id": ROLE_ID, "attempt": 2}
    assert scheduler.create_timer.await_args.kwargs == {"guild_id": GUILD_ID}
    moderation.repository.add_log.assert_not_awaited()
    cog._log_to_channel.assert_not_awaited()


async def test_retry_counts_up_from_previous_attempt(cog, member, scheduler):
    member.remove_roles.side_effect = make_http_error(discord.HTTPException, 503)

    await cog.on_unmute_timer_complete(make_timer(attempt=2))

    assert scheduler.create_timer.await_args.args[2]["attempt"] == 3


async def test_last_attempt_alerts_mod_log_instead_of_retrying(cog, member, scheduler):
    member.remove_roles.side_effect = make_http_error(discord.Forbidden, 403)

    await cog.on_unmute_timer_complete(make_timer(attempt=UNMUTE_MAX_ATTEMPTS))

    scheduler.create_timer.assert_not_awaited()
    moderation.repository.add_log.assert_not_awaited()
    assert logged_action(cog) == "Auto-unmute failed"
    embed = cog._log_to_channel.await_args.args[1]
    reason = next(field.value for field in embed.fields if field.name == "Reason")
    assert "missing permissions" in reason
    assert "manually" in reason
