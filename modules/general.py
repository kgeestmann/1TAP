import discord
from discord.ext import commands

# Regular command: !ping
@commands.command(name="ping")
async def ping(ctx):
    await ctx.send(f"Pong! Latency: {round(ctx.bot.latency * 1000)}ms")

# Slash command: /ping
@commands.slash_command(name="ping", description="Check if the bot is responsive")
async def ping_slash(ctx):
    await ctx.respond(f"Pong! Latency: {round(ctx.bot.latency * 1000)}ms")

# Regular command: !help
@commands.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="Help", description="Available commands:", color=0xa61af9
    )
    embed.add_field(name="!ping", value="Check bot latency", inline=False)
    embed.add_field(name="!help", value="Show this help message", inline=False)
    await ctx.send(embed=embed)

# Slash command: /help
@commands.slash_command(name="help", description="Show bot help information")
async def help_slash(ctx):
    embed = discord.Embed(
        title="Help", description="Available commands:", color=0xa61af9
    )
    embed.add_field(name="/ping or !ping", value="Check bot latency", inline=False)
    embed.add_field(name="/help or !help", value="Show this help message", inline=False)
    await ctx.respond(embed=embed)

def setup(bot):
    bot.add_command(ping)
    bot.add_application_command(ping_slash)
    bot.add_command(help_command)
    bot.add_application_command(help_slash)