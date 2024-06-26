from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

import traceback
import asyncio
import pytz
import random

from helpers import (
    utils as _utils,
    ServerOffline,
    Mode
)
from datetime import datetime
from typing import Optional, Union, List, Dict, TYPE_CHECKING
from functools import partial
from inspect import cleandoc

if TYPE_CHECKING:
    from sqlite3 import Row
    from bot import QueryBot
    from helpers.chart import ChartData
    from asqlite import ProxiedConnection

class Overwrite(discord.ui.View):
    def __init__(self, ip: str, port: int, data: Row, author: discord.Member) -> None:
        super().__init__(timeout=60.0)
        self.message: Optional[discord.Message] = None
        self.ip: str = ip 
        self.port: int = port
        self.data: Row = data
        self.author: discord.Member = author # Person who did the interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This is not your confirmation view.", ephemeral=True)
            return False
        
        return True

    async def on_timeout(self) -> None:
        for button in self.children:
            if isinstance(button, discord.ui.Button):
                button.disabled = True 

        e = discord.Embed(
            description = f"{_utils.get_result_emoji('failure')} The command timed out. Run the command again to set a SA-MP server for this guild.",
            color = discord.Color.red()
        )

        if self.message:
            await self.message.edit(embed=e, view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji=_utils.get_result_emoji())
    async def confirm(self, interaction: discord.Interaction[QueryBot], _button: discord.ui.Button) -> None:
        await interaction.response.defer()

        assert interaction.guild is not None # to avoid errors while type-checking

        async with interaction.client.pool.acquire() as conn:
            await conn.execute("UPDATE query SET ip = ?, port = ? WHERE guild_id = ?", (self.ip, self.port, interaction.guild.id,))
            await conn.execute("INSERT OR IGNORE INTO stats (ip, port) VALUES (?, ?)", (self.ip, self.port,))
            await conn.commit()

        e = discord.Embed(
            description = f"{_utils.get_result_emoji()} Successfully set the SA-MP server for this guild to **{self.ip}:{self.port}**.",
            color = discord.Color.green()
        )

        try:
            if self.data[3] is not None and self.data[2] is not None:
                await interaction.client._status.start_status_with_guild(interaction.guild)
            else:
                if e.description is not None:
                    server_channel = await interaction.client.tree.find_mention_for("server channel")
                    server_interval = await interaction.client.tree.find_mention_for("server interval")
                    if self.data[3] is None and self.data[2] is None:
                         e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command.\n:warning: You must set an interval to query server status using the {server_interval} command."
                    elif self.data[3] is None:
                        e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command."
                    elif self.data[2] is None:
                        e.description += f"\n\n:warning: You must set an interval to query server status using the {server_interval} command."
        except Exception:
            await interaction.client.log_error_via_webhook("server_set button confirm", traceback.format_exc(), extra=f"in guild ID {interaction.guild.id}")

        await interaction.client._status.start_stats_update_with_guild(interaction.guild)
        await interaction.followup.send(embed=e)

        for button in self.children:
            if isinstance(button, discord.ui.Button):
                button.disabled = True 
        
        self.stop()

        if self.message:
            await self.message.edit(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji=_utils.get_result_emoji('failure'))
    async def cancel(self, interaction: discord.Interaction[QueryBot], _button: discord.ui.Button) -> None:
        for button in self.children:
            if isinstance(button, discord.ui.Button):
                button.disabled = True 

        self.stop()

        if self.message:
            await self.message.edit(view=self)

        await interaction.response.send_message(content="Successfully cancelled the configuration.")

