import discord
from discord.ext import commands, tasks
from discord import app_commands

import re

from helpers import (
    utils as _utils,
    config,
    query
)
from typing import Literal

ip_regex = "^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.){3}(25[0-5]|(2[0-4]|1\d|[1-9]|)\d)$"

def get_emoji(_type: Literal['success', 'failure', 'timeout'] = 'success') -> str:
    if _type == 'success':
        return config.REACTION_SUCCESS if config.REACTION_SUCCESS else config.DEFAULT_REACTION_SUCCESS
    elif _type == 'timeout':
        return config.REACTION_TIMEOUT if config.REACTION_TIMEOUT else config.DEFAULT_REACTION_TIMEOUT
    else:
        return config.REACTION_FAILURE if config.REACTION_FAILURE else config.DEFAULT_REACTION_FAILURE

class Overwrite(discord.ui.View):
    def __init__(self, ip: str, port: int, data: dict) -> None:
        super().__init__(timeout=60.0)
        self.message: discord.Message = None
        self.ip = ip 
        self.port = port
        self.data = data
        self.done: bool = False

    async def on_timeout(self):
        if self.done:
            return 
        
        for button in self.children:
            button.disabled = True

        e = discord.Embed(
            description = f"{get_emoji('failure')} The command timed out. Run the command again to set a SA-MP server for this guild.",
            color = discord.Color.red()
        )
        await self.message.edit(embed=e, view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji=get_emoji())
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with interaction.client.pool.acquire() as conn:
            await conn.execute("UPDATE query SET ip = ?, port = ? WHERE guild_id = ?", (self.ip, self.port, interaction.guild.id,))
            await conn.commit()

        e = discord.Embed(
            description = f"{get_emoji()} Successfully set the SA-MP server for this guild to **{self.ip}:{self.port}**.",
            color = discord.Color.green()
        )
        try:
            if self.data[4] is not None and self.data[3] is not None:
                await interaction.client._status.start_status_with_guild(interaction.guild)
            else:
                server_channel = _utils.command_mention_from_tree(interaction.client, "server", "channel")
                server_interval = _utils.command_mention_from_tree(interaction.client, "server", "interval")
                if self.data[4] is None and self.data[3] is None:
                     e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command.\n:warning: You must set an interval to query server status using the {server_interval} command."
                elif self.data[4] is None:
                    e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command."
                elif self.data[3] is None:
                    e.description += f"\n\n:warning: You must set an interval to query server status using the {server_interval} command."
        except:
            pass

        self.done = True
        await interaction.response.send_message(embed=e)

        for button in self.children:
            button.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji=get_emoji('failure'))
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content="Successfully cancelled the configuration.")

        for button in self.children:
            button.disabled = True

        self.done = True
        await self.message.edit(view=self)

