import logging
import re
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from database import repository
from database.models import MuteMode

logger = logging.getLogger("onetap.moderation")

_DURATION_RE = re.compile(r"(\d+)\s*([smhd])", re.IGNORECASE)
_UNIT_NAMES = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
MAX_TIMEOUT = timedelta(days=28)
DEFAULT_TIMEOUT = timedelta(hours=1)
UNMUTE_EVENT = "unmute"  # scheduler event name for timed role-mute expiry
# The scheduler fires each timer at most once, so a failed auto-unmute is
# retried by scheduling a fresh timer; after the last attempt a human is told.
UNMUTE_MAX_ATTEMPTS = 3
UNMUTE_RETRY_DELAY = timedelta(minutes=10)

# (color, embed title) per action
_ACTION_STYLE = {
    "kicked": (0xE74C3C, "Member kicked"),
    "muted": (0xE67E22, "Member muted"),
    "unmuted": (0x2ECC71, "Member unmuted"),
    "unmute failed": (0x992D22, "Auto-unmute failed"),
}
NO_PING = discord.AllowedMentions.none()


def parse_duration(text: str) -> timedelta:
    matches = _DURATION_RE.findall(text or "")
    if not matches:
        raise ValueError("Invalid duration. Use something like `10m`, `2h`, `1d`, or `30s`.")
    kwargs: dict[str, int] = {}
    for value, unit in matches:
        name = _UNIT_NAMES[unit.lower()]
        kwargs[name] = kwargs.get(name, 0) + int(value)
    delta = timedelta(**kwargs)
    if delta <= timedelta(0):
        raise ValueError("Duration must be greater than zero.")
    return delta


