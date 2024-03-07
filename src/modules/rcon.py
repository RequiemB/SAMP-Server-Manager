import discord
from discord.ext import commands
from discord import app_commands

import asyncio
import trio_asyncio

from helpers import (
    utils as _utils,
    query
)

from samp_query import (
    Client,
    InvalidRCONPassword,
    RCONDisabled,
)

from modules.server import get_emoji

RCON_CMDLIST = [
    "cmdlist",
    "varlist",
    "exit",
    "echo",
    "hostname",
    "gamemodetext",
    "mapname",
    "exec",
    "kick",
    "ban",
    "changemode",
    "gmx",
    "reloadbans",
    "reloadlog",
    "say",
    "players",
    "banip",
    "unbanip",
    "gravity",
    "weather",
    "loadfs",
    "weburl",
    "unloadfs",
    "reloadfs",
    "password",
    "messageslimit",
    "ackslimit",
    "messageholelimit",
    "playertimeout",
    "language"
]

class NotLoggedIn(Exception):
    "Exception raised when the user is not logged into RCON."

class RCONLogin(discord.ui.Modal):
    def __init__(self, cog: commands.Cog, user: discord.Member, guild: discord.Guild, ip: str, port: int):
        self.cog = cog
        self.ip = ip
        self.port = port
        self.guild = guild
        self.user = user
        super().__init__(title="RCON Login")
        self.password = discord.ui.TextInput(label="RCON Password", required=True)
        self.add_item(self.password)

    async def on_submit(self, interaction: discord.Interaction): 
        await interaction.response.send_message("Waiting for a response from the server...")
        try:
            await self.cog.login_rcon(self.user, self.guild, self.ip, self.port, self.password.value)
        except InvalidRCONPassword:
            self.cog.update_login_tries(self.guild, self.user)
            tries_left = 3 - self.cog.login_tries[self.guild.id][self.user.id]
            e = discord.Embed(description=f"{get_emoji('failure')} The RCON password is invalid. You have {tries_left} attempts left.", color=discord.Color.red())
            await interaction.edit_original_response(content=None, embed=e)
        except RCONDisabled: 
            e = discord.Embed(description=f"{get_emoji('failure')} RCON is disabled in this server.", color=discord.Color.red())
            await interaction.edit_original_response(content=None, embed=e)
        except query.ServerOffline:
            e = discord.Embed(description=f"{get_emoji('failure')} The server didn't respond after 3 attempts.", color=discord.Color.red())
            await interaction.edit_original_response(content=None, embed=e)
        else:
            e = discord.Embed(description=f"{get_emoji()} You have successfully logged into the RCON of **{self.ip}:{self.port}**. Your session expires in 10 minutes.", color=discord.Color.green())
            await interaction.edit_original_response(content=None, embed=e)
        
