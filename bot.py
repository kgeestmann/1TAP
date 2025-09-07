import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Rotating statuses
statuses = [
    discord.Game("Monitoring chat"),
    discord.Game("Type !help for commands"),
    discord.Activity(type=discord.ActivityType.watching, name="over the server"),
    discord.Activity(type=discord.ActivityType.listening, name="your commands")
]

async def change_status():
    await bot.wait_until_ready()
    while not bot.is_closed():
        for status in statuses:
            await bot.change_presence(status=discord.Status.online, activity=status)
            await asyncio.sleep(10)

bot.loop.create_task(change_status())

# Load modules
for filename in os.listdir("./modules"):
    if filename.endswith(".py") and not filename.startswith("__"):
        bot.load_extension(f"modules.{filename[:-3]}")

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    print(f"Bot is ready and serving {len(bot.guilds)} guild(s)")

# Error handling
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