class ChartSelect(discord.ui.Select):
    def __init__(self, data: Dict[str, ChartData], *, disabled: bool = False) -> None:
        self.data = data
        super().__init__(
            placeholder = "Select a date",
            options = [
                discord.SelectOption(label = "-".join(k[5:].split("-")[::-1]), value = k, emoji = "🗓️", description = f"Chart for the day of {'-'.join(k.split('-')[::-1])}") 
                for i, k in enumerate(data.keys()) if i <= 24 
            ] if not disabled else [discord.SelectOption(label="Nothing")],
            row = 0,
            min_values = 1,
            max_values = 1,
            disabled = disabled
        )

    async def callback(self, interaction: discord.Interaction[QueryBot]) -> None:
        await interaction.response.edit_message(view=self.view)
        if interaction.guild:
            loop = asyncio.get_event_loop()
            func = partial(interaction.client.chart.make_chart_from_data, interaction.guild.id, self.values[0], self.data, Mode.MODE_DAY)
            chart = await loop.run_in_executor(None, func)

            await interaction.followup.send(file=chart) # type: ignore

class ChartModal(discord.ui.Modal):
    def __init__(self, data: Dict[str, ChartData]) -> None:
        self.data = data
        super().__init__(
            title = "Server Chart Made",
            timeout = 60.0
        )
        self.input = discord.ui.TextInput(label="Date", placeholder="The date (as in the embed) from which the chart should be made", min_length=10, max_length=10)
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction[QueryBot]) -> None:
        # Validate the date format
        try:
            test = self.input.value.split("-")
            if len(test) != 3: # There will be 3 items when dd-mm-yyyy gets split with '-' as the delimiter
                raise ValueError
        except ValueError:
            await interaction.response.send_message(embed=discord.Embed(description=f"{_utils.get_result_emoji('failure')} **{self.input.value}** is not in the `dd-mm-yyyy` format.", color=discord.Color.red()))
            return
        
        await interaction.response.send_message(embed=discord.Embed(description=f"{_utils.get_result_emoji('timeout')} Fetching the server chart of **{self.input.value}**...", color=discord.Color.blue()))
        # The date the user inputs will be in the form of 'dd-mm-yyyy'
        # We need to reverse it
        date = "-".join(self.input.value.split("-")[::-1])
        if interaction.guild:
            resp = await interaction.original_response()
            loop = asyncio.get_event_loop()
            func = partial(interaction.client.chart.make_chart_from_data, interaction.guild.id, date, self.data, Mode.MODE_DAY)
            try:
                chart = await loop.run_in_executor(None, func)
            except:
                e = discord.Embed(description=f"{_utils.get_result_emoji('failure')} Server chart for **{self.input.value}** was not found.", color=discord.Color.red())
                await resp.edit(embed=e)
            else:
                await resp.edit(embed=None, attachments=[chart])

class ChartView(discord.ui.View):
    def __init__(self, data: Dict[str, ChartData], month: str) -> None:
        super().__init__(timeout=180.0)
        self.data = data
        self.month = month
        self.message: Optional[discord.Message] = None
        if self.entire_chart.label:
            self.entire_chart.label = f"Chart for {month}"

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True

        if self.message:
            await self.message.edit(view=self)

    @discord.ui.button(label="placeholder", style=discord.ButtonStyle.gray, row=1)
    async def entire_chart(self, interaction: discord.Interaction[QueryBot], button: discord.ui.Button) -> None:
        if interaction.guild:
            loop = asyncio.get_event_loop()
            func = partial(interaction.client.chart.make_chart_from_data, interaction.guild.id, self.month, self.data)
            chart = await loop.run_in_executor(None, func)

            await interaction.response.send_message(file=chart) # type: ignore

    @discord.ui.button(label="Enter Date", style=discord.ButtonStyle.gray, row=1)
    async def enter_date(self, interaction: discord.Interaction[QueryBot], button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ChartModal(self.data))

