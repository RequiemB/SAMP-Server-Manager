import discord
from discord.ext import commands

import asyncio

from datetime import datetime
from helpers import (
    utils as _utils,
)

from modules.server import get_emoji

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
                description = f"{get_emoji('failure')} The IP: **{self.ip.value}** is not a valid IP address.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        
        addr = self.ip.value.split(":")

        async with interaction.client.pool.acquire() as conn:
            await conn.execute("UPDATE query SET ip = ?, port = ? WHERE guild_id = ?", (addr[0], addr[1], interaction.guild.id,))
            await conn.commit()

        e = discord.Embed(
            description = f"{get_emoji()} Successfully set the SA-MP server for this guild to **{addr[0]}:{addr[1]}**.",
            color = discord.Color.green()
        )

        self.__view.children[0].disabled = True
        self.__view._server = True

        self.embed.clear_fields()
        self.embed.add_field(name="Server", value=f"{get_emoji()} Configured" if self.__view._server else f"{get_emoji('failure')} Not Configured")
        self.embed.add_field(name="Interval", value=f"{get_emoji()} Configured" if self.__view._interval else f"{get_emoji('failure')} Not Configured")
        self.embed.add_field(name="Channel", value=f"{get_emoji()} Configured" if self.__view._channel else f"{get_emoji('failure')} Not Configured")
        await self.message.edit(embed=self.embed, view=self.__view)

        await interaction.response.send_message(embed=e, ephemeral=True)

        if self.__view._channel and self.__view._interval:
            await self.__view._status.start_status_with_guild(interaction.guild)

class IntervalModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View, message: discord.Message, embed: discord.Embed):
        self.message = message
        self.__view = view
        self.embed = embed
        self.interval = discord.ui.TextInput(label='Interval', placeholder="Example: 5m for 5 minutes and 10m for 10 minutes. Minimum values are 5m and 30m.")
        super().__init__(title="Set an Interval", timeout=60.0)
        self.add_item(self.interval)
        
    async def on_submit(self, interaction: discord.Interaction):
        duration= _utils.format_time(self.interval.value)
        if duration == "":
            e = discord.Embed(description = f"{get_emoji('failure')} Invalid time format specified. The minimum value is `5m` and the maximum value is `30m`.", color = discord.Color.red())
            await interaction.response.send_message(embed=e)
            return

        async with interaction.client.pool.acquire() as conn:
            await conn.execute("UPDATE query SET interval = ? WHERE guild_id = ?", (duration, interaction.guild.id,))
            await conn.commit()

        e = discord.Embed(
            description = f"{get_emoji()} Successfully set the interval for this guild to `{self.interval.value}`.",
            color = discord.Color.green()
        )

        self.__view.children[1].disabled = True
        self.__view._interval = True

        self.embed.clear_fields()
        self.embed.add_field(name="Server", value=f"{get_emoji()} Configured" if self.__view._server else f"{get_emoji('failure')} Not Configured")
        self.embed.add_field(name="Interval", value=f"{get_emoji()} Configured" if self.__view._interval else f"{get_emoji('failure')} Not Configured")
        self.embed.add_field(name="Channel", value=f"{get_emoji()} Configured" if self.__view._channel else f"{get_emoji('failure')} Not Configured")
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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.manage_guild:
            e = discord.Embed(
                description = f"{get_emoji('failure')} You require the **Manage Guild** permission in order to execute this command.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return False
        
        return True

    @discord.ui.button(style=discord.ButtonStyle.green, label="Set Server")
    async def server(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ServerModal(self, self.message, self.embed))

    @discord.ui.button(style=discord.ButtonStyle.green, label="Set Interval")
    async def interval(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(IntervalModal(self, self.message, self.embed))

    @discord.ui.button(style=discord.ButtonStyle.green, label="Set Channel")
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
            command_mention = await _utils.command_mention_from_tree(interaction.client, 1, "server channel")
            e.description = f":warning: Message has timed out. Use the command {command_mention} to set a status channel."
            e.color = discord.Color.red()
            await interaction.edit_original_response(embed=e)
        else:
            _id = int(message.content[2:-1])
            channel = interaction.guild.get_channel(_id)
            if channel is None:
                channel = await interaction.guild.fetch_channel(_id)
                
                if channel is None:
                    e.description = f"{get_emoji('failure')} An error occured while attempting to fetch the channel. Try again and if the issue still persists, try another channel and make sure I have permissions to view it."
                    await interaction.followup.send(embed=e, ephemeral=True)
                    return
                    
            async with interaction.client.pool.acquire() as conn:
                await conn.execute("UPDATE query SET channel_id = ? WHERE guild_id = ?", (_id, interaction.guild.id,))
                await conn.commit()

            e.description = f"{get_emoji()} Set the auto status updater channel to {channel.mention}."
            await interaction.edit_original_response(embed=e)

            self.children[2].disabled = True
            self._channel = True

            self.embed.clear_fields()
            self.embed.add_field(name="Server", value=f"{get_emoji()} Configured" if self._server else f"{get_emoji('failure')} Not Configured")
            self.embed.add_field(name="Interval", value=f"{get_emoji()} Configured" if self._interval else f"{get_emoji('failure')} Not Configured")
            self.embed.add_field(name="Channel", value=f"{get_emoji()} Configured" if self._channel else f"{get_emoji('failure')} Not Configured")
            
            await self.message.edit(embed=self.embed, view=self)

            if self._server and self._interval:
                await self._status.start_status_with_guild(interaction.guild)

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.status = bot._status

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        async with self.bot.pool.acquire() as conn:
            await conn.execute("INSERT INTO query (guild_id) VALUES (?)", (guild.id,))
            await conn.commit()

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

        e.add_field(name="Server", value=f"{get_emoji('failure')} Not Configured")
        e.add_field(name="Interval", value=f"{get_emoji('failure')} Not Configured")
        e.add_field(name="Channel", value=f"{get_emoji('failure')} Not Configured")

        e.set_footer(text="Made by requiem.b", icon_url="https://cdn.discordapp.com/avatars/680416522245636183/08d6f631895d23878a8028e110262a8d.png?size=1024")

        view = Config(self.status, e)
        try:
            view.message = await channel.send(embed=e, view=view)
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        query = f"DELETE FROM query WHERE guild_id = {guild.id}"
        async with self.bot.pool.acquire() as conn:
            await conn.execute("DELETE FROM query WHERE guild_id = ?", (guild.id,))
            await conn.commit()

async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))
