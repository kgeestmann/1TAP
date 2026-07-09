import os

import discord
from discord import app_commands
from discord.ext import commands

from utils.logger import log_action

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "1157410384471396372"))


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Prefix command: !kick
    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        await member.kick(reason=reason)
        log_entry = log_action("kick", member, ctx.author, reason)
        await ctx.send(f"{member} has been kicked.")
        await self._log_to_channel(log_entry)

    # Slash command: /kick
    @app_commands.command(name="kick", description="Kick a member")
    @app_commands.describe(member="The member to kick", reason="Reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = None,
    ):
        await member.kick(reason=reason)
        log_entry = log_action("kick", member, interaction.user, reason)
        await interaction.response.send_message(f"{member} has been kicked.")
        await self._log_to_channel(log_entry)

    async def _log_to_channel(self, log_entry):
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"Kick logged: {log_entry}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
