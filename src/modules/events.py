import discord
from discord.ext import commands

import asqlite
import asyncio

from datetime import datetime
from helpers import (
    utils as _utils,
    config
)

class ServerModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View, message: discord.Message, embed: discord.Embed):
        self.message = message
        self.__view = view
        self.embed = embed
        self.ip = discord.ui.TextInput(label='Address', placeholder="Example IP address: 51.178.143.229:7777")
        super().__init__(title="Set a SA-MP server", timeout=60.0)
        self.add_item(self.ip)
        
    async def on_submit(self, interaction: discord.Interaction):
        if not _utils.is_ip(self.ip.value):
            e = discord.Embed(
                description = f"{config.reactionFailure} The IP: **{self.ip.value}** is not a valid IP address.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        addr = self.ip.value.split(":")

        await _utils.update_server_for_guild(interaction.guild, addr[0], addr[1])

        e = discord.Embed(
            description = f"{config.reactionSuccess} Successfully set the SA-MP server for this guild to **{addr[0]}:{addr[1]}**.",
            color = discord.Color.green()
        )

        self.__view.children[0].disabled = True
        self.__view._server = True

        self.embed.clear_fields()
        self.embed.add_field(name="Server", value=f"{config.reactionSuccess} Configured" if self.__view._server else f"{config.reactionFailure} Not Configured")
        self.embed.add_field(name="Interval", value=f"{config.reactionSuccess} Configured" if self.__view._interval else f"{config.reactionFailure} Not Configured")
        self.embed.add_field(name="Channel", value=f"{config.reactionSuccess} Configured" if self.__view._channel else f"{config.reactionFailure} Not Configured")
        await self.message.edit(embed=self.embed, view=self.__view)

        await interaction.response.send_message(embed=e, ephemeral=True)

        if self.__view._channel and self.__view._interval:
            await self.__view._status.start_status_with_guild(interaction.guild)

class IntervalModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View, message: discord.Message, embed: discord.Embed):
        self.message = message
        self.__view = view
        self.embed = embed
        self.interval = discord.ui.TextInput(label='Interval', placeholder="Example: 1m for a minute, 30s for 30 seconds and 10m for 10 minutes.")
        super().__init__(title="Set an Interval", timeout=60.0)
        self.add_item(self.interval)
        
    async def on_submit(self, interaction: discord.Interaction):
        duration, fraction = _utils.format_time(self.interval.value)
        if duration == "" and fraction == "":
            e = discord.Embed(description = f"{config.reactionFailure} Invalid time format specified. Time must be passed as `1s` for a second or `1m` for a minute.", color = discord.Color.red())
            await interaction.response.send_message(embed=e)
            return
        elif duration == "error" and fraction == "":
            e = discord.Embed(description = f"{config.reactionFailure} Invalid time format specified. The minimum value is `30s` and the maximum value is `30m`.", color = discord.Color.red())
            await interaction.response.send_message(embed=e)
            return

        query = f"UPDATE query SET INTERVAL = {duration}, FRACTION = '{fraction}' WHERE guild_id = {interaction.guild.id}"
        conn, cursor = await _utils.execute_query(query)

        await conn.commit()
        await conn.close()

        e = discord.Embed(
            description = f"{config.reactionSuccess} Successfully set the interval for this guild to `{self.interval.value}`.",
            color = discord.Color.green()
        )

        self.__view.children[1].disabled = True
        self.__view._interval = True

        self.embed.clear_fields()
        self.embed.add_field(name="Server", value=f"{config.reactionSuccess} Configured" if self.__view._server else f"{config.reactionFailure} Not Configured")
        self.embed.add_field(name="Interval", value=f"{config.reactionSuccess} Configured" if self.__view._interval else f"{config.reactionFailure} Not Configured")
        self.embed.add_field(name="Channel", value=f"{config.reactionSuccess} Configured" if self.__view._channel else f"{config.reactionFailure} Not Configured")
        await self.message.edit(embed=self.embed, view=self.__view)

        await interaction.response.send_message(embed=e, ephemeral=True)

        if self.__view._channel and self.__view._server:
            await self.__view._status.start_status_with_guild(interaction.guild)

