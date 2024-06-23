from __future__ import annotations

import discord
from discord.ext import commands

import asyncio

from datetime import datetime
from helpers import (
    utils as _utils,
)

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..helpers.status import Status
    from bot import QueryBot

class ServerModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View, message: discord.Message, embed: discord.Embed) -> None:
        self.message: discord.Message = message
        self.__view: Config = view # type: ignore
        self.embed: discord.Embed = embed
        self.ip: discord.ui.TextInput = discord.ui.TextInput(label='Address', placeholder="Example IP address: 51.178.143.229:7777")
        super().__init__(title="Set a SA-MP server", timeout=60.0)
        self.add_item(self.ip)
        
    async def on_submit(self, interaction: discord.Interaction):
        assert interaction.guild

        if not _utils.is_ip(self.ip.value):
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} The IP: **{self.ip.value}** is not a valid IP address.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        
        addr = self.ip.value.split(":")

        async with self.__view.bot.pool.acquire() as conn:
            await conn.execute("UPDATE query SET ip = ?, port = ? WHERE guild_id = ?", (addr[0], addr[1], interaction.guild.id,))
            await conn.execute("INSERT OR IGNORE INTO stats (ip, port) VALUES (?, ?)", (addr[0], addr[1]))
            await conn.commit()

        e = discord.Embed(
            description = f"{_utils.get_result_emoji()} Successfully set the SA-MP server for this guild to **{addr[0]}:{addr[1]}**.",
            color = discord.Color.green()
        )

        if isinstance(self.__view.children[0], discord.ui.Button):
            self.__view.server.disabled = True

        self.__view._server = True

        self.embed.clear_fields()
        self.embed.add_field(name="Server", value=f"{_utils.get_result_emoji()} Configured" if self.__view._server else f"{_utils.get_result_emoji('failure')} Not Configured")
        self.embed.add_field(name="Interval", value=f"{_utils.get_result_emoji()} Configured" if self.__view._interval else f"{_utils.get_result_emoji('failure')} Not Configured")
        self.embed.add_field(name="Channel", value=f"{_utils.get_result_emoji()} Configured" if self.__view._channel else f"{_utils.get_result_emoji('failure')} Not Configured")
        await self.message.edit(embed=self.embed, view=self.__view)

        await interaction.response.send_message(embed=e, ephemeral=True)
        await self.__view._status.start_stats_update_with_guild(interaction.guild)

        if self.__view._channel and self.__view._interval:
            self.__view.stop()
            await self.__view._status.start_status_with_guild(interaction.guild)

class IntervalModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View, message: discord.Message, embed: discord.Embed) -> None:
        self.message: discord.Message = message
        self.__view: Config = view # type: ignore
        self.embed: discord.Embed = embed
        self.interval: discord.ui.TextInput = discord.ui.TextInput(label='Interval', placeholder="Example: 5m for 5 minutes and 10m for 10 minutes. Minimum values are 5m and 30m.")
        super().__init__(title="Set an Interval", timeout=60.0)
        self.add_item(self.interval)
        
    async def on_submit(self, interaction: discord.Interaction):
        assert interaction.guild

        duration= _utils.format_time(self.interval.value)
        if not duration:
            e = discord.Embed(description = f"{_utils.get_result_emoji('failure')} Invalid time format specified. The minimum value is `5m` and the maximum value is `30m`.", color = discord.Color.red())
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        async with self.__view.bot.pool.acquire() as conn:
            await conn.execute("UPDATE query SET interval = ? WHERE guild_id = ?", (duration, interaction.guild.id,))
            await conn.commit()

        e = discord.Embed(
            description = f"{_utils.get_result_emoji()} Successfully set the interval for this guild to `{self.interval.value}`.",
            color = discord.Color.green()
        )

        if isinstance(self.__view.children[1], discord.ui.Button):
            self.__view.children[1].disabled = True

        self.__view._interval = True

        self.embed.clear_fields()
        self.embed.add_field(name="Server", value=f"{_utils.get_result_emoji()} Configured" if self.__view._server else f"{_utils.get_result_emoji('failure')} Not Configured")
        self.embed.add_field(name="Interval", value=f"{_utils.get_result_emoji()} Configured" if self.__view._interval else f"{_utils.get_result_emoji('failure')} Not Configured")
        self.embed.add_field(name="Channel", value=f"{_utils.get_result_emoji()} Configured" if self.__view._channel else f"{_utils.get_result_emoji('failure')} Not Configured")
        await self.message.edit(embed=self.embed, view=self.__view)

        await interaction.response.send_message(embed=e, ephemeral=True)

        if self.__view._channel and self.__view._server:
            self.__view.stop()
            await self.__view._status.start_status_with_guild(interaction.guild)

