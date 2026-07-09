import discord
from discord import app_commands
from discord.ext import commands

HELP_COLOR = 0xA61AF9


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Prefix command: !ping
    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await ctx.send(f"Pong! Latency: {round(self.bot.latency * 1000)}ms")

    # Slash command: /ping
    @app_commands.command(name="ping", description="Check if the bot is responsive")
    async def ping_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"Pong! Latency: {round(self.bot.latency * 1000)}ms"
        )

    # Prefix command: !help
    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        await ctx.send(embed=self._help_embed())

    # Slash command: /help
    @app_commands.command(name="help", description="Show bot help information")
    async def help_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self._help_embed())

    @staticmethod
    def _help_embed() -> discord.Embed:
        embed = discord.Embed(
            title="Help", description="Available commands:", color=HELP_COLOR
        )
        embed.add_field(name="/ping or !ping", value="Check bot latency", inline=False)
        embed.add_field(name="/help or !help", value="Show this help message", inline=False)
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
