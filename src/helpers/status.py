import discord
from discord.ext import tasks

import datetime

from helpers import (
    utils as _utils,
    config
)
from .query import ServerOffline

class Status:
    def __init__(self, bot):
        self.bot = bot
        self.status_messages = {} 
        self.tasks = {}
        self.query = bot.query

    async def _get_status(self, host, port, channel_id, guild_id):
        channel = self.bot.get_channel(channel_id)

        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)

        try:
            data = await self.query.get_server_data(host, port)
        except ServerOffline:
            e = discord.Embed(
                description = f"{config.reactionFailure} The server didn't respond after 3 attempts.",
                color=discord.Color.red()
            )
            await channel.send(embed=e)
            return

        info = data["info"]

        try:
            if self.status_messages[guild_id] is not None:
                message = self.status_messages[guild_id]
                await message.delete()
        except:
            pass

        e = discord.Embed(
            title = info.name,
            description = f"Basic information of {info.name}:",
            color = discord.Color.blue(),
            timestamp = datetime.datetime.now()
        )

        player_list = f"{'#': <2}{'Name': ^32}{'Score': >4}\n"

        for i, player in enumerate(data["players"].players):
            player_list += f"{i: <2}{player.name: ^32}{player.score: >4}\n"

        e.add_field(name="IP Address", value=f"{host}:{port}")
        e.add_field(name="Gamemode", value=info.gamemode)
        e.add_field(name="Players", value=f"{info.players}/{info.max_players}")
        e.add_field(name="Latency", value=f"{data['ping'] * 1000:.0f}ms")
        e.add_field(name="Language", value=info.language)
        e.add_field(name="Players", value=f"```{player_list}```", inline=False)
        
        message = await channel.send(embed=e)
        self.status_messages[guild_id] = message
    
    def retrieve_config_from_data(self, data):
        guild_id = data[0]
        ip = None
        port = None
        interval = None
        channel_id = None

        if data[1] is not None:
            ip = data[1]
        
        if data[2] is not None:
            port = int(data[2])

        if data[3] is not None:
            interval, _ = _utils.format_time(data[3])

        if data[4] is not None:
            channel_id = int(data[4])

        return guild_id, ip, port, interval, channel_id

    async def start_status_global(self):

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchall("SELECT * FROM query")

        for index in res:
            
            guild_id, ip, port, interval, channel_id = self.retrieve_config_from_data(index)

            @tasks.loop(seconds=10.0, reconnect=True)
            async def get_status(ip, port, channel_id, guild_id):
                await self._get_status(ip, port, channel_id, guild_id)

            @get_status.before_loop
            async def before_get_status():
                await self.bot.wait_until_ready()

            if (ip is not None and port is not None and interval is not None and channel_id is not None):
                self.tasks[guild_id] = get_status
                self.tasks[guild_id].change_interval(seconds=interval)
                self.tasks[guild_id].start(ip, port, channel_id, guild_id)
                
    async def start_status_with_guild(self, guild):

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT * FROM query WHERE guild_id = ?", (guild.id,))

        guild_id, ip, port, interval, channel_id = self.retrieve_config_from_data(res)

        @tasks.loop(seconds=float(interval), reconnect=True)
        async def get_status(ip, port, channel_id, guild_id):
            await self._get_status(ip, port, channel_id, guild_id)

        if self.tasks.get(guild.id) == None:
            self.tasks[guild.id] = get_status
            self.tasks[guild.id].start(ip, port, channel_id, guild_id)
        else:
            if self.tasks[guild.id].is_running():
                self.tasks[guild.id].cancel()

            self.tasks[guild.id] = get_status
            self.tasks[guild.id].start(ip, port, channel_id, guild_id)