class Config(discord.ui.View):
    def __init__(self, bot: QueryBot, status: Status, embed: discord.Embed) -> None:
        self.bot: QueryBot = bot
        self._status: Status = status
        self.message: Optional[discord.Message] = None
        self.embed: discord.Embed = embed
        self.is_being_configured: Optional[discord.Member] = None # Whether a member is configuring using the view, if yes then disable it for everyone else

        self._server = False
        self._interval = False
        self._channel = False
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        assert type(interaction.user) == discord.Member

        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return False
        
        if self.is_being_configured is not None and interaction.user != self.is_being_configured:
            e = discord.Embed(
                description = f"{_utils.get_result_emoji('failure')} This view is already being used to configure the bot by {self.is_being_configured.mention}.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return False
        
        return True

    @discord.ui.button(style=discord.ButtonStyle.green, label="Set Server")
    async def server(self, interaction: discord.Interaction, button: discord.ui.Button):
        assert type(interaction.user) == discord.Member
        self.is_being_configured = interaction.user

        if self.message:
            await interaction.response.send_modal(ServerModal(self, self.message, self.embed))
        else:
            raise RuntimeError("Message was None at the time of ServerModal initialization")

    @discord.ui.button(style=discord.ButtonStyle.green, label="Set Interval")
    async def interval(self, interaction: discord.Interaction, button: discord.ui.Button):
        assert type(interaction.user) == discord.Member
        self.is_being_configured = interaction.user

        if self.message:
            await interaction.response.send_modal(IntervalModal(self, self.message, self.embed))
        else:
            raise RuntimeError("Message was None at the time of IntervalModal initialization")

    @discord.ui.button(style=discord.ButtonStyle.green, label="Set Channel")
    async def channel(self, interaction: discord.Interaction[QueryBot], button: discord.ui.Button):
        assert interaction.guild and type(interaction.user) == discord.Member

        self.is_being_configured = interaction.user
        e = discord.Embed(
            description = ":keyboard: Mention the channel to send the SA-MP status updates in this chat.\n:watch: This message will timeout in 30 seconds.",
            color = discord.Color.blue()
        )

        await interaction.response.send_message(embed=e, ephemeral=True)
        
        def check(message: discord.Message):
            return message.author.id == interaction.user.id

        try:
            message = await interaction.client.wait_for('message', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            command_mention = await interaction.client.tree.find_mention_for("server channel")
            e.description = f":warning: Message has timed out. Use the command {command_mention} to set a status channel."
            e.color = discord.Color.red()
            await interaction.edit_original_response(embed=e)
        else:
            _id = int(message.content[2:-1])
            channel = interaction.guild.get_channel(_id)

            if channel is None:
                e.description = f"{_utils.get_result_emoji('failure')} An error occured while attempting to fetch the channel. Try again and if the issue still persists, try another channel and make sure I have permissions to view it."
                e.color = discord.Color.red()
                await interaction.followup.send(embed=e, ephemeral=True)
                return
            
            if not isinstance(channel, discord.TextChannel):
                e.description = f"{_utils.get_result_emoji('failure')} Only a text channel can be set as the channel for querying."
                e.color = discord.Color.red()
                await interaction.followup.send(embed=e, ephemeral=True)
                return
                
            try:
                message = await channel.send("This is a test message. Ignore it.")
                await message.delete()
            except discord.Forbidden:
                e.description = f"{_utils.get_result_emoji('failure')} An error occured while attempting to send a message to the channel. Ensure that I have the necessary permissions to send messages in that channel."
                e.color = discord.Color.red()
                await interaction.followup.send(embed=e, ephemeral=True)
                return
                
            async with interaction.client.pool.acquire() as conn:
                await conn.execute("UPDATE query SET channel_id = ? WHERE guild_id = ?", (_id, interaction.guild.id,))
                await conn.commit()

            e.description = f"{_utils.get_result_emoji()} Set the auto status updater channel to {channel.mention}."
            await interaction.edit_original_response(embed=e)

            button.disabled = True
            self._channel = True

            self.embed.clear_fields()
            self.embed.add_field(name="Server", value=f"{_utils.get_result_emoji()} Configured" if self._server else f"{_utils.get_result_emoji('failure')} Not Configured")
            self.embed.add_field(name="Interval", value=f"{_utils.get_result_emoji()} Configured" if self._interval else f"{_utils.get_result_emoji('failure')} Not Configured")
            self.embed.add_field(name="Channel", value=f"{_utils.get_result_emoji()} Configured" if self._channel else f"{_utils.get_result_emoji('failure')} Not Configured")
            
            if self.message:
                await self.message.edit(embed=self.embed, view=self)

            if self._server and self._interval:
                self.stop()
                await self._status.start_status_with_guild(interaction.guild)

class Events(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: QueryBot = bot
        self.emoji = _utils.get_result_emoji()
        self.status: Status = self.bot._status

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.bot.logger.info(f"Bot has been added to {guild.name} (ID: {guild.id})")
        async with self.bot.pool.acquire() as conn:
            await conn.execute("INSERT INTO query (guild_id) VALUES (?)", (guild.id,))
            await conn.commit()

        channel = None

        if guild.system_channel is not None:
            channel = guild.system_channel
        else:
            for c in guild.text_channels:
                if c.name == "general" or c.name == "general-chat":
                    channel = c

        if channel is None:
            channel = guild.text_channels[0]

        assert self.bot.user

        e = discord.Embed(
            title = self.bot.user.name,
            description = "Thanks for inviting me to this guild! You can now get information about your SA-MP server and even set a channel to send the information in a given interval.\n\nYou need to do some basic configuration to access all the bot's features. They are listed below.\nYou can set them now by using the buttons. It's recommended to configure it now.\nJoin the [support server](https://discord.gg/z9j2kb9kB3) if you require help.",
            color = discord.Color.blue(),
            timestamp = datetime.now()
        )

        e.add_field(name="Server", value=f"{_utils.get_result_emoji('failure')} Not Configured")
        e.add_field(name="Interval", value=f"{_utils.get_result_emoji('failure')} Not Configured")
        e.add_field(name="Channel", value=f"{_utils.get_result_emoji('failure')} Not Configured")

        e.set_footer(text="Made by requiem.b", icon_url="https://cdn.discordapp.com/avatars/680416522245636183/08d6f631895d23878a8028e110262a8d.png?size=1024")

        view = Config(self.bot, self.status, e)
        try:
            view.message = await channel.send(embed=e, view=view)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.bot.logger.info(f"Bot was removed from {guild.name} (ID: {guild.id}).")
        async with self.bot.pool.acquire() as conn:
            await conn.execute("DELETE FROM query WHERE guild_id = ?", (guild.id,))
            await conn.commit()

        del self.bot._status.status_messages[guild.id]

        try:
            if self.bot._status.guild_status_tasks[guild.id] is not None:
                if self.bot._status.guild_status_tasks[guild.id].is_running():
                    self.bot._status.guild_status_tasks[guild.id].cancel()
        except KeyError:
            pass

        try:
            if self.bot._status.update_stats_tasks[guild.id].is_running():
                self.bot._status.guild_status_tasks[guild.id].cancel()
        except KeyError:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild:
            return
        
        # Check if the message was sent in the status channel, if it is then re-send the status message
        try:
            if not all([
                self.bot._status.status_messages[message.guild.id] is not None,
                isinstance(self.bot._status.status_messages[message.guild.id], discord.Message),
                message.channel.id == self.bot._status.status_messages[message.guild.id].channel.id,
            ]):
                return
        except (AttributeError, KeyError):
            return
        
        # Re-send it at next query time
        self.bot.logger.warning(f"Resending status message at next query time in {message.guild.name}.")
        self.bot._status._resend_next_iter[message.guild.id] = True

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT channel_id FROM query WHERE guild_id = ?", (channel.guild.id))

            if not res[0]:
                return
            
            if res[0] == channel.id:
                self.bot.logger.info(f"Status channel was deleted in {channel.guild.name}. Cancelling task and removing it from database.")
                await conn.execute("UPDATE query SET channel_id = NULL WHERE guild_id = ?", (channel.guild.id))
                await conn.commit()
                
                del self.bot._status.status_messages[channel.guild.id]
                
                try: 
                    if self.bot._status.guild_status_tasks[channel.guild.id] is not None:
                        if self.bot._status.guild_status_tasks[channel.guild.id].is_running():
                            self.bot._status.guild_status_tasks[channel.guild.id].cancel()
                except (AttributeError, KeyError):
                    pass

                for c in channel.guild.channels: # Let the server moderators know that we don't have permissions
                    if isinstance(c, discord.TextChannel) and c.permissions_for(channel.guild.me).send_messages:
                        await c.send(f"My permissions to send messages in {channel.mention} was revoked. I can no longer update status in that channel. Set a new channel for status using the {await self.bot.tree.find_mention_for('server channel')} command.")
                        break

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT channel_id FROM query WHERE guild_id = ?", (after.guild.id))

            if not res[0]:
                return
            
            if res[0] == after.id and not all([
                after.permissions_for(after.guild.me).send_messages,
                after.permissions_for(after.guild.me).read_messages
            ]):
                self.bot.logger.info(f"Bot has no permissions to send messages in status channel in {after.guild.name}. Cancelling task and removing it from database.")
                await conn.execute("UPDATE query SET channel_id = NULL WHERE guild_id = ?", (after.guild.id))
                await conn.commit()

                del self.bot._status.status_messages[after.guild.id]
                
                try:
                    if self.bot._status.guild_status_tasks[after.guild.id] is not None:
                        if self.bot._status.guild_status_tasks[after.guild.id].is_running():
                            self.bot._status.guild_status_tasks[after.guild.id].cancel()
                except (AttributeError, KeyError):
                    pass

                for channel in after.guild.channels: # Let the server moderators know that we don't have permissions
                    if isinstance(channel, discord.TextChannel) and channel.permissions_for(after.guild.me).send_messages:
                        await channel.send(f"My permissions to send messages in {after.mention} was revoked. I can no longer update status in that channel. Set a new channel for status using the {await self.bot.tree.find_mention_for('server channel')} command.")
                        break

async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))
