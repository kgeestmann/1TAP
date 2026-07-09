import discord
from discord import app_commands
from discord.ext import commands

from database import repository

EMBED_COLOR = 0xA61AF9


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Slash-command group: /config ...  (only usable by members with Manage Server)
    config = app_commands.Group(
        name="config",
        description="Configure the bot for this server",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    @config.command(name="show", description="Show the current server configuration")
    async def show(self, interaction: discord.Interaction):
        cfg = await repository.get_config(interaction.guild_id)
        log_ch = f"<#{cfg.log_channel_id}>" if cfg.log_channel_id else "*not set*"
        role = f"<@&{cfg.muted_role_id}>" if cfg.muted_role_id else "*not set*"
        embed = discord.Embed(title="Server configuration", color=EMBED_COLOR)
        embed.add_field(name="Mod-log channel", value=log_ch, inline=False)
        embed.add_field(name="Mute mode", value=f"`{cfg.mute_mode.value}`", inline=False)
        embed.add_field(name="Muted role", value=role, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @config.command(name="logchannel", description="Set the channel where moderation actions are logged")
    @app_commands.describe(channel="The text channel to send mod logs to")
    async def logchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await repository.set_config(interaction.guild_id, log_channel_id=channel.id)
        await interaction.response.send_message(
            f"Mod-log channel set to {channel.mention}.", ephemeral=True
        )

    @config.command(name="mutemode", description="Choose how muting works on this server")
    @app_commands.describe(mode="timeout = native Discord timeout; role = assign a muted role")
    @app_commands.choices(mode=[
        app_commands.Choice(name="timeout (native)", value="timeout"),
        app_commands.Choice(name="role (muted role)", value="role"),
    ])
    async def mutemode(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await repository.set_config(interaction.guild_id, mute_mode=mode.value)
        note = ""
        if mode.value == "role":
            cfg = await repository.get_config(interaction.guild_id)
            if not cfg.muted_role_id:
                note = " No muted role is set yet — run `/config setupmuterole` or `/config muterole`."
        await interaction.response.send_message(
            f"Mute mode set to **{mode.value}**.{note}", ephemeral=True
        )

    @config.command(name="muterole", description="Use an existing role as the muted role")
    @app_commands.describe(role="The role to assign when muting (role mode)")
    async def muterole(self, interaction: discord.Interaction, role: discord.Role):
        await repository.set_config(interaction.guild_id, muted_role_id=role.id)
        await interaction.response.send_message(
            f"Muted role set to {role.mention}.", ephemeral=True
        )

    @config.command(name="setupmuterole",
                    description="Create a Muted role and deny it messaging in every channel")
    async def setupmuterole(self, interaction: discord.Interaction):
        guild = interaction.guild
        me = guild.me
        if not (me.guild_permissions.manage_roles and me.guild_permissions.manage_channels):
            await interaction.response.send_message(
                "I need the **Manage Roles** and **Manage Channels** permissions to do that.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # Reuse an existing configured/"Muted" role if there is one
        cfg = await repository.get_config(guild.id)
        role = guild.get_role(cfg.muted_role_id) if cfg.muted_role_id else None
        if role is None:
            role = discord.utils.get(guild.roles, name="Muted")
        if role is None:
            try:
                role = await guild.create_role(name="Muted", reason="Muted role for moderation")
            except discord.HTTPException:
                await interaction.followup.send("I couldn't create the Muted role.", ephemeral=True)
                return

        failed = 0
        for channel in guild.channels:
            try:
                await channel.set_permissions(
                    role,
                    send_messages=False,
                    send_messages_in_threads=False,
                    create_public_threads=False,
                    create_private_threads=False,
                    add_reactions=False,
                    speak=False,
                    reason="Configure muted role",
                )
            except discord.HTTPException:
                failed += 1

        await repository.set_config(guild.id, muted_role_id=role.id, mute_mode="role")
        message = f"Muted role {role.mention} is ready and mute mode set to **role**."
        if failed:
            message += f" (Couldn't update {failed} channel(s) — check my permissions there.)"
        await interaction.followup.send(message, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Config(bot))
