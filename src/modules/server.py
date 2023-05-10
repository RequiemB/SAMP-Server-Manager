import discord
from discord.ext import commands, tasks
from discord import app_commands

import asqlite
import traceback
import datetime
import trio_asyncio
import re

from helpers import (
    utils as _utils,
    config,
    status as _status
)

ip_regex = "^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.){3}(25[0-5]|(2[0-4]|1\d|[1-9]|)\d)$"

class Overwrite(discord.ui.View):
    def __init__(self, ip, port, data):
        super().__init__(timeout=60.0)
        self.message = None
        self.ip = ip
        self.port = port
        self.data = data

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
        try:
            if self.data[5] is not None and self.data[3] is not None:
                await self._status.start_status_with_guild(interaction.guild)
            else:
                server_channel = await _utils.format_command_mention_from_command(interaction.client, "server", "channel")
                server_interval = await _utils.format_command_mention_from_command(interaction.client, "server", "interval")
                if self.data[5] is None and self.data[3] is None:
                     e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command.\n:warning: You must set an interval to query server status using the {server_interval} command."
                elif self.data[5] is None:
                    e.description += f"\n\n:warning: You must set a channel to post server status in using the {command_mention} command."
                elif self.data[3] is None:
                    e.description += f"\n\n:warning: You must set an interval to query server status using the {server_interval} command."
        except:
            pass

        await interaction.response.send_message(embed=e)

        for button in self.children:
            button.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji=config.reactionFailure)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content="Successfully cancelled the configuration.")

        for button in self.children:
            button.disabled = True

        await self.message.edit(view=self)