class Server(commands.GroupCog, name='server', description="All the server commands lie under this group."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._status = self.bot._status
        self.ip = re.compile(ip_regex)
        self.query = self.bot.query

    async def cog_load(self):
        await _utils.set_up_database(self.bot)
        await self._status.start_status_global()
#        self.auto_sync.start()     If you want commands to be auto-synced, just remove the comment in this line.

    @tasks.loop(count=1)
    async def auto_sync(self):
        self.bot.command_list = await self.bot.tree.sync()
        self.bot.logger.info("Synced all application commands globally.")

    @auto_sync.before_loop
    async def before_auto_sync(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="get", description="Gets the information for the SA-MP server set in this guild.", extras={"cog": "Server"})
    async def server_get(self, interaction: discord.Interaction):
        await interaction.response.defer()

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT * FROM query WHERE guild_id = ?", (interaction.guild.id,))

        if res[1] is None: # IP
            command_mention = _utils.command_mention_from_tree(self.bot, 1, "server set") # The second argument specifies which group the command is in, 0 for RCON and 1 for Server.
            e = discord.Embed(
                description = f"{get_emoji('failure')} No SA-MP server has been configured for this guild. Ask a manager to set one using the {command_mention} command.",
                color = discord.Color.red()
            )
            await interaction.followup.send(embed=e)
            return

        ip = res[1]
        port = int(res[2])

        try:
            data = await self.query.get_server_data(ip, port)
        except query.ServerOffline:
            e = discord.Embed(description=f"{get_emoji('failure')} The server didn't respond after 3 attempts.", color=discord.Color.red())
            await interaction.followup.send(content=None, embed=e)
            return

        e = _utils.make_svinfo_embed(ip, port, data)
        
        await interaction.followup.send(embed=e)

    @app_commands.command(name="set", description="Sets a SA-MP server for this guild.", extras={"cog": "Server"})
    @app_commands.describe(
        ip="The IP address of the SA-MP server.",
        port="The port of the SA-MP server."
    )
    async def server_set(self, interaction: discord.Interaction, ip: str, port: int):
        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{get_emoji('failure')} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        if not re.search(self.ip, ip):
            e = discord.Embed(
                description = f"{get_emoji('failure')} The IP: **{ip}** is not a valid IP address.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT * FROM query WHERE guild_id = ?", (interaction.guild.id,))

        is_server_set: bool = res[1] is not None # IP
        if is_server_set:
            e = discord.Embed(
                description = f"{get_emoji('failure')} An SA-MP server is already configured for this guild. Do you wish to overwrite?",
                color = discord.Color.red()
            )
            view = Overwrite(ip, port, res)
            await interaction.response.send_message(embed=e, view=view)
            view.message = await interaction.original_response()
        else:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("UPDATE query SET IP = ?, PORT = ? WHERE guild_id = ?", (ip, port, interaction.guild.id,))
                await conn.commit()

            e = discord.Embed(
                description = f"{get_emoji()} Successfully set the SA-MP server for this guild to **{ip}:{port}**.",
                color = discord.Color.green()
            )

            try:
                if res[4] is not None and res[3] is not None:
                    await self._status.start_status_with_guild(interaction.guild)
                else:
                    server_channel = await _utils.command_mention_from_tree(interaction.client, 1, "server channel")
                    server_interval = await _utils.command_mention_from_tree(interaction.client, 1, "server interval")
                    if res[4] is None and res[3] is None:
                         e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command.\n:warning: You must set an interval to query server status using the {server_interval} command."
                    elif res[4] is None:
                        e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command."
                    elif res[3] is None:
                        e.description += f"\n\n:warning: You must set an interval to query server status using the {server_interval} command."
            except:
                pass

            await interaction.response.send_message(embed=e)

    @app_commands.command(name="channel", description="Sets the channel in which the bot updates the SA-MP server information.", extras={"cog": "Server"})
    @app_commands.describe(
        channel="The channel in which the bot should update the SA-MP server info.",
        interval="The interval at which the info should be sent. Must be higher than 5m and lower than 30m. Example usage: 5m for 5 minutes, 25m for 25 minutes."
    )
    async def server_channel(self, interaction: discord.Interaction, channel: discord.TextChannel, interval: str = None):
        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{get_emoji('failure')} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return
        
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT * FROM query WHERE guild_id = ?", (interaction.guild.id,))

        if res[1] is None: # IP
            command_mention = _utils.command_mention_from_tree(interaction.client, 1, "server set")

            e = discord.Embed(
                description = f"{get_emoji('failure')} You must configure a SA-MP server for this guild using the {command_mention} command before setting a channel/an interval.",
                color = discord.Color.red()
            )

            await interaction.response.send_message(embed=e)
            return

        duration: int
        query: str
        
        if interval is not None:
            duration = _utils.format_time(interval)

            if duration == "": # Gave a value above 30m or below 5m
                e = discord.Embed(description = f"{get_emoji('failure')} Invalid time format specified. The minimum value is `5m` and the maximum value is `30m`.", color = discord.Color.red())
                await interaction.response.send_message(embed=e)
                return
            else:
                query, parameters = "UPDATE query SET interval = ?, channel_id = ? WHERE guild_id = ?", (duration, channel.id, interaction.guild.id,)
        else:
            query, parameters = "UPDATE query SET channel_id = ? WHERE guild_id = ?", (channel.id, interaction.guild.id,)

        assert query is not None

        async with self.bot.pool.acquire() as conn:
            await conn.execute(query, parameters)
            await conn.commit()
            
        if interval is not None or res[3] is not None:
            await self._status.start_status_with_guild(interaction.guild)

        e = discord.Embed(color = discord.Color.green())
        if interval is not None:
            e.description = f"{get_emoji()} Successfully set the SA-MP server status channel to {channel.mention} and the interval to `{interval}`."
        else:
            command_mention = _utils.command_mention_from_tree(interaction.client, 1, "server interval")
            e.description = f"{get_emoji()} Successfully set the SA-MP server status channel to {channel.mention}. Use {command_mention} to set an interval."
        
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="interval", description="Sets the interval at which the info should be sent.", extras={"cog": "Server"})
    @app_commands.describe(
        interval="The interval at which the info should be sent. Must be higher than 5m and lower than 30m. Example usage: 5m for 5 minutes, 25m for 25 minutes."
    )
    async def server_interval(self, interaction: discord.Interaction, interval: str):
        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{get_emoji('failure')} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return
        
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT * FROM query WHERE guild_id = ?", (interaction.guild.id,))

        if res[1] is None: # IP
            command_mention = _utils.command_mention_from_tree(interaction.client, 1, "server set")

            e = discord.Embed(
                description = f"{get_emoji('failure')} You must configure a SA-MP server for this guild using the {command_mention} command before setting an interval.",
                color = discord.Color.red()
            )

            await interaction.response.send_message(embed=e)
            return
        
        duration = _utils.format_time(interval)

        if duration == "":
            e = discord.Embed(description = f"{get_emoji('failure')} Invalid time format specified. The minimum value is `5m` and the maximum value is `30m`.", color = discord.Color.red())
            await interaction.response.send_message(embed=e)
            return

        async with self.bot.pool.acquire() as conn:
            await conn.execute("UPDATE query SET interval = ? WHERE guild_id = ?", (duration, interaction.guild.id,))
            await conn.commit()

        e = discord.Embed(
            description = f"{get_emoji()} Successfully set the interval for this guild to `{interval}`.",
            color = discord.Color.green()
        )

        if res[4] is None:
            command_mention = _utils.command_mention_from_tree(interaction.client, 1, "server channel")
            e.description += f"\n\n:warning: You must set a channel to send SA-MP server status using {command_mention}."
        else:
            await self._status.start_status_with_guild(interaction.guild)

        await interaction.response.send_message(embed=e)

async def setup(bot: commands.Bot):
    await bot.add_cog(Server(bot))