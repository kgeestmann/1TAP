import discord
from discord.ext import commands
from utils.logger import log_action

LOG_CHANNEL_ID = 1157410384471396372

# Prefix command: !kick
@commands.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    log_entry = log_action("kick", member, ctx.author, reason)
    await ctx.send(f"{member} has been kicked.")

    log_channel = ctx.bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"Kick logged: {log_entry}")

# Slash command: /kick
@commands.slash_command(name="kick", description="Kick a member")
@commands.has_permissions(kick_members=True)
async def kick_slash(ctx, member: discord.Member, reason: str = None):
    await member.kick(reason=reason)
    log_entry = log_action("kick", member, ctx.author, reason)
    await ctx.respond(f"{member} has been kicked.")

    log_channel = ctx.bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"Kick logged: {log_entry}")

def setup(bot):
    bot.add_command(kick)
    bot.add_application_command(kick_slash)