class RCONCommand(discord.ui.Modal):
    def __init__(self, cog: commands.Cog, user: discord.Member, guild: discord.Guild):
        self.cog = cog
        self.user = user
        self.guild = guild

        try:
            if self.cog.rcon_logged[guild.id][user.id] is not None:
                self.client = self.cog.rcon_logged[guild.id][user.id]
            else:
                raise NotLoggedIn
        except KeyError:
            raise NotLoggedIn
            
        super().__init__(title="RCON Command")
        self.command = discord.ui.TextInput(label="Command", placeholder="Command to execute. E.g. loadfs bare.pwn | exit | banip 127.0.0.1", required=True)
        self.add_item(self.command)

    async def on_submit(self, interaction: discord.Interaction):
        command = self.command.value.split()[0]
        if command not in RCON_CMDLIST:
            e = discord.Embed(description=f"{get_emoji('failure')} `{command}` is not a RCON command.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)
            return
        
        await interaction.response.send_message(f"RCON Command `{self.command.value}` has been sent. Waiting for a response from the server...", ephemeral=True)
        try:
            response = await interaction.client.query.send_rcon_command(self.client, self.command.value)
        except query.ServerOffline:
            e = discord.Embed(description=f"{get_emoji('failure')} The server didn't respond after 3 attempts.", color=discord.Color.red())
            await interaction.edit_original_response(content=None, embed=e)
        except RCONDisabled: # Might be because of high latency or other reasons, catch the error
            e = discord.Embed(description=f"{get_emoji('timeout')} Timed out waiting for a response from the server. The potential error could be that {self.get_potential_error(command)}", color=discord.Color.red())
            await interaction.edit_original_response(content=None, embed=e)       
        else:
            e = discord.Embed(
                title = "RCON Command Information",
                description = f"Invocation of the RCON Command by {interaction.user.mention} was successful.",
                color = discord.Color.green(),
                timestamp = discord.utils.utcnow()
            )

            e.add_field(name="Command", value=self.command.value)
            e.add_field(name="Invoked at", value=discord.utils.format_dt(discord.utils.utcnow(), style="R"))
            e.add_field(name="Response", value=f"```{response}```", inline=False)

            await interaction.edit_original_response(content=None, embed=e)

    def get_potential_error(self, command: str): # This function is used to get the potential error from the server when no response is received, i.e. RCONDisabled is raised
        error = ""

        if command == "players": # players will receive no response when no players are online
            error = "no players are online."

        if command == "kick": # kick will receive no response when the playerid given is not active
            error = "an invalid player id was provided."

        if command == "ban": # same thing for ban
            error = "an invalid player id was provided."

        return error


class RCON(commands.GroupCog, name="rcon", description="All the RCON commands lie under this group."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.query = bot.query
        self.login_tries = {}

    def update_login_tries(self, guild: discord.Guild, user: discord.Member):
        try:
            self.login_tries[guild.id]
        except KeyError:
            self.login_tries[guild.id] = {}

        try:
            self.login_tries[guild.id][user.id] += 1
        except:
            self.login_tries[guild.id][user.id] = 1

        if self.login_tries[guild.id][user.id] == 3:

            async def reset_login_tries(guild: discord.Guild, user: discord.Member):
                await asyncio.sleep(3000)
                self.login_tries[guild.id][user.id] = 0

            asyncio.create_task(reset_login_tries(guild, user))
    
    async def login_rcon(self, user: discord.Member, guild: discord.Guild, ip: str, port: int, password: str):
        client = await trio_asyncio.trio_as_aio(self.query.connect)(ip, port, password)
        response = await self.query.send_rcon_command(client, f'echo {user.name} has logged into RCON in {guild.name}.')
        self.authenticate_user(user, guild, client)

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

    def authenticate_user(self, user: discord.Member, guild: discord.Guild, client: Client):
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
        try:
            if self.login_tries[interaction.guild.id][interaction.user.id] == 3:
                e = discord.Embed(description=f"{get_emoji('failure')} You don't have any attempts remaining to log into RCON. You must wait until the count resets.", color=discord.Color.red())
                await interaction.response.send_message(embed=e)
                return
        except:
            pass

        async with self.bot.pool.acquire() as conn:
            res = await conn.fetchone("SELECT * FROM query WHERE guild_id = ?", (interaction.guild.id,))

        if res[1] is None:
            e = discord.Embed(description=f"{get_emoji('failure')} You need to configure a SAMP server for this guild before logging into RCON.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)
            return

        if self.is_logged_in(interaction.guild.id, interaction.user.id):
            e = discord.Embed(description=":floppy_disk: You're already logged in to RCON.", color=discord.Color.red())
            await interaction.response.send_message(embed=e, ephemeral=True)
            return 

        login = RCONLogin(self, interaction.user, interaction.guild, res[1], res[2]) # res[1], res[2] = IP, Port
        await interaction.response.send_modal(login)    
        
    @app_commands.command(name="cmd", description="Sends a RCON command to the SA-MP server set in the guild.")
    async def rcon_cmd(self, interaction: discord.Interaction):
        if not self.is_logged_in(interaction.guild.id, interaction.user.id):
            command_mention = _utils.command_mention_from_tree(interaction.client, 0, "rcon login")
            e = discord.Embed(description=f"{get_emoji('failure')} You need to log into RCON using {command_mention} before executing RCON commands.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)
            return

        try: # There's a chance the user gets automatically logged out from the session while executing this command
            command = RCONCommand(self, interaction.user, interaction.guild)
        except NotLoggedIn:
            command_mention = _utils.command_mention_from_tree(interaction.client, 0, "rcon login")
            e = discord.Embed(description=f"{get_emoji('failure')} You need to log into RCON using {command_mention} before executing RCON commands.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)
            return

        await interaction.response.send_modal(command)

    @app_commands.command(name="whitelist", description="Whitelist a user to execute RCON commands.")
    @app_commands.describe(member="The user to whitelist.")
    async def rcon_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message("This feature is yet to be implemented.")

async def setup(bot: commands.Bot):
    await bot.add_cog(RCON(bot))
