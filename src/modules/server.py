import discord
from discord.ext import commands
from discord import app_commands

import asqlite
import traceback

from helpers import (
    utils as _utils,
    config
)

class Overwrite(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, ip, port):
        super().__init__(timeout=60.0)
        self.message = None
        self.ip = ip
        self.port = port

    async def on_timeout(self):
        for button in self.children:
            button.disabled = True

        e = discord.Embed(
            description = f"{config.reactionFailure} The command timed out. Run the command again to set a SA-MP server for this guild.",
            color = discord.Color.red()
        )
        await self.message.edit(embed=e, view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji=config.reactionSuccess)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _utils.update_server_for_guild(interaction.guild, self.ip, self.port)

        e = discord.Embed(
            description = f"{config.reactionSuccess} Successfully set the SA-MP server for this guild to **{self.ip}:{self.port}**.",
            color = discord.Color.green()
        )
        await interaction.response.send_message(embed=e)
        for button in self.children:
            button.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji=config.reactionFailure)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.message.edit(content="Successfully cancelled the configuration.", view=None)

GUILD = discord.Object(id=980522617570213989)

@app_commands.guilds(GUILD)
class Server(commands.GroupCog, name='server', description="All the server commands lie under this group."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="get", description="Gets the information for the SA-MP server set in this guild.", extras={"cog": "Server"})
    async def server_get(self, interaction: discord.Interaction):
        await interaction.response.defer()
        query = f"SELECT * FROM query WHERE guild_id={interaction.guild.id}"
        conn, cursor = await _utils.execute_query(query)
        data = await cursor.fetchall()
        if len(data) == 0:
            command_mention = await _utils.format_command_mention_from_command(self.bot, "server", "set", GUILD)
            e = discord.Embed(
                description = f"{config.reactionFailure} No SA-MP server has been configured for this guild. Ask a manager to set one using the {command_mention} command.",
                color = discord.Color.red()
            )
            await interaction.followup.send(embed=e)
            return
        await conn.close()

        ip = data[0][1]
        port = int(data[0][2])
        ping, info = await _utils.get_server_info(ip, port)
        e = discord.Embed(
            title = info.name,
            description = f"Basic information of {info.name}:",
            color = discord.Color.blue(),
            timestamp = interaction.created_at
        )
        e.add_field(name="Gamemode", value=info.gamemode)
        e.add_field(name="Players", value=f"{info.players}/{info.max_players}")
        e.add_field(name="Latency", value=ping)
        e.add_field(name="Password", value=info.password)
        e.add_field(name="Language", value=info.language)
        await interaction.followup.send(embed=e)

    @app_commands.command(name="set", description="Sets a SA-MP server for this guild.", extras={"cog": "Server"})
    @app_commands.describe(
        ip="The IP address of the SA-MP server.",
        port="The port of the SA-MP server."
    )
    async def server_set(self, interaction: discord.Interaction, ip: str, port: int):
        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{config.reactionFailure} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        query = f"SELECT * FROM query WHERE guild_id={interaction.guild.id}" 
        conn, cursor = await _utils.execute_query(query) 
        data = await cursor.fetchall() 
        is_server_set: bool = len(data) != 0
        if is_server_set:
            e = discord.Embed(
                description = f"{config.reactionFailure} An SA-MP server is already configured for this guild. Do you wish to overwrite?",
                color = discord.Color.red()
            )
            view = Overwrite(interaction, ip, port)
            await interaction.response.send_message(embed=e, view=view)
            view.message = await interaction.original_message()
        else:
            await _utils.configure_server_for_guild(interaction.guild, ip, port)

            e = discord.Embed(
                description = f"{config.reactionSuccess} Successfully set the SA-MP server for this guild to **{ip}:{port}**.",
                color = discord.Color.green()
            )
            await interaction.followup.send(embed=e)

        await conn.close()

    @app_commands.command(name="interval", description="Sets the interval at which the info should be sent.", extras={"cog": "Server"})
    @app_commands.describe(
        interval="The interval at which the info should be sent. Must be higher than 30s and lower than 30m. Example Usage: 1s for 1 second, 1m for 1 minute."
    )
    async def server_interval(self, interaction: discord.Interaction, interval: str):
        ...

async def setup(bot: commands.Bot):
    await bot.add_cog(Server(bot))