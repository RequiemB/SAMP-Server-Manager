import discord
from discord.ext import tasks

import asqlite
import datetime

from helpers import utils as _utils

class Status:
    def __init__(self, bot):
        self.bot = bot
        self.status_messages = {} 
        self.tasks = {}

    async def _get_status(self, ip, port, channel_id, guild_id):
        guild = self.bot.get_guild(int(guild_id))
        ping, info = await _utils.get_server_info(ip, int(port))

        try:
            if self.status_messages[guild.id] is not None:
                message = self.status_messages[guild.id]
                await message.delete()
        except:
            pass

        e = discord.Embed(
            title = info.name,
            description = f"Basic information of {info.name}:",
            color = discord.Color.blue(),
            timestamp = datetime.datetime.now()
        )
        e.add_field(name="IP Address", value=f"{ip}:{port}")
        e.add_field(name="Gamemode", value=info.gamemode)
        e.add_field(name="Players", value=f"{info.players}/{info.max_players}")
        e.add_field(name="Latency", value="{:.2f}ms".format(ping))
        e.add_field(name="Password", value=info.password)
        e.add_field(name="Language", value=info.language)

        channel = self.bot.get_channel(channel_id)

        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)

        message = await channel.send(embed=e)
        self.status_messages[guild.id] = message
    
    def retrieve_config_from_data(self, data):
        guild_id = data[0]
        ip = None
        port = None
        interval = None
        fraction = None
        channel_id = None

        if data[1] is not None:
            ip = data[1]
        
        if data[2] is not None:
            port = int(data[2])

        if data[3] is not None:
            interval = data[3]

        if data[4] is not None:
            fraction = data[4]

        if data[5] is not None:
            channel_id = int(data[5])

        return guild_id, ip, port, interval, fraction, channel_id

    async def start_status_global(self):

        conn, cursor = await _utils.execute_query("SELECT * FROM query")  
        data = await cursor.fetchall()

        for index in data:
            
            guild_id, ip, port, interval, fraction, channel_id = self.retrieve_config_from_data(index)

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

        await conn.close()
                
    async def start_status_with_guild(self, guild):

        query = f"SELECT * FROM query WHERE guild_id = {guild.id}"

        conn, cursor = await _utils.execute_query(query)
        data = await cursor.fetchone()

        guild_id, ip, port, interval, fraction, channel_id = self.retrieve_config_from_data(data)

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