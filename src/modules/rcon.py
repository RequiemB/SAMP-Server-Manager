import discord
from discord.ext import commands
from discord import app_commands

import asqlite

class RCON(commands.GroupCog, name="rcon", description="All the RCON commands lie under this group."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="login", description="Logs into the RCON of the SA-MP server set in the guild.")
    async def rcon_login(self, interaction: discord.Interaction):
        await interaction.response.send_message("This feature is yet to be implemented.")

    # This is done in Direct Messages as to not leak the RCON password
    @app_commands.command(name="pass", description="Sets the RCON password of the SA-MP server set in the guild.")
    async def rcon_pass(self, interaction: discord.Interaction):
        await interaction.response.send_message("This feature is yet to be implemented.")

    @app_commands.command(name="cmd", description="Sends a RCON command to the SA-MP server set in the guild.")
    async def rcon_cmd(self, interaction: discord.Interaction, cmd: str):
        await interaction.response.send_message("This feature is yet to be implemented.")

    @app_commands.command(name="whitelist", description="Whitelist a user to execute RCON commands.")
    @app_commands.describe(member="The user to whitelist.")
    async def rcon_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message("This feature is yet to be implemented.")

async def setup(bot: commands.Bot):
    await bot.add_cog(RCON(bot))
