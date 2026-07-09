import os
import asyncio
import logging
import itertools

import discord
from discord import app_commands
from discord.ext import commands, tasks

from settings import settings
from logging_config import setup_logging
from database.session import engine, run_migrations

logger = logging.getLogger("onetap")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Rotating statuses
statuses = itertools.cycle([
    discord.Game("Monitoring chat"),
    discord.Game("Type !help for commands"),
    discord.Activity(type=discord.ActivityType.watching, name="over the server"),
    discord.Activity(type=discord.ActivityType.listening, name="your commands"),
])


class OneTapBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        # Ensure the data directory exists, then apply migrations
        data_dir = os.path.dirname(settings.database_path)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        await asyncio.to_thread(run_migrations)  # alembic upgrade head (sync)

        # Load all module extensions
        for filename in os.listdir("./modules"):
            if filename.endswith(".py") and not filename.startswith("__"):
                extension = f"modules.{filename[:-3]}"
                try:
                    await self.load_extension(extension)
                    logger.info("Loaded extension: %s", extension)
                except Exception:
                    logger.exception("Failed to load extension %s", extension)

        # Register slash commands with Discord
        synced = await self.tree.sync()
        logger.info("Synced %d slash command(s)", len(synced))

        # Start background presence rotation
        self.rotate_status.start()

    async def close(self):
        await engine.dispose()
        await super().close()

    @tasks.loop(seconds=60)
    async def rotate_status(self):
        await self.change_presence(status=discord.Status.online, activity=next(statuses))

    @rotate_status.before_loop
    async def before_rotate_status(self):
        await self.wait_until_ready()


bot = OneTapBot()


@bot.event
async def on_ready():
    logger.info("%s connected to Discord", bot.user)
    logger.info("Ready and serving %d guild(s)", len(bot.guilds))


# Error handling for prefix (!) commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use `!help` to see available commands.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can only be used in a server.")
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send(f"Bad usage: {error}")
    else:
        logger.error("Unhandled command error in %s", ctx.command, exc_info=error)


# Error handling for slash (/) commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        message = "You don't have permission to use this command."
    elif isinstance(error, app_commands.NoPrivateMessage):
        message = "This command can only be used in a server."
    elif isinstance(error, app_commands.CheckFailure):
        message = "You can't use this command here."
    else:
        message = "Something went wrong running that command."
        logger.error("Unhandled app command error", exc_info=error)

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


# Run the bot
if __name__ == "__main__":
    setup_logging()
    if not settings.discord_bot_token:
        logger.error("DISCORD_BOT_TOKEN is not set — aborting startup.")
    else:
        # log_handler=None: we own logging config, don't let discord.py add its own
        bot.run(settings.discord_bot_token, log_handler=None)