class TimezoneOverwrite(discord.ui.View):
    def __init__(self, conn: ProxiedConnection, current_tz: str, new_tz: str) -> None:
        self.conn: ProxiedConnection = conn
        self.current_tz: str = current_tz
        self.new_tz: str = new_tz
        self.message: Optional[discord.Message] = None
        super().__init__(timeout=60.0)

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        if self.message:
            await self.message.edit(view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji=_utils.get_result_emoji())
    async def confirm(self, interaction: discord.Interaction[QueryBot], button: discord.ui.Button) -> None:
        assert interaction.guild

        try:
            task = interaction.client._status.update_stats_tasks[interaction.guild.id]
        except KeyError:
            pass
        else:
            if task.is_running():
                task.cancel()

        await self.conn.execute("DELETE FROM dailystats WHERE guild_id = ?", (interaction.guild.id))
        await self.conn.execute("UPDATE query SET timezone = ? WHERE guild_id = ?", (self.new_tz, interaction.guild.id))

        e = discord.Embed(
            description = f"{_utils.get_result_emoji()} Successfully changed timezone from **{self.current_tz}** to **{self.new_tz}**.",
            color = discord.Color.green()
        )
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        await interaction.response.send_message(embed=e)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji=_utils.get_result_emoji('failure'))
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("Successfully canceled the operation.")

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        if self.message:
            await self.message.edit(view=self)

