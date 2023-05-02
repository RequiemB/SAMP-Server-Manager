import discord
from discord.ext import commands
from discord import app_commands

import asqlite

GUILD = discord.Object(id=980522617570213989)

@app_commands.guilds(GUILD)
class Server(commands.GroupCog, name='server', description="All the server commands lie under this group."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="get", description="Gets the information for the SA-MP server set in this guild.", extras={"cog": "Server"})
    @app_commands.guilds(GUILD)
    async def server_get(self, interaction: discord.Interaction):
        ...

    @app_commands.command(name="set", description="Sets a SA-MP server for this guild.", extras={"cog": "Server"})
    @app_commands.describe(
        ip="The IP address of the SA-MP server.",
        port="The port of the SA-MP server."
    )
    @app_commands.guilds(GUILD)
    async def server_set(self, interaction: discord.Interaction, ip: str, port: int):
        ...

    @app_commands.command(name="interval", description="Sets the interval at which the info should be sent.", extras={"cog": "Server"})
    @app_commands.describe(
        interval="The interval at which the info should be sent. Must be higher than 30s and lower than 30m. Example Usage: 1s for 1 second, 1m for 1 minute."
    )
    @app_commands.guilds(GUILD)
    async def server_interval(self, interaction: discord.Interaction, interval: str):
        ...

async def setup(bot: commands.Bot):
    await bot.add_cog(Server(bot))