import discord
from discord.ext import commands
from discord import app_commands

import asqlite
import traceback
import asyncio
import os
import logging

from samp_query import Client
from helpers import (
    config,
    log, 
    utils
)
from pkgutil import iter_modules
from dotenv import load_dotenv

logger = logging.getLogger("QueryBot")
logger.setLevel(logging.DEBUG)
logger.propagate = False

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(log.Logger()) 
logger.addHandler(handler)


class QueryBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix = config.PREFIX,
            intents = discord.Intents.all(),
            owner_ids = config.OWNER_IDS
        )
        self._extensions = [m.name for m in iter_modules(['modules'], prefix='modules.')]
        self._extensions.append("jishaku")
        self.logger = logger

    async def on_ready(self):
        print(f"Logged in as {self.user}.")

    async def setup_hook(self):

        for extension in self._extensions:
            try:
                await self.load_extension(extension)
            except:
                self.logger.error(f"Unable to load extension {extension}.")
                traceback.print_exc()
            else:
                self.logger.info(f"Loaded extension {extension}.")

        await utils.set_up_database(self)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        traceback.print_exc()

        # TODO: Add auto status updater 

bot = QueryBot()

load_dotenv()

async def main():
    async with bot:
        await bot.start(os.getenv('TOKEN'))

asyncio.run(main())
