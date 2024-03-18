import discord
from discord import app_commands
from discord.ext import commands

from helpers import (
    config, 
    utils as _utils,
    query
)
from modules.server import get_emoji

class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.query = bot.query

    @app_commands.command(name="bugreport", description="Use this command to report a bug found in the bot.", extras={"Cog": "Misc"})
    @app_commands.describe(bug="The bug that was found.")
    async def bugreport(self, interaction: discord.Interaction, *, bug: str):
        channel = interaction.client.get_channel(int(config.BUG_REPORT_CHANNEL))
        if channel is None:
            channel = await interaction.client.fetch_channel(int(config.BUG_REPORT_CHANNEL))

            if channel is None:
                e = discord.Embed(description=f"{get_emoji('failure')} No channel for bug reports is configured.", color=discord.Color.red())
                await interaction.response.send_message(embed=e)
                return
            
        e = discord.Embed(
            title=f"Report by {interaction.user}", 
            description=f"Bug report was made by {interaction.user} (ID: {interaction.user.id}) in {interaction.guild} (ID: {interaction.guild.id})",
            color = discord.Color.blue(),
            timestamp = discord.utils.utcnow()
        )

        e.add_field(name="Bug Report", value=f"```{bug}```")
        await channel.send(embed=e)
        e = discord.Embed(description=f"{get_emoji('success')} Your bug report has been sent successfully. Join the [support server](https://discord.gg/z9j2kb9kB3) to know the status.", color=discord.Color.green())
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="status", description="Gets the status of any SA-MP/OMP game server.", extras={"Cog": "Server"})
    @app_commands.describe(ip="The IP address of the server.")
    async def status(self, interaction: discord.Interaction, ip: str):
        if not _utils.is_ip(ip):
            e = discord.Embed(
                description = f"{get_emoji('failure')} The IP: **{ip}** is not a valid IP address.",
                color = discord.Color.red()
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        
        await interaction.response.send_message("Waiting for a response from the server...", ephemeral=True)

        addr = ip.split(":")

        try:
            data = await self.query.get_server_data(addr[0], addr[1])
        except query.ServerOffline:
            e = discord.Embed(description=f"{get_emoji('failure')} The server didn't respond after 3 attempts.", color=discord.Color.red())
            await interaction.edit_original_response(content=None, embed=e)
            return
        
        e = _utils.make_svinfo_embed(addr[0], addr[1], data)
        await interaction.edit_original_response(content=None, embed=e)
    
async def setup(bot: commands.Bot):
    await bot.add_cog(Misc(bot))