class Config(discord.ui.View):
    def __init__(self, status, embed: discord.Embed):
        self._status = status
        self.message = None
        self.embed = embed
        self._server = False
        self._interval = False
        self._channel = False
        super().__init__(timeout=300.0)

    @discord.ui.button(style=discord.ButtonStyle.green, label="Set Server", emoji="<:au:981890460513620060>")
    async def server(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ServerModal(self, self.message, self.embed))

    @discord.ui.button(style=discord.ButtonStyle.green, label="Set Interval", emoji="<:au:981890460513620060>")
    async def interval(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(IntervalModal(self, self.message, self.embed))

    @discord.ui.button(style=discord.ButtonStyle.green, label="Set Channel", emoji="<:au:981890460513620060>")
    async def channel(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            command_mention = await _utils.format_command_mention_from_command(interaction.client, "server", "channel")
            e.description = f":warning: Message has timed out. Use the command {command_mention} to set a status channel."
            e.color = discord.Color.red()
            await interaction.edit_original_response(embed=e)
        else:
            _id = int(message.content[2:-1])
            channel = interaction.guild.get_channel(_id)
            if channel is None:
                channel = await interaction.guild.fetch_channel(_id)
                
                if channel is None:
                    e.description = f"{config.reactionFailure} An error occured while attempting to fetch the channel. Try again and if the issue still persists, try another channel and make sure I have permissions to view it."
                    await interaction.followup.send(embed=e)
                    return
                    
            query = f"UPDATE query SET channel_id = {_id} WHERE guild_id = {interaction.guild.id}"
            conn, cursor = await _utils.execute_query(query)

            await conn.commit()
            await conn.close()

            e.description = f"{config.reactionSuccess} Successfully set the auto status updater channel to {channel.mention}."
            await interaction.edit_original_response(embed=e)

            self.children[2].disabled = True
            self._channel = True

            self.embed.clear_fields()
            self.embed.add_field(name="Server", value=f"{config.reactionSuccess} Configured" if self._server else f"{config.reactionFailure} Not Configured")
            self.embed.add_field(name="Interval", value=f"{config.reactionSuccess} Configured" if self._interval else f"{config.reactionFailure} Not Configured")
            self.embed.add_field(name="Channel", value=f"{config.reactionSuccess} Configured" if self._channel else f"{config.reactionFailure} Not Configured")
            
            await self.message.edit(embed=self.embed, view=self)

            if self._server and self._interval:
                await self._status.start_status_with_guild(interaction.guild)


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.status = bot._status

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await _utils.add_guild(guild)

        if guild.system_channel is not None:
            channel = guild.system_channel
        else:
            for c in guild.text_channels:
                if c.name == "general" or c.name == "general-chat":
                    channel = c

        if channel is None:
            channel = guild.text_channels[0]

        e = discord.Embed(
            title = self.bot.user.name,
            description = "Thanks for inviting me to this guild! You can now get information about your SA-MP server and even set a channel to send the information in a given interval.\n\nYou need to do some basic configuration to access all the bot's features. They are listed below.\nYou can set them now by using the buttons. It's recommended to configure it now.",
            color = discord.Color.blue(),
            timestamp = datetime.now()
        )

        e.add_field(name="Server", value=f"{config.reactionFailure} Not Configured")
        e.add_field(name="Interval", value=f"{config.reactionFailure} Not Configured")
        e.add_field(name="Channel", value=f"{config.reactionFailure} Not Configured")

        view = Config(self.status, e)
        view.message = await channel.send(embed=e, view=view)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        query = f"DELETE FROM query WHERE guild_id = {guild.id}"
        conn, cursor = await _utils.execute_query(query)
        await conn.commit()
        await conn.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))
