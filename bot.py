import os
import itertools

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

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
        # Load all module extensions (runs before the bot connects)
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


# Error handling for prefix commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use `!help` to see available commands.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        print(f"An error occurred: {error}")


# Run the bot
if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set!")
    else:
        bot.run(TOKEN)
