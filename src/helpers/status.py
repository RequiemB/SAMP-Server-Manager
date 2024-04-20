from __future__ import annotations

import discord
from discord.ext import tasks

import traceback

from helpers import utils as _utils
from .query import ServerOffline
from datetime import datetime
from .errors import StatusChannelNotFound

from typing import Dict, Union, Optional, TYPE_CHECKING
from ._types import ServerData

if TYPE_CHECKING:
    from .query import Query
    from bot import QueryBot
    from sqlite3 import Row
    from samp_query import ServerInfo

DAILY_STATS_INTERVAL = 60 # The interval at which to get the daily stats of the server (in minutes)

class Status:
    def __init__(self, bot):
        self.bot: QueryBot = bot
        self.query: Query = self.bot.query
        self.global_running: bool = False

        self.status_messages: Dict[int, discord.Message] = {} 
        self.guild_status_tasks: Dict[int, tasks.Loop] = {}
        self.last_dailystats_update: Dict[int, datetime] = {}
        self._resend_next_iter: Dict[int, bool] = {} 

    def get_status_channel(self, guild_id: int, channel_id: int) -> discord.TextChannel:
        channel = self.bot.get_channel(channel_id)

        if not channel:
            raise StatusChannelNotFound(guild_id)
        
        assert isinstance(channel, discord.TextChannel)
        return channel

    async def get_status_message(self, guild_id: int, channel_id: int) -> Optional[Union[discord.Message, discord.PartialMessage]]:
        try:
            if self.status_messages[guild_id] is not None and isinstance(self.status_messages[guild_id], discord.Message):
                return self.status_messages[guild_id]
        except KeyError:
            pass
                
        channel = self.get_status_channel(guild_id, channel_id)

        if not channel:
            raise StatusChannelNotFound(guild_id)

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT message_id FROM query WHERE guild_id = ?", (guild_id,))

        if not res[0]:
            return None

        message = channel.get_partial_message(res[0])
        return message
    
    async def resend_status_message(self, channel: discord.TextChannel, *args, **kwargs) -> discord.Message:
        try:
            await self.status_messages[channel.guild.id].delete() # type: ignore
        except Exception:
            pass
        message = await channel.send(*args, **kwargs)
        self.status_messages[channel.guild.id] = message

        async with self.bot.pool.acquire() as conn:
            await conn.execute("UPDATE query SET message_id = ? WHERE guild_id = ?", (message.id, channel.guild.id,))
            await conn.commit()

        return message

    @tasks.loop(minutes=2.0, reconnect=True)
    async def update_stats(self):
        """The task that updates the server stats."""
        finished_servers = [] # List of servers that have been already updated

        try:
            async with self.bot.pool.acquire() as conn:
                res = await conn.fetchall("SELECT guild_id, ip, port FROM query")
        except Exception as exc: # Database isn't properly set up, most likely
            self.bot.logger.error("Exception occured in update_stats", exc_info=exc)
            return 
        
        for guild_data in res:
            try:
                guild_id, ip, port = guild_data[0], guild_data[1], guild_data[2]

                if ip is None and port is None:
                    continue

                if (ip, port) in finished_servers:
                    continue

                is_server_active: bool = False
                data: Dict[str, Union[str, int, ServerInfo]] = {}

                try:
                    data["info"] = await self.query.get_server_info(ip, port, retry=False)
                    is_server_active = True
                except Exception as exc:
                    if not isinstance(exc, ServerOffline):
                        traceback.print_exc()

                data["ip"] = ip
                data["port"] = port

                if is_server_active:
                    await self.update_server_stats(data) # type: ignore
                try:
                    self.last_dailystats_update[guild_id]
                except KeyError:
                    await self.update_daily_server_stats(data, is_server_active, guild_id)
                else:
                    difference = datetime.now() - self.last_dailystats_update[guild_id]
                    minutes = divmod(difference.total_seconds(), 60)[0]
                    if minutes >= DAILY_STATS_INTERVAL:
                        await self.update_daily_server_stats(data, is_server_active, guild_id)

                finished_servers.append((ip, port))
                self.bot.logger.info(f"Finished updating statistics of {ip}:{port}.")
                                
            except Exception: # An exception occured in a guild, catch it, log it to discord and then move on to the next guild
                await self.bot.log_error_via_webhook("get_status", traceback.format_exc(), extra=f"in guild ID {guild_id}") # type: ignore

    async def update_server_stats(self, data: Dict[str, str | int | ServerInfo]) -> None:
        async with self.bot.pool.acquire() as conn:
            stats = await conn.fetchone("SELECT highest_playercount, peak_hour FROM stats WHERE ip = ? AND port = ?", (data["ip"], data["port"]))
            
            highest_playercount, peak_hour = stats[0], stats[1]
            current_players = data["info"].players # type: ignore

            query: str
            params: tuple[int, str | None, Union[str, int]]

            if not highest_playercount or current_players > highest_playercount:
                peak_hour = _utils.get_peak_hour() if highest_playercount else None
                query, params = "UPDATE stats SET highest_playercount = ?, peak_hour = ? WHERE ip = ? AND port = ?", (current_players, peak_hour, data["ip"], data["port"]) # type: ignore
                await conn.execute(query, params)
                await conn.commit()

    async def update_daily_server_stats(self, data: Dict[str, Union[str, int, ServerInfo]], is_server_active: bool, guild_id: int) -> None:
        ip, port = data["ip"], data["port"]
        if is_server_active:
            player_count = data["info"].players # type: ignore
            status = "online"
        else:
            player_count = 0
            status = "offline"

        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M")

        query = """
            INSERT INTO dailystats (
                ip,
                port,
                playercount,
                date,
                time,
                status
            )
            VALUES (
                ?, ?, ?, ?, ?, ?
            )
        """
        params = (ip, port, player_count, date, time, status)

        async with self.bot.pool.acquire() as conn:
            await conn.execute(query, params)
            await conn.commit()

        self.last_dailystats_update[guild_id] = datetime.now()

    async def send_offline_status(self, interval: int, channel_id: int, guild_id: int) -> None:
        e = discord.Embed(
            description = f"{_utils.get_result_emoji('failure')} The server didn't respond after 3 attempts.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )

        e.set_footer(text=f"Auto-updates every {int(interval)} minutes | Last updated", icon_url="https://cdn.discordapp.com/emojis/1226063973644763147.gif?size=128&quality=lossless")

        try:
            if self._resend_next_iter[guild_id]:
                channel = self.get_status_channel(guild_id, channel_id)
                
                await self.resend_status_message(channel, embed=e)
                self._resend_next_iter[guild_id] = False
                return
        except (KeyError, AttributeError):
            pass

        message = await self.get_status_message(guild_id, channel_id)

        if not message:
            self.status_messages[guild_id] = await self.get_status_channel(guild_id, channel_id).send(embed=e)

            async with self.bot.pool.acquire() as conn:
                await conn.execute("UPDATE query SET message_id = ? WHERE guild_id = ?", (self.status_messages[guild_id].id, guild_id,))
                await conn.commit()

        elif isinstance(message, discord.Message):
            self.status_messages[guild_id] =  await message.edit(embed=e, view=None)
        else:
            try:
                self.status_messages[guild_id] =  await message.edit(embed=e, view=None)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound): # Message doesn't exist
                self.status_messages[guild_id] = await self.get_status_channel(guild_id, channel_id).send(embed=e)

                async with self.bot.pool.acquire() as conn:
                    await conn.execute("UPDATE query SET message_id = ? WHERE guild_id = ?", (self.status_messages[guild_id].id, guild_id,))
                    await conn.commit()

    async def send_status(self, data: ServerData, interval: int, channel_id: int, guild_id: int) -> None:
        self.bot.server_data[guild_id] = data

        e, view = _utils.make_svinfo_embed(data)
        e.set_footer(text=f"Auto-updates every {int(interval)} minutes | Last updated", icon_url="https://cdn.discordapp.com/emojis/1226063973644763147.gif?size=128&quality=lossless")

        try:
            if self._resend_next_iter[guild_id]:
                channel = self.get_status_channel(guild_id, channel_id)
                await self.resend_status_message(channel, embed=e, view=view)
                self._resend_next_iter[guild_id] = False
                return
        except (KeyError, AttributeError):
            pass

        message = await self.get_status_message(guild_id, channel_id)

        if not message:
            self.status_messages[guild_id] = await self.get_status_channel(guild_id, channel_id).send(embed=e, view=view)

            async with self.bot.pool.acquire() as conn:
                await conn.execute("UPDATE query SET message_id = ? WHERE guild_id = ?", (self.status_messages[guild_id].id, guild_id,))
                await conn.commit()

        elif isinstance(message, discord.Message):
            self.status_messages[guild_id] = await message.edit(embed=e, view=view)
        else:
            try:
                self.status_messages[guild_id] = await message.edit(embed=e, view=view)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound): # Message doesn't exist
                self.status_messages[guild_id] = await self.get_status_channel(guild_id, channel_id).send(embed=e, view=view)

                async with self.bot.pool.acquire() as conn:
                    await conn.execute("UPDATE query SET message_id = ? WHERE guild_id = ?", (self.status_messages[guild_id].id, guild_id,))
                    await conn.commit()

    def retrieve_config_from_data(self, data: Row) -> tuple[int, str | None, int | None, float | None, int | None]:
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
            interval = float(data[3])

        if data[4] is not None:
            channel_id = int(data[4])

        return guild_id, ip, port, interval, channel_id
                
    async def start_status_with_guild(self, guild: discord.Guild) -> None:
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT guild_id, ip, port, interval, channel_id FROM query WHERE guild_id = ?", (guild.id,))

        guild_id, ip, port, interval, channel_id = self.retrieve_config_from_data(res)

        assert interval is not None

        @tasks.loop(minutes=interval, reconnect=True)
        async def get_status(guild_id, ip, port, channel_id, interval):
            try:
                data = await self.query.get_server_data(ip, port)
            except ServerOffline:
                try:
                    await self.send_offline_status(interval, channel_id, guild_id)
                except Exception:
                    await self.bot.log_error_via_webhook("get_status", traceback.format_exc(), extra=f"in guild ID {guild_id}")
            except Exception: # Any other exception
                await self.bot.log_error_via_webhook("get_status", traceback.format_exc(), extra=f"in guild ID {guild_id}")
            else:
                try:
                    await self.send_status(data, interval, channel_id, guild_id)
                except Exception:
                    await self.bot.log_error_via_webhook("get_status", traceback.format_exc(), extra=f"in guild ID {guild_id}")

        try:
            if self.guild_status_tasks[guild_id] is not None:
                if self.guild_status_tasks[guild_id].is_running():
                    self.guild_status_tasks[guild_id].cancel()
        except KeyError:
            pass

        self._resend_next_iter[guild.id] = False

        try:
            if self.status_messages[guild.id].channel.id != channel_id:
                self._resend_next_iter[guild_id] = True
        except (AttributeError, KeyError):
            pass

        self.guild_status_tasks[guild_id] = get_status
        self.guild_status_tasks[guild_id].start(guild_id, ip, port, channel_id, interval)
        self.bot.logger.info(f"Query status task was started at guild ID {guild_id}.")

    async def start_global_status(self) -> None:
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchall("SELECT guild_id, ip, port, interval, channel_id, message_id FROM query")

        for guild_data in res:
            guild_id, ip, port, interval, channel_id = self.retrieve_config_from_data(guild_data)
            message_id = guild_data[5]

            if not all([
                guild_id is not None,
                ip is not None,
                port is not None,
                interval is not None,
                channel_id is not None,
            ]):
                continue

            assert interval and channel_id

            @tasks.loop(minutes=interval, reconnect=True)
            async def get_status(guild_id, ip, port, channel_id, interval):
                try:
                    data = await self.query.get_server_data(ip, port)
                except ServerOffline:
                    try:
                        await self.send_offline_status(interval, channel_id, guild_id)
                    except Exception:
                        await self.bot.log_error_via_webhook("get_status", traceback.format_exc(), extra=f"in guild ID {guild_id}")
                except Exception:
                    await self.bot.log_error_via_webhook("get_status", traceback.format_exc(), extra=f"in guild ID {guild_id}")
                else:
                    try:
                        await self.send_status(data, interval, channel_id, guild_id)
                    except Exception:
                        await self.bot.log_error_via_webhook("get_status", traceback.format_exc(), extra=f"in guild ID {guild_id}")

            try:
                if self.guild_status_tasks[guild_id] is not None:
                    if self.guild_status_tasks[guild_id].is_running():
                        self.guild_status_tasks[guild_id].cancel()
            except KeyError:
                pass

            self._resend_next_iter[guild_id] = False

            # Check if the last message in the status channel is the bot's after bot restart
            try:
                if message_id and self.get_status_channel(guild_id, channel_id).last_message_id != message_id:
                    self._resend_next_iter[guild_id] = True
            except Exception:
                await self.bot.log_error_via_webhook("get_status", traceback.format_exc(), extra=f"in guild ID {guild_id}")

            self.guild_status_tasks[guild_id] = get_status
            self.guild_status_tasks[guild_id].start(guild_id, ip, port, channel_id, interval)
            self.bot.logger.info(f"Query status task was started at guild ID {guild_id}.")

        self.global_running = True