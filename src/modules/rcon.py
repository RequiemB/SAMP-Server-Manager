import discord
from discord.ext import commands
from discord import app_commands

import asqlite

from helpers import (
    utils as _utils,
    config
)

class RCONFailure(Exception):
    pass

class RCONLogin(discord.ui.View):
    # to be implemented
    pass

class RCON(commands.GroupCog, name="rcon", description="All the RCON commands lie under this group."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def rcon_logged(self):
        return self.bot.rcon_logged

    @rcon_logged.setter
    async def rcon_setter(self, guild_id: int, user_id: int):
        try:
            if user_id in self.bot.rcon_logged[guild_id]:
                return

            self.bot.rcon_logged[guild_id].append(user_id)
        except KeyError:
            self.bot.rcon_logged[guild_id] = []
            self.bot.rcon_logged[guild_id].append(user_id)

    @staticmethod
    def rcon_check():
        async def _rcon_check(interaction: discord.Interaction):
            # TODO: add rcon check
            return True

        return app_commands.check(_rcon_check)

    def is_logged_in(self, guild_id: int, user_id: int):
        try:
            return user_id in self.rcon_logged[guild_id]
        except KeyError:
            return False

    async def authenticate_user(self, guild_id: int, user_id: int):
        # to be implemented
        pass

    @app_commands.command(name="login", description="Logs into the RCON of the SA-MP server set in the guild.")
    @rcon_check()
    async def rcon_login(self, interaction: discord.Interaction):
        conn = await asqlite.connect("./database/query.db")
        cursor = await conn.cursor()

        await cursor.execute("SELECT * FROM query WHERE guild_id = ?", (interaction.guild.id,))
        data = await cursor.fetchone()

        if data[1] is None and data[2] is None:
            e = discord.Embed(description=f"{config.reactionFailure} You need to configure a SAMP server for this guild before logging into RCON.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)
            await conn.close()
            return

        if is_logged_in(interaction.guild.id, interaction.user.id):
            e = discord.Embed(description=":floppy_disk: You're already logged in to RCON.", color=discord.Color.red())
            await interaction.response.send_message(embed=e, ephemeral=True)
            await conn.close()
            return 

        await cursor.execute("SELECT password FROM RCON where guild_id = ?", (interaction.guild.id,))
        res = await cursor.fetchone()

        if res[0] is None:
            e = discord.Embed(description=f"{config.reactionFailure} No RCON password has been set for this guild. You'll have to login manually.", color=discord.Color.red())
            view = RCONLogin(interaction)
            await interaction.response.send_message(embed=e, view=view)
        else:
            info = await _utils.get_server_info(data[1], int(data[2]))
            await authenticate_user(interaction.guild.id, interaction.user.id)
            e = discord.Embed(description=f"{config.reactionSuccess} You have successfully logged into the RCON of `{info.name}`. Your session will be valid for 15 minutes.", color=discord.Color.green())
            await interaction.response.send_message(embed=e)

        await conn.close()        
        
    @app_commands.command(name="cmd", description="Sends a RCON command to the SA-MP server set in the guild.")
    async def rcon_cmd(self, interaction: discord.Interaction, cmd: str):
        await interaction.response.send_message("This feature is yet to be implemented.")

    @app_commands.command(name="whitelist", description="Whitelist a user to execute RCON commands.")
    @app_commands.describe(member="The user to whitelist.")
    async def rcon_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message("This feature is yet to be implemented.")

async def setup(bot: commands.Bot):
    await bot.add_cog(RCON(bot))
