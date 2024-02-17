import discord
from discord.ext import commands
from discord import app_commands

import asqlite
import asyncio
import trio_asyncio

from helpers import (
    utils as _utils,
    config
)

from samp_query import (
    Client,
    InvalidRCONPassword,
    RCONDisabled,
)

class RCONLogin(discord.ui.Modal):
    def __init__(self, cog, user, guild, ip, port):
        self.cog = cog
        self.ip = ip
        self.port = port
        self.guild = guild
        self.user = user
        super().__init__(title="RCON Login")
        self.password = discord.ui.TextInput(label="RCON Password", required=True)
        self.add_item(self.password)

    async def on_submit(self, interaction: discord.Interaction): 
        await interaction.response.send_message("Waiting for a response from the server...", ephemeral=True)
        try:
            await self.cog.login_rcon(self.user, self.guild, self.ip, self.port, self.password.value)
        except InvalidRCONPassword:
            e = discord.Embed(description=f"{config.reactionFailure} The RCON password is invalid.", color=discord.Color.red())
            await interaction.edit_original_response(content=None, embed=e)
        except RCONDisabled: # RCONDisabled is being raised always due to a bug in the library
            e = discord.Embed(description=f"{config.reactionFailure} RCON is disabled in this server.", color=discord.Color.red())
            await interaction.edit_original_response(content=None, embed=e)
        else:
            e = discord.Embed(description=f"{config.reactionSuccess} You have successfully logged into the RCON of **{self.ip}:{self.port}**. Your session expires in 10 minutes.", color=discord.Color.green())
            await interaction.edit_original_response(content=None, embed=e)

class RCON(commands.GroupCog, name="rcon", description="All the RCON commands lie under this group."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.query = bot.query
    
    async def login_rcon(self, user: discord.Member, guild: discord.Guild, ip: str, port: int, password: str):
        client = await trio_asyncio.trio_as_aio(self.query.connect)(ip, port, password)
        response = await self.query.send_rcon_command(client, f'echo {user.name} has logged into RCON in {guild.name}.')
        await self.authenticate_user(user, guild, client)

    @property
    def rcon_logged(self):
        return self.bot.rcon_logged

    @rcon_logged.setter
    def rcon_logged(self, value):
        guild_id = value[0]
        user_id = value[1]
        client = value[2]

        if guild_id not in self.bot.rcon_logged:
            self.bot.rcon_logged[guild_id] = {}

        self.bot.rcon_logged[guild_id][user_id] = client

    def is_logged_in(self, guild_id: int, user_id: int):
        try:
            return user_id in self.rcon_logged[guild_id]
        except KeyError:
            return False

    async def authenticate_user(self, user: discord.Member, guild: discord.Guild, client: Client):
        self.rcon_logged = (guild.id, user.id, client)

        async def session_logout(user: discord.Member, guild: discord.Guild, client: Client):
            if user.id in self.rcon_logged[guild.id]:
                await asyncio.sleep(600)
                data = await self.query.get_server_data(client.ip, client.port)
                name = data["info"].name

                del self.rcon_logged[guild.id][user.id]

                await user.send(f"You have been automatically logged out of the RCON of **{name}**.")

        asyncio.create_task(session_logout(user, guild, client))

    @app_commands.command(name="login", description="Logs into the RCON of the SA-MP server set in the guild.")
    async def rcon_login(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT * FROM query WHERE guild_id = ?", (interaction.guild.id,))

        if res[1] is None:
            e = discord.Embed(description=f"{config.reactionFailure} You need to configure a SAMP server for this guild before logging into RCON.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)
            return

        if self.is_logged_in(interaction.guild.id, interaction.user.id):
            e = discord.Embed(description=":floppy_disk: You're already logged in to RCON.", color=discord.Color.red())
            await interaction.response.send_message(embed=e, ephemeral=True)
            return 

        login = RCONLogin(self, interaction.user, interaction.guild, res[1], res[2]) # res[1], res[2] = IP, Port
        await interaction.response.send_modal(login)    
        
    @app_commands.command(name="cmd", description="Sends a RCON command to the SA-MP server set in the guild.")
    async def rcon_cmd(self, interaction: discord.Interaction, cmd: str):
        await interaction.response.send_message("This feature is yet to be implemented.")

    @app_commands.command(name="whitelist", description="Whitelist a user to execute RCON commands.")
    @app_commands.describe(member="The user to whitelist.")
    async def rcon_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message("This feature is yet to be implemented.")

async def setup(bot: commands.Bot):
    await bot.add_cog(RCON(bot))
