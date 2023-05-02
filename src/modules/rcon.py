import discord
from discord.ext import commands
from discord import app_commands

import asqlite

GUILD = discord.Object(id=980522617570213989)

@app_commands.guilds(GUILD)
class RCON(commands.GroupCog, name="rcon", description="All the RCON commands lie under this group."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="login", description="Logs into the RCON of the SA-MP server set in the guild.")
    @app_commands.guilds(GUILD)
    async def rcon_login(self, interaction: discord.Interaction):
        ...

    # This is done in Direct Messages as to not leak the RCON password
    @app_commands.command(name="pass", description="Sets the RCON password of the SA-MP server set in the guild.")
    @app_commands.guilds(GUILD)
    async def rcon_pass(self, interaction: discord.Interaction):
        ...

    @app_commands.command(name="cmd", description="Sends a RCON command to the SA-MP server set in the guild.")
    @app_commands.guilds(GUILD)
    async def rcon_cmd(self, interaction: discord.Interaction, cmd: str):
        ...

    @app_commands.command(name="whitelist", description="Whitelist a user to execute RCON commands.")
    @app_commands.guilds(GUILD)
    @app_commands.describe(member="The user to whitelist.")
    async def rcon_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        ...

async def setup(bot: commands.Bot):
    await bot.add_cog(RCON(bot))
