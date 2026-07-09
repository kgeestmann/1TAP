import re
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from database import repository
from database.models import MuteMode

_DURATION_RE = re.compile(r"(\d+)\s*([smhd])", re.IGNORECASE)
_UNIT_NAMES = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
MAX_TIMEOUT = timedelta(days=28)
DEFAULT_TIMEOUT = timedelta(hours=1)


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


def audit_reason(moderator, reason) -> str:
    return f"{moderator} — {reason or 'No reason provided'}"


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

    # ---- helpers ----
    async def _log_to_channel(self, guild, text):
        cfg = await repository.get_config(guild.id)
        channel_id = cfg.log_channel_id
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(text)
            except discord.HTTPException:
                pass

    async def _apply_kick(self, guild, moderator, target, reason) -> str | None:
        error = check_hierarchy(guild, moderator, target)
        if error:
            return error
        try:
            await target.kick(reason=audit_reason(moderator, reason))
        except discord.Forbidden:
            return "I don't have permission to kick that member."
        except discord.HTTPException:
            return "Something went wrong kicking that member."
        await repository.add_log(guild.id, "kick", target, moderator, reason)
        await self._log_to_channel(
            guild, f"👢 **{target}** was kicked by {moderator}. Reason: {reason or 'N/A'}"
        )
        return None

    async def _apply_mute(self, guild, moderator, target, duration_text, reason):
        """Returns (success_message, error_message); exactly one is non-None."""
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
            try:
                await target.add_roles(role, reason=audit_reason(moderator, reason))
            except discord.Forbidden:
                return None, "I don't have permission to assign the muted role."
            except discord.HTTPException:
                return None, "Something went wrong assigning the muted role."
            await repository.add_log(guild.id, "mute", target, moderator, reason)
            await self._log_to_channel(
                guild, f"🔇 **{target}** was muted by {moderator}. Reason: {reason or 'N/A'}"
            )
            return f"{target.mention} has been muted.", None

        # timeout mode
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
        await repository.add_log(guild.id, "mute", target, moderator, reason)
        await self._log_to_channel(
            guild,
            f"🔇 **{target}** was timed out for {format_delta(delta)} by {moderator}. "
            f"Reason: {reason or 'N/A'}",
        )
        return f"{target.mention} has been muted for {format_delta(delta)}.", None

    async def _apply_unmute(self, guild, moderator, target, reason):
        error = check_hierarchy(guild, moderator, target)
        if error:
            return None, error
        cfg = await repository.get_config(guild.id)
        actions = []
        if target.is_timed_out():
            try:
                await target.timeout(None, reason=audit_reason(moderator, reason))
                actions.append("timeout")
            except discord.HTTPException:
                pass
        role = guild.get_role(cfg.muted_role_id) if cfg.muted_role_id else None
        if role and role in target.roles:
            try:
                await target.remove_roles(role, reason=audit_reason(moderator, reason))
                actions.append("muted role")
            except discord.HTTPException:
                pass
        if not actions:
            return None, f"{target} doesn't appear to be muted."
        await repository.add_log(guild.id, "unmute", target, moderator, reason)
        await self._log_to_channel(guild, f"🔊 **{target}** was unmuted by {moderator}.")
        return f"{target.mention} has been unmuted.", None

    # ---- kick ----
    @commands.command(name="kick")
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        error = await self._apply_kick(ctx.guild, ctx.author, member, reason)
        await ctx.send(error if error else f"{member} has been kicked.")

    @app_commands.command(name="kick", description="Kick a member")
    @app_commands.describe(member="The member to kick", reason="Reason for the kick")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        error = await self._apply_kick(interaction.guild, interaction.user, member, reason)
        await interaction.response.send_message(
            error if error else f"{member} has been kicked.", ephemeral=bool(error)
        )

    # ---- mute ----
    @commands.command(name="mute")
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: str = None, *, reason: str = None):
        message, error = await self._apply_mute(ctx.guild, ctx.author, member, duration, reason)
        await ctx.send(error or message)

    @app_commands.command(name="mute", description="Mute a member (timeout or muted role, per server config)")
    @app_commands.describe(
        member="The member to mute",
        duration="e.g. 10m, 2h, 1d — only used in timeout mode (default 1h)",
        reason="Reason for the mute",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute_slash(self, interaction: discord.Interaction, member: discord.Member,
                         duration: str = None, reason: str = None):
        message, error = await self._apply_mute(interaction.guild, interaction.user, member, duration, reason)
        await interaction.response.send_message(error or message, ephemeral=bool(error))

    # ---- unmute ----
    @commands.command(name="unmute")
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        message, error = await self._apply_unmute(ctx.guild, ctx.author, member, reason)
        await ctx.send(error or message)

    @app_commands.command(name="unmute", description="Unmute a member (clears timeout and/or muted role)")
    @app_commands.describe(member="The member to unmute", reason="Reason for the unmute")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        message, error = await self._apply_unmute(interaction.guild, interaction.user, member, reason)
        await interaction.response.send_message(error or message, ephemeral=bool(error))


async def setup(bot):
    await bot.add_cog(Moderation(bot))