def format_delta(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    parts = []
    for label, size in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        if total >= size:
            qty, total = divmod(total, size)
            parts.append(f"{qty}{label}")
    return " ".join(parts) or "0s"


def describe_api_error(error: discord.HTTPException, permission_hint: str) -> str:
    if isinstance(error, discord.Forbidden):
        return f"missing permissions — {permission_hint}"
    return f"Discord API error ({error.status})"


def describe_unmute_failure(error: discord.HTTPException) -> str:
    return describe_api_error(error, "the muted role is above my top role or I lack Manage Roles")


def describe_timeout_failure(error: discord.HTTPException) -> str:
    return describe_api_error(error, "I need Moderate Members and a role above theirs")


def partial_unmute_message(target, cleared: list[str], failures: list[str]) -> str:
    text = f"Couldn't fully unmute {user_label(target)}: {'; '.join(failures)}."
    if cleared:
        text += f" Cleared: {', '.join(cleared)}."
    return text


def audit_reason(moderator, reason) -> str:
    return f"{moderator} — {reason or 'No reason provided'}"


def user_label(user) -> str:
    """Display name for logs/replies — a username, never a ping."""
    return discord.utils.escape_markdown(str(user))


def announce(target, moderator, action: str, *, extra: str = "", reason: str | None = None) -> str:
    """Plain-text command reply. Usernames only (no mentions => no pings)."""
    text = f"{user_label(target)} was {action} by {user_label(moderator)}{extra}"
    if reason:
        text += f" (reason: {reason})"
    return text + "."


def build_log_embed(target, moderator, action: str, *,
                    duration: str | None = None, reason: str | None = None) -> discord.Embed:
    color, title = _ACTION_STYLE.get(action, (0x95A5A6, f"Member {action}"))
    embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
    avatar = getattr(target, "display_avatar", None)
    if avatar is not None:
        embed.set_thumbnail(url=avatar.url)
    embed.add_field(name="Member", value=f"{user_label(target)}\n`{target.id}`", inline=True)
    embed.add_field(name="Moderator", value=user_label(moderator), inline=True)
    if duration:
        embed.add_field(name="Duration", value=duration, inline=True)
    embed.add_field(name="Reason", value=reason or "—", inline=False)
    embed.set_footer(text=f"User ID: {target.id}")
    return embed


def check_hierarchy(guild, author, target) -> str | None:
    """Return an error string if `author` may not act on `target`, else None."""
    if target.id == author.id:
        return "You can't moderate yourself."
    if target.id == guild.me.id:
        return "I can't moderate myself."
    if target.id == guild.owner_id:
        return "You can't moderate the server owner."
    if author.id != guild.owner_id and author.top_role <= target.top_role:
        return "You can't moderate someone with a role equal to or higher than yours."
    if guild.me.top_role <= target.top_role:
        return "My highest role isn't above that member, so I can't act on them."
    return None


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def scheduler(self):
        return self.bot.get_cog("Scheduler")

    # ---- helpers ----
    async def _log_to_channel(self, guild, embed):
        cfg = await repository.get_config(guild.id)
        if not cfg.log_channel_id:
            return
        channel = guild.get_channel(cfg.log_channel_id)
        if channel:
            try:
                await channel.send(embed=embed, allowed_mentions=NO_PING)
            except discord.HTTPException:
                pass

    async def _apply_kick(self, guild, moderator, target, reason):
        """Returns (success_message, error_message); exactly one is non-None."""
        error = check_hierarchy(guild, moderator, target)
        if error:
            return None, error
        try:
            await target.kick(reason=audit_reason(moderator, reason))
        except discord.Forbidden:
            return None, "I don't have permission to kick that member."
        except discord.HTTPException:
            return None, "Something went wrong kicking that member."
        await repository.add_log(guild.id, "kick", target, moderator, reason)
        await self._log_to_channel(
            guild, build_log_embed(target, moderator, "kicked", reason=reason)
        )
        return announce(target, moderator, "kicked", reason=reason), None

    async def _apply_mute(self, guild, moderator, target, duration_text, reason):
        error = check_hierarchy(guild, moderator, target)
        if error:
            return None, error
        cfg = await repository.get_config(guild.id)

        if cfg.mute_mode == MuteMode.ROLE:
            role = guild.get_role(cfg.muted_role_id) if cfg.muted_role_id else None
            if role is None:
                return None, "No muted role is configured. An admin can run `/config setupmuterole` first."
            if role >= guild.me.top_role:
                return None, "The muted role is above my top role, so I can't assign it. Move my role higher."
            delta = None
            if duration_text:
                try:
                    delta = parse_duration(duration_text)
                except ValueError as exc:
                    return None, str(exc)
            try:
                await target.add_roles(role, reason=audit_reason(moderator, reason))
            except discord.Forbidden:
                return None, "I don't have permission to assign the muted role."
            except discord.HTTPException:
                return None, "Something went wrong assigning the muted role."
            # Cancel any previous timer, then schedule a new one if timed.
            if self.scheduler:
                await self.scheduler.cancel_timer(UNMUTE_EVENT, guild_id=guild.id, user_id=target.id)
                if delta:
                    await self.scheduler.create_timer(
                        UNMUTE_EVENT,
                        datetime.now(timezone.utc) + delta,
                        {"guild_id": guild.id, "user_id": target.id, "role_id": role.id},
                        guild_id=guild.id,
                    )
            return await self._finish_mute(guild, moderator, target, delta, reason)

        # timeout mode (Discord expires it natively)
        try:
            delta = parse_duration(duration_text) if duration_text else DEFAULT_TIMEOUT
        except ValueError as exc:
            return None, str(exc)
        if delta > MAX_TIMEOUT:
            return None, "Timeouts can be at most 28 days."
        try:
            await target.timeout(delta, reason=audit_reason(moderator, reason))
        except discord.Forbidden:
            return None, "I can't time out that member — I need Moderate Members and a high enough role."
        except discord.HTTPException:
            return None, "Something went wrong applying the timeout."
        return await self._finish_mute(guild, moderator, target, delta, reason)

    async def _finish_mute(self, guild, moderator, target, delta, reason):
        duration_display = format_delta(delta) if delta else None
        extra = f" for {duration_display}" if duration_display else ""
        await repository.add_log(guild.id, "mute", target, moderator, reason)
        await self._log_to_channel(
            guild, build_log_embed(target, moderator, "muted",
                                   duration=duration_display, reason=reason)
        )
        return announce(target, moderator, "muted", extra=extra, reason=reason), None

    async def _apply_unmute(self, guild, moderator, target, reason):
        error = check_hierarchy(guild, moderator, target)
        if error:
            return None, error
        cfg = await repository.get_config(guild.id)
        audit = audit_reason(moderator, reason)
        cleared, failures = [], []
        if target.is_timed_out():
            try:
                await target.timeout(None, reason=audit)
                cleared.append("timeout")
            except discord.HTTPException as exc:
                failures.append(f"couldn't clear the timeout ({describe_timeout_failure(exc)})")
        role = guild.get_role(cfg.muted_role_id) if cfg.muted_role_id else None
        role_still_assigned = False
        if role and role in target.roles:
            try:
                await target.remove_roles(role, reason=audit)
                cleared.append("muted role")
            except discord.HTTPException as exc:
                role_still_assigned = True
                failures.append(f"couldn't remove the muted role ({describe_unmute_failure(exc)})")
        # While the role is still on, keep any pending auto-unmute: it retries
        # and alerts the mod-log if it keeps failing.
        if self.scheduler and not role_still_assigned:
            await self.scheduler.cancel_timer(UNMUTE_EVENT, guild_id=guild.id, user_id=target.id)
        if failures:
            return None, partial_unmute_message(target, cleared, failures)
        if not cleared:
            return None, f"{user_label(target)} doesn't appear to be muted."
        await repository.add_log(guild.id, "unmute", target, moderator, reason)
        await self._log_to_channel(
            guild, build_log_embed(target, moderator, "unmuted", reason=reason)
        )
        return announce(target, moderator, "unmuted", reason=reason), None

    # ---- auto-unmute: fired by the Scheduler when a timed role-mute expires ----
    @commands.Cog.listener()
    async def on_unmute_timer_complete(self, timer):
        data = timer.payload
        guild = self.bot.get_guild(data["guild_id"])
        if guild is None:
            return
        member = guild.get_member(data["user_id"])
        if member is None:
            return  # left the server; Discord drops their roles anyway
        role = guild.get_role(data["role_id"])
        if role is None or role not in member.roles:
            logger.info("Auto-unmute for %s in guild %s: muted role already gone, nothing to do",
                        member.id, guild.id)
            return
        try:
            await member.remove_roles(role, reason="Mute duration expired")
        except discord.NotFound:
            logger.info("Auto-unmute for %s in guild %s: member or role no longer exists",
                        member.id, guild.id)
            return
        except discord.HTTPException as error:
            await self._handle_unmute_failure(guild, member, data, error)
            return
        await repository.add_log(guild.id, "unmute", member, self.bot.user, "duration expired")
        await self._log_to_channel(
            guild, build_log_embed(member, self.bot.user, "unmuted", reason="duration expired")
        )

    async def _handle_unmute_failure(self, guild, member, payload, error):
        """Retry a failed auto-unmute later, or alert the mod-log once out of attempts."""
        attempt = payload.get("attempt", 1)
        cause = describe_unmute_failure(error)
        if attempt < UNMUTE_MAX_ATTEMPTS and await self._schedule_unmute_retry(guild, member, payload, attempt):
            logger.warning("Auto-unmute attempt %d/%d for %s in guild %s failed (%s); retrying in %s",
                           attempt, UNMUTE_MAX_ATTEMPTS, member.id, guild.id, cause,
                           format_delta(UNMUTE_RETRY_DELAY))
            return
        logger.error("Auto-unmute for %s in guild %s gave up after %d attempt(s): %s",
                     member.id, guild.id, attempt, cause)
        await self._log_to_channel(
            guild, build_log_embed(member, self.bot.user, "unmute failed",
                                   reason=f"{cause}. Remove the muted role manually.")
        )

    async def _schedule_unmute_retry(self, guild, member, payload, attempt) -> bool:
        """Schedule the next auto-unmute attempt; False if it couldn't be scheduled."""
        if not self.scheduler:
            return False
        try:
            await self.scheduler.create_timer(
                UNMUTE_EVENT,
                datetime.now(timezone.utc) + UNMUTE_RETRY_DELAY,
                {**payload, "attempt": attempt + 1},
                guild_id=guild.id,
            )
        except Exception:
            # The original timer is already gone, so falling back to the
            # mod-log alert is the only way left to surface this.
            logger.exception("Could not schedule auto-unmute retry for %s in guild %s",
                             member.id, guild.id)
            return False
        return True

    # ---- kick ----
    @commands.command(name="kick")
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        message, error = await self._apply_kick(ctx.guild, ctx.author, member, reason)
        await ctx.send(error or message, allowed_mentions=NO_PING)

    @app_commands.command(name="kick", description="Kick a member")
    @app_commands.describe(member="The member to kick", reason="Reason for the kick")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        message, error = await self._apply_kick(interaction.guild, interaction.user, member, reason)
        await interaction.response.send_message(error or message, ephemeral=bool(error), allowed_mentions=NO_PING)

    # ---- mute ----
    @commands.command(name="mute")
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: str = None, *, reason: str = None):
        message, error = await self._apply_mute(ctx.guild, ctx.author, member, duration, reason)
        await ctx.send(error or message, allowed_mentions=NO_PING)

    @app_commands.command(name="mute", description="Mute a member (timeout or muted role, per server config)")
    @app_commands.describe(
        member="The member to mute",
        duration="e.g. 10m, 2h, 1d — timeout: default 1h; role: optional auto-unmute timer",
        reason="Reason for the mute",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute_slash(self, interaction: discord.Interaction, member: discord.Member,
                         duration: str = None, reason: str = None):
        message, error = await self._apply_mute(interaction.guild, interaction.user, member, duration, reason)
        await interaction.response.send_message(error or message, ephemeral=bool(error), allowed_mentions=NO_PING)

    # ---- unmute ----
    @commands.command(name="unmute")
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        message, error = await self._apply_unmute(ctx.guild, ctx.author, member, reason)
        await ctx.send(error or message, allowed_mentions=NO_PING)

    @app_commands.command(name="unmute", description="Unmute a member (clears timeout and/or muted role)")
    @app_commands.describe(member="The member to unmute", reason="Reason for the unmute")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        message, error = await self._apply_unmute(interaction.guild, interaction.user, member, reason)
        await interaction.response.send_message(error or message, ephemeral=bool(error), allowed_mentions=NO_PING)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
