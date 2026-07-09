import os
import asyncio
import itertools

import discord
from discord import app_commands
from discord.ext import commands, tasks

from settings import settings
from database.session import engine, run_migrations

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
                    print(f"Loaded extension: {extension}")
                except Exception as exc:
                    print(f"Failed to load {extension}: {exc}")

        # Register slash commands with Discord
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")

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
    print(f"{bot.user} has connected to Discord!")
    print(f"Bot is ready and serving {len(bot.guilds)} guild(s)")


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
        print(f"An error occurred: {error}")


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
        print(f"App command error: {error}")

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


# Run the bot
if __name__ == "__main__":
    if not settings.discord_bot_token:
        print("Error: DISCORD_BOT_TOKEN environment variable not set!")
    else:
        bot.run(settings.discord_bot_token)