class Server(commands.GroupCog, name='server', description="All the server commands lie under this group."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._status = self.bot._status
        self.ip = re.compile(ip_regex)

    async def cog_load(self):
        await _utils.set_up_database(self.bot)
        await self._status.start_status_global()
        self.auto_sync.start()

    @tasks.loop(count=1)
    async def auto_sync(self):
        await self.bot.tree.sync()
        self.bot.logger.info("Synced all application commands globally.")

    @auto_sync.before_loop
    async def before_auto_sync(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="get", description="Gets the information for the SA-MP server set in this guild.", extras={"cog": "Server"})
    async def server_get(self, interaction: discord.Interaction):
        await interaction.response.defer()
        query = f"SELECT * FROM query WHERE guild_id={interaction.guild.id}"
        conn, cursor = await _utils.execute_query(query)
        data = await cursor.fetchall()
        if len(data) == 0:
            command_mention = await _utils.format_command_mention_from_command(self.bot, "server", "set")
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
        e.add_field(name="IP Address", value=f"{ip}:{port}")
        e.add_field(name="Gamemode", value=info.gamemode)
        e.add_field(name="Players", value=f"{info.players}/{info.max_players}")
        e.add_field(name="Latency", value="{:.2f}ms".format(ping))
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

        if not re.search(self.ip, ip):
            e = discord.Embed(
                description = f"{config.reactionFailure} The IP: **{ip}** is not a valid IP address.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        query = f"SELECT * FROM query WHERE guild_id={interaction.guild.id}" 
        conn, cursor = await _utils.execute_query(query) 
        data = await cursor.fetchone() 
        if data is not None:
            is_server_set: bool = len(data) != 0
        else:
            is_server_set: bool = False
        await conn.close()
        if is_server_set:
            e = discord.Embed(
                description = f"{config.reactionFailure} An SA-MP server is already configured for this guild. Do you wish to overwrite?",
                color = discord.Color.red()
            )
            view = Overwrite(ip, port, data)
            await interaction.response.send_message(embed=e, view=view)
            view.message = await interaction.original_response()
        else:
            await _utils.update_server_for_guild(interaction.guild, ip, port)

            e = discord.Embed(
                description = f"{config.reactionSuccess} Successfully set the SA-MP server for this guild to **{ip}:{port}**.",
                color = discord.Color.green()
            )

            try:
                if self.data[5] is not None and self.data[3] is not None:
                    await self._status.start_status_with_guild(interaction.guild)
                else:
                    server_channel = await _utils.format_command_mention_from_command(interaction.client, "server", "channel")
                    server_interval = await _utils.format_command_mention_from_command(interaction.client, "server", "interval")
                    if self.data[5] is None and self.data[3] is None:
                         e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command.\n:warning: You must set an interval to query server status using the {server_interval} command."
                    elif self.data[5] is None:
                        e.description += f"\n\n:warning: You must set a channel to post server status in using the {command_mention} command."
                    elif self.data[3] is None:
                        e.description += f"\n\n:warning: You must set an interval to query server status using the {server_interval} command."
            except:
                pass

            await interaction.response.send_message(embed=e)

    @app_commands.command(name="channel", description="Sets the channel in which the bot updates the SA-MP server information.", extras={"cog": "Server"})
    @app_commands.describe(
        channel="The channel in which the bot should update the SA-MP server info.",
        interval="The interval at which the info should be sent. Must be higher than 30s and lower than 30m. Example Usage: 1s for 1 second, 1m for 1 minute."
    )
    async def server_channel(self, interaction: discord.Interaction, channel: discord.TextChannel, interval: str = None):
        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{config.reactionFailure} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        query = f"SELECT * FROM query where guild_id = {interaction.guild.id}"
        conn, cursor = await _utils.execute_query(query)
        data = await cursor.fetchone()
        if data is None:
            command_mention = await _utils.format_command_mention_from_command(interaction.client, "server", "set")

            e = discord.Embed(
                description = f"{config.reactionFailure} You must configure a SA-MP server for this guild using the {command_mention} command before setting a channel/an interval.",
                color = discord.Color.red()
            )

            await interaction.response.send_message(embed=e)

        duration: int
        fraction: str
        query: str
        
        if interval is not None:
            duration, fraction = _utils.format_time(interval)
            if duration == "" and fraction == "":
                e = discord.Embed(description = f"{config.reactionFailure} Invalid time format specified. Time must be passed as `1s` for a second or `1m` for a minute.", color = discord.Color.red())
                await interaction.response.send_message(embed=e)
                return
            elif duration == "error" and fraction == "":
                e = discord.Embed(description = f"{config.reactionFailure} Invalid time format specified. The minimum value is `30s` and the maximum value is `30m`.", color = discord.Color.red())
                await interaction.response.send_message(embed=e)
                return
            else:
                query = f"UPDATE query SET INTERVAL = {duration}, FRACTION = '{fraction}', channel_id = {channel.id} WHERE guild_id = {interaction.guild.id}"
        else:
            query = f"UPDATE query SET channel_id = {channel.id} WHERE guild_id = {interaction.guild.id}"

        assert query is not None

        conn, cursor = await _utils.execute_query(query)
        await conn.commit()

        if interval is not None or data[3] is not None:
            await self._status.start_status_with_guild(interaction.guild)

        e = discord.Embed(color = discord.Color.green())
        if interval is not None:
            e.description = f"{config.reactionSuccess} Successfully set the SA-MP server status channel to {channel.mention} and the interval to `{interval}`."
        else:
            command_mention = await _utils.format_command_mention_from_command(interaction.client, "server", "interval")
            e.description = f"{config.reactionSuccess} Successfully set the SA-MP server status channel to {channel.mention}. Use {command_mention} to set an interval."
        
        await conn.close()
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="interval", description="Sets the interval at which the info should be sent.", extras={"cog": "Server"})
    @app_commands.describe(
        interval="The interval at which the info should be sent. Must be higher than 30s and lower than 30m. Example Usage: 1s for 1 second, 1m for 1 minute."
    )
    async def server_interval(self, interaction: discord.Interaction, interval: str):
        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{config.reactionFailure} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        query = f"SELECT * FROM query where guild_id = {interaction.guild.id}"
        conn, cursor = await _utils.execute_query(query)
        data = await cursor.fetchone()
        if data is None:
            command_mention = await _utils.format_command_mention_from_command(interaction.client, "server", "set")

            e = discord.Embed(
                description = f"{config.reactionFailure} You must configure a SA-MP server for this guild using the {command_mention} command before setting an interval.",
                color = discord.Color.red()
            )

            await interaction.response.send_message(embed=e)
            return

        duration, fraction = _utils.format_time(interval)
        if duration == "" and fraction == "":
            e = discord.Embed(description = f"{config.reactionFailure} Invalid time format specified. Time must be passed as `1s` for a second or `1m` for a minute.", color = discord.Color.red())
            await interaction.response.send_message(embed=e)
            return
        elif duration == "error" and fraction == "":
            e = discord.Embed(description = f"{config.reactionFailure} Invalid time format specified. The minimum value is `30s` and the maximum value is `30m`.", color = discord.Color.red())
            await interaction.response.send_message(embed=e)
            return

        query = f"UPDATE query SET INTERVAL = {duration}, FRACTION = '{fraction}' WHERE guild_id = {interaction.guild.id}"
        await cursor.execute(query)

        await conn.commit()
        await conn.close()

        e = discord.Embed(
            description = f"{config.reactionSuccess} Successfully set the interval for this guild to `{interval}`.",
            color = discord.Color.green()
        )

        if data[5] is None:
            command_mention = await _utils.format_command_mention_from_command(interaction.client, "server", "channel")
            e.description += f"\n\n:warning: You must set a channel to send SA-MP server status using {command_mention}."
        else:
            await self._status.start_status_with_guild(interaction.guild)

        await interaction.response.send_message(embed=e)

async def setup(bot: commands.Bot):
    await bot.add_cog(Server(bot))