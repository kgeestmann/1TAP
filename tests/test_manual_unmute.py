from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from database.schemas import GuildConfigModel
from modules import moderation
from modules.moderation import UNMUTE_EVENT
from tests.helpers import GUILD_ID, ROLE_ID, USER_ID, make_http_error


@pytest.fixture(autouse=True)
def muted_role_configured(monkeypatch):
    monkeypatch.setattr(moderation.repository, "get_config",
                        AsyncMock(return_value=GuildConfigModel(muted_role_id=ROLE_ID)))
    monkeypatch.setattr(moderation, "check_hierarchy", lambda guild, author, target: None)


async def unmute(cog, guild, member):
    return await cog._apply_unmute(guild, MagicMock(), member, "appeal accepted")


def assert_timer_cancelled(scheduler):
    scheduler.cancel_timer.assert_awaited_once_with(UNMUTE_EVENT, guild_id=GUILD_ID, user_id=USER_ID)


async def test_removes_role_cancels_timer_and_logs(cog, guild, member, role, scheduler):
    message, error = await unmute(cog, guild, member)

    assert error is None
    assert "unmuted" in message
    member.remove_roles.assert_awaited_once()
    assert_timer_cancelled(scheduler)
    assert moderation.repository.add_log.await_args.args[1] == "unmute"


async def test_role_removal_failure_is_reported_and_keeps_timer(cog, guild, member, scheduler):
    member.remove_roles.side_effect = make_http_error(discord.Forbidden, 403)

    message, error = await unmute(cog, guild, member)

    assert message is None
    assert "couldn't remove the muted role" in error
    assert "missing permissions" in error
    assert "doesn't appear to be muted" not in error
    scheduler.cancel_timer.assert_not_awaited()
    moderation.repository.add_log.assert_not_awaited()
    cog._log_to_channel.assert_not_awaited()


async def test_timeout_failure_is_reported_alongside_what_was_cleared(cog, guild, member, scheduler):
    member.is_timed_out.return_value = True
    member.timeout.side_effect = make_http_error(discord.HTTPException, 500)

    message, error = await unmute(cog, guild, member)

    assert message is None
    assert "couldn't clear the timeout (Discord API error (500))" in error
    assert "Cleared: muted role" in error
    assert_timer_cancelled(scheduler)
    moderation.repository.add_log.assert_not_awaited()


async def test_not_muted_member_reports_nothing_to_do(cog, guild, member, scheduler):
    member.roles = []

    message, error = await unmute(cog, guild, member)

    assert message is None
    assert "doesn't appear to be muted" in error
    assert_timer_cancelled(scheduler)