class Server(commands.Cog):
    "Commands related to server status and more."
    def __init__(self, bot) -> None:
        self.bot: QueryBot = bot
        self._status = self.bot._status
        self.emoji = _utils.get_result_emoji()
        self.query = self.bot.query
        self.chart = self.bot.chart

    server = app_commands.Group(name="server", description="All the server commands lie under this group.", guild_only=True)
        
    @server.command(name="get", description="Queries the information from the server set in this guild and displays it in an embed.", extras={"cog": "Server"})
    async def server_get(self, interaction: discord.Interaction[QueryBot]) -> None:
        await interaction.response.defer()

        assert interaction.guild is not None

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT ip, port FROM query WHERE guild_id = ?", (interaction.guild.id,))

        if res[0] is None: # IP
            command_mention = await interaction.client.tree.find_mention_for("server set") # The second argument specifies which group the command is in, 0 for RCON and 1 for Server.
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} No SA-MP server has been configured for this guild. Ask a manager to set one using the {command_mention} command.",
                color = discord.Color.red()
            )
            await interaction.followup.send(embed=e)
            return

        ip = res[0]
        port = int(res[1])

        try:
            data = await self.query.get_server_data(ip, port)
        except ServerOffline:
            e = discord.Embed(description=f"{_utils.get_result_emoji('failure')} The server didn't respond after 3 attempts.", color=discord.Color.red())
            await interaction.followup.send(embed=e) 
            return
        
        self.bot.server_data[interaction.guild.id] = data

        e, view = _utils.make_svinfo_embed(data) 
        await interaction.followup.send(embed=e, view=view)

    @server.command(name="set", description="Configures a SA-MP/OMP game server for the guild.", extras={"cog": "Server", "ip": ['51.228.224.222:7777', '144.76.57.59:9863']})
    @app_commands.describe(
        ip="The IP address of the SA-MP server."
    )
    async def server_set(self, interaction: discord.Interaction[QueryBot], ip: str) -> None:
        assert type(interaction.user) == discord.Member and interaction.guild # to avoid type-hinting errors

        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        if not _utils.is_ip(ip):
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} The IP: **{ip}** is not a valid IP address.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT ip, port, interval, channel_id, timezone FROM query WHERE guild_id = ?", (interaction.guild.id,))

        try:
            host, port = ip.split(":")
        except ValueError:
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} The IP: **{ip}** is not a valid IP address.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        is_server_set: bool = res[0] is not None # IP
        if is_server_set:
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} An SA-MP server is already configured for this guild. Do you wish to overwrite?",
                color = discord.Color.red()
            )
            view = Overwrite(host, int(port), res, interaction.user)
            await interaction.response.send_message(embed=e, view=view)
            view.message = await interaction.original_response()
        else:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("UPDATE query SET ip = ?, port = ? WHERE guild_id = ?", (host, port, interaction.guild.id,))
                await conn.execute("INSERT OR IGNORE INTO stats (ip, port) VALUES (?, ?)", (host, port,))
                await conn.commit()

            e = discord.Embed(
                description = f"{_utils.get_result_emoji()} Successfully set the SA-MP server for this guild to **{ip}**.",
                color = discord.Color.green()
            )

            try:
                if res[3] is not None and res[2] is not None:
                    await self._status.start_status_with_guild(interaction.guild)
                else:
                    if e.description is not None:
                        server_channel = await interaction.client.tree.find_mention_for("server channel")
                        server_interval = await interaction.client.tree.find_mention_for("server interval")
                        if res[3] is None and res[2] is None:
                             e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command.\n:warning: You must set an interval to query server status using the {server_interval} command."
                        elif res[3] is None:
                            e.description += f"\n\n:warning: You must set a channel to post server status in using the {server_channel} command."
                        elif res[2] is None:
                            e.description += f"\n\n:warning: You must set an interval to query server status using the {server_interval} command."
            except Exception:
                traceback.print_exc()

            if res[4]: # res[4] = timezone
                await self._status.start_stats_update_with_guild(interaction.guild)

            await interaction.response.send_message(embed=e)

            try:
                data = await self.query.get_server_data(host, int(port))
            except ServerOffline:
                pass
            else:
                self.bot.server_data[interaction.guild.id] = data

    @server.command(name="channel", description="Sets the channel in which the bot updates the SA-MP server information.", extras={"cog": "Server", "interval": ["6m", "20m", "30m", "15m"]})
    @app_commands.describe(
        channel="The channel in which the bot should update the SA-MP server info.",
        interval="The interval at which the info should be sent. Must be higher than 5m and lower than 30m."
    )
    async def server_channel(self, interaction: discord.Interaction[QueryBot], channel: discord.TextChannel, interval: Optional[str] = None) -> None:
        assert type(interaction.user) == discord.Member and interaction.guild is not None
        
        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return
        
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT ip, port, channel_id, interval FROM query WHERE guild_id = ?", (interaction.guild.id,))

        if res[0] is None: # IP
            command_mention = await interaction.client.tree.find_mention_for("server set")

            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} You must configure a SA-MP server for this guild using the {command_mention} command before setting a channel/an interval.",
                color = discord.Color.red()
            )

            await interaction.response.send_message(embed=e)
            return
        
        query: str
        parameters: Union[tuple[int, int, int], tuple[int, int]]
        
        if interval is not None:
            duration = _utils.format_time(interval)

            if not duration: # Gave a value above 30m or below 5m
                e = discord.Embed(description = f"{_utils.get_result_emoji('failure')} Invalid time format specified. The minimum value is `5m` and the maximum value is `30m`.", color = discord.Color.red())
                await interaction.response.send_message(embed=e)
                return
            else:
                query, parameters = "UPDATE query SET interval = ?, channel_id = ? WHERE guild_id = ?", (duration, channel.id, interaction.guild.id,)
        else:
            query, parameters = "UPDATE query SET channel_id = ? WHERE guild_id = ?", (channel.id, interaction.guild.id,)

        async with self.bot.pool.acquire() as conn:
            await conn.execute(query, parameters)
            await conn.commit()
            
        if interval is not None or res[3] is not None:
            await self._status.start_status_with_guild(interaction.guild)

        e = discord.Embed(color = discord.Color.green())
        if interval is not None:
            e.description = f"{_utils.get_result_emoji()} Successfully set the SA-MP server status channel to {channel.mention} and the interval to `{interval}`."
        else:
            e.description = f"{_utils.get_result_emoji()} Successfully set the SA-MP server status channel to {channel.mention}."
        
        await interaction.response.send_message(embed=e)

    @server.command(name="interval", description="Sets the interval at which the info should be sent.", extras={"cog": "Server", "interval": ["6m", "20m", "30m", "15m"]})
    @app_commands.describe(
        interval="The interval at which the info should be sent. Must be higher than 5m and lower than 30m."
    )
    async def server_interval(self, interaction: discord.Interaction[QueryBot], interval: str) -> None:
        assert type(interaction.user) is discord.Member and interaction.guild is not None

        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return
        
        await interaction.response.defer()
        
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT ip, port, interval, channel_id FROM query WHERE guild_id = ?", (interaction.guild.id,))

        if res[0] is None: # IP
            command_mention = await interaction.client.tree.find_mention_for("server set")

            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} You must configure a SA-MP server for this guild using the {command_mention} command before getting the stats.",
                color = discord.Color.red()
            )

            await interaction.followup.send(embed=e)
            return
        
        duration = _utils.format_time(interval)

        if not duration:
            e = discord.Embed(description = f"{_utils.get_result_emoji('failure')} Invalid time format specified. The minimum value is `5m` and the maximum value is `30m`.", color = discord.Color.red())
            await interaction.followup.send(embed=e)
            return

        async with self.bot.pool.acquire() as conn:
            await conn.execute("UPDATE query SET interval = ? WHERE guild_id = ?", (duration, interaction.guild.id,))
            await conn.commit()

        e = discord.Embed(
            description = f"{_utils.get_result_emoji()} Successfully set the interval for this guild to `{interval}`.",
            color = discord.Color.green()
        )

        if res[3] is None and e.description is not None:
            command_mention = await interaction.client.tree.find_mention_for("server channel")
            e.description += f"\n\n:warning: You must set a channel to send SA-MP server status using {command_mention}."
        else:
            await self._status.start_status_with_guild(interaction.guild)

        await interaction.followup.send(embed=e)

    @server.command(name="stats", description="Shows the recorded stats of the server set.")
    async def server_stats(self, interaction: discord.Interaction[QueryBot]) -> None:
        assert type(interaction.user) == discord.Member and interaction.guild is not None

        await interaction.response.defer()
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT ip, port FROM query WHERE guild_id = ?", (interaction.guild.id,))

        ip, port = res[0], res[1]

        if ip is None:
            command_mention = await interaction.client.tree.find_mention_for("server set")

            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} You must configure a SA-MP server for this guild using the {command_mention} command before setting an interval.",
                color = discord.Color.red()
            )

            await interaction.followup.send(embed=e)
            return

        try:
            info = await self.query.get_server_info(ip, port)

            header = info.name
            current_players = info.players 
        except ServerOffline:
            try:
                header = self.bot.server_data[interaction.guild.id]["info"].name
            except KeyError:
                header = f"{ip}:{port}"
            current_players = "N/A"

        e = discord.Embed(
            title=f"Stats of {header}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        async with self.bot.pool.acquire() as conn:
            stats = await conn.fetchone("SELECT highest_playercount, peak_hour FROM stats WHERE ip = ? AND port = ?", (ip, port,))
            uptime_data = await conn.fetchall("SELECT status FROM dailystats WHERE ip = ? AND port = ?", (ip, port,))
        
            highest_playerc = stats[0] 
            peak_hour = stats[1]
    
            if not highest_playerc or (current_players != "N/A" and current_players > highest_playerc):
                peak_hour = _utils.get_peak_hour() if highest_playerc else None
                query, params = "UPDATE stats SET highest_playercount = ?, peak_hour = ? WHERE ip = ? AND port = ?", (current_players, peak_hour, ip, port,)
                await conn.execute(query, params)
                await conn.commit()

        uptime_percentage = _utils.calc_uptime(uptime_data)

        e.add_field(name="Highest Recorded Player Count", value=highest_playerc)
        e.add_field(name="Current Players Online", value=current_players)
        e.add_field(name="Recorded Peak Time", value=f"`{peak_hour}`", inline=False)
        e.add_field(name="Uptime Percentage", value=uptime_percentage, inline=True)

        await interaction.followup.send(embed=e)        

    @server.command(name="chart", description="Fetches the chart of the server activity based on the arguments passed.", extras={"month": ['January', 'March', 'November', 'August']})
    @app_commands.describe(month="The month from which the chart should be made. Leave it empty to get the data for this month. All month names are valid. E.g. January, March, November.")
    async def server_chart(self, interaction: discord.Interaction[QueryBot], month: Optional[str] = None) -> None:
        assert interaction.guild

        await interaction.response.defer()

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT ip, port FROM query WHERE guild_id = ?", (interaction.guild.id))

            ip, port = res[0], res[1]

            if not ip and not port:
                command_mention = await interaction.client.tree.find_mention_for("server set")

                e = discord.Embed(
                    description = f"{_utils.get_result_emoji('failure')} You must configure a SA-MP server for this guild using the {command_mention} command before fetching charts.",
                    color = discord.Color.red()
                )

                await interaction.followup.send(embed=e)
                return

            now = datetime.now()
            year_int = now.year

            if not month:
                month_int = now.month
                month = _utils.MONTHS[month_int-1]
            else:
                month_int = _utils.MONTHS.index(month) + 1

            if month_int < 10:
                month_int = f"0{month_int}"

            res = await conn.fetchall(f"SELECT playercount, date, time FROM dailystats WHERE guild_id = ? AND ip = ? AND port = ? AND date LIKE '{year_int}-{month_int}%'", (interaction.guild.id, ip, port,))  

            data = self.chart.chart_data_from_res(res) 
            if not data: # No entries
                e = discord.Embed(
                    description = f"{_utils.get_result_emoji('failure')} Charts for {month} were not found. If the month hasn't passed, try again a bit later.",
                    color = discord.Color.red()
                )
                await interaction.followup.send(embed=e)
                return
                
            copy = data.copy() # Make a copy of this dict to use to get logged days

            for day, chart_data in data.items():
                if not self.chart.can_chart_be_made(chart_data, Mode.MODE_DAY):
                    del copy[day] # Days from which charts cannot be made are removed

            e = discord.Embed(
                title = "Server Chart Maker",
                color = discord.Color.blue(),
                timestamp = datetime.now()
            )
            e.description = cleandoc(f"""
                You can use the drop-down menu to get the chart from a specific day. 
                                     
                :warning: Charts for days will only be available if there are more than 6 recorded time points available.
                                     
                Clicking on the **'Chart for {month}'** button will show you the graph of highest player count recorded in a day for the entire month of {month}.
                :warning: Charts for months will only be available if there are more than 6 recorded dates available.

                If the days logged below is not present in the drop-down, click on the **'Enter Date'** button and enter the date in the same format as seen in the list.
            """)
            logged_days = self.chart.get_logged_days(copy)
            if not self.bot.chart.can_chart_be_made(data, Mode.MODE_MONTH) and len(logged_days) == 0: 
                e = discord.Embed(
                    description = f"{_utils.get_result_emoji('failure')} Charts for {month} were not found. If the month hasn't passed, try again a bit later.",
                    color = discord.Color.red()
                )
                await interaction.followup.send(embed=e)
                return
            
            if len(logged_days) > 0:
                valid_days = "\n".join([f"* {day}" for day in logged_days]) # get_logged_days will only show dates which pass the `can_chart_be_made` check
            else:
                valid_days = f"No days in {month} has more than 6 timepoints recorded."
            e.add_field(name=f"Logged Days in {month}", value=valid_days)

            chart_view = ChartView(data, month)
            if len(logged_days) > 0:
                chart_view.add_item(ChartSelect(copy)) # Init select with the 'copy' instance of the actual data   
            else:
                chart_view.add_item(ChartSelect(copy, disabled=True))

            if not self.bot.chart.can_chart_be_made(data, Mode.MODE_MONTH):
                chart_view.entire_chart.disabled = True

            await interaction.followup.send(embed=e, view=chart_view)
            chart_view.message = await interaction.original_response()

    @server_chart.autocomplete("month")
    async def month_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        current_month = _utils.get_month_name(datetime.now().month)
        index = _utils.MONTHS.index(current_month)
        if not current:
            return [
                app_commands.Choice(name=month, value=month) for month in _utils.MONTHS[:index+1]
            ]
        else:
            return [
                app_commands.Choice(name=month, value=month) for month in _utils.MONTHS[:index+1] if month.lower() in current.lower()
            ]
        
    @app_commands.command(name="status", description="Gets the status of any SA-MP/OMP game server.", extras={"Cog": "Server", "ip": ['144.76.57.59:9863', '46.183.184.33:7778']})
    @app_commands.describe(ip="The IP address of the server.")
    async def status(self, interaction: discord.Interaction[QueryBot], ip: str) -> None:
        if not _utils.is_ip(ip):
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} The IP: **{ip}** is not a valid IP address.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        
        await interaction.response.send_message("Waiting for a response from the server...", ephemeral=True)

        addr = ip.split(":")

        try:
            data = await self.query.get_server_data(addr[0], int(addr[1]))
        except ServerOffline:
            e = discord.Embed(description=f"{_utils.get_result_emoji('failure')} The server didn't respond after 3 attempts.", color=discord.Color.red())
            await interaction.edit_original_response(content=None, embed=e)
            return
        
        e, view = _utils.make_svinfo_embed(data, server_stats=False)
        await interaction.edit_original_response(content=None, embed=e, view=view)

    @server.command(name="status", description="An alias to /server get. There is no difference in functionality.")
    async def server_status(self, interaction: discord.Interaction[QueryBot]) -> None:
        await interaction.response.defer()

        assert interaction.guild is not None

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT ip, port FROM query WHERE guild_id = ?", (interaction.guild.id,))

        if res[0] is None: # IP
            command_mention = await interaction.client.tree.find_mention_for("server set") 
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} No SA-MP server has been configured for this guild. Ask a manager to set one using the {command_mention} command.",
                color = discord.Color.red()
            )
            await interaction.followup.send(embed=e)
            return

        ip = res[0]
        port = int(res[1])

        try:
            data = await self.query.get_server_data(ip, port)
        except ServerOffline:
            e = discord.Embed(description=f"{_utils.get_result_emoji('failure')} The server didn't respond after 3 attempts.", color=discord.Color.red())
            await interaction.followup.send(embed=e) 
            return
        
        self.bot.server_data[interaction.guild.id] = data

        e, view = _utils.make_svinfo_embed(data) 
        await interaction.followup.send(embed=e, view=view)

    @server.command(name="timezone", description="Sets a timezone for the server. This is required for chart data collection.")
    @app_commands.describe(timezone="The timezone to use for the server. Write the continent name to get more accurate results.")
    async def server_timezone(self, interaction: discord.Interaction[QueryBot], *, timezone: str) -> None:
        assert interaction.guild and type(interaction.user) is discord.Member

        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return
        
        if timezone not in pytz.common_timezones:
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} **{timezone}** is not a recognized timezone.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e)
            return

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT ip, port, timezone FROM query WHERE guild_id = ?", (interaction.guild.id,))

            if res[2]:
                view = TimezoneOverwrite(conn, res[2], timezone)
                e = discord.Embed(
                    description = f"Are you sure you want to change the configured timezone for this server from **{res[2]}** to **{timezone}**.\n\n:warning: This will cause all chart data collected to be erased.",
                    color = discord.Color.red()
                )
                await interaction.response.send_message(embed=e, view=view)
                view.message = await interaction.original_response()
            else:
                await conn.execute("UPDATE query SET timezone = ? WHERE guild_id = ?", (timezone, interaction.guild.id))
                await conn.commit()

                e = discord.Embed(
                    description = f"{_utils.get_result_emoji()} Successfully set the timezone for this guild to **{timezone}**.",
                    color = discord.Color.green()
                )
                await interaction.response.send_message(embed=e)

                if res[0] and res[1]:
                    await interaction.client._status.start_stats_update_with_guild(interaction.guild)

    @server_timezone.autocomplete('timezone')
    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        timezones = pytz.common_timezones
        if not current:
            selected_timezones = random.choices(timezones, k=25)
            return [
                app_commands.Choice(name=tz, value=tz) for tz in selected_timezones
            ]
        else:
            choices = []
            for tz in timezones:
                if len(choices) == 25:
                    break

                if current.lower() in tz.lower():
                    choices.append(app_commands.Choice(name=tz, value=tz))

            return choices

async def setup(bot: QueryBot) -> None:
    await bot.add_cog(Server(bot))