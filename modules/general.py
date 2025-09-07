import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx):
        await ctx.send(f"Pong! Latency: {round(self.bot.latency*1000)}ms")

    @commands.slash_command(name="ping", description="Check if the bot is responsive")
    async def ping_slash(self, ctx):
        await ctx.respond(f"Pong! Latency: {round(self.bot.latency*1000)}ms")

    @commands.command(name="help")
    async def help_command(self, ctx):
        embed = discord.Embed(title="Help", description="Available commands:", color=0xa61af9)
        embed.add_field(name="!ping", value="Check bot latency", inline=False)
        embed.add_field(name="!help", value="Show this help message", inline=False)
        await ctx.send(embed=embed)

    @commands.slash_command(name="help", description="Show bot help information")
    async def help_slash(self, ctx):
        embed = discord.Embed(title="Help", description="Available commands:", color=0xa61af9)
        embed.add_field(name="/ping or !ping", value="Check bot latency", inline=False)
        embed.add_field(name="/help or !help", value="Show this help message", inline=False)
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(General(bot))