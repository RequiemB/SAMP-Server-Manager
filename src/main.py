import discord
from discord.ext import commands
from discord import app_commands

import asqlite
import traceback
import asyncio
import os
import logging
import trio
import trio_asyncio

from helpers import (
    config,
    log, 
    utils,
    status
)
from pkgutil import iter_modules
from dotenv import load_dotenv

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
logger.propagate = False

handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
handler.setFormatter(log.Logger()) 
logger.addHandler(handler)

class QueryBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix = config.PREFIX,
            intents = discord.Intents.all(),
            owner_ids = config.OWNER_IDS,
            status=discord.Status.dnd, 
            activity=discord.Activity(name="your SAMP server", type=discord.ActivityType.watching),
        )
        self._extensions = [m.name for m in iter_modules(['modules'], prefix='modules.')]
        self._extensions.append("jishaku")
        self.logger = logger
        self._status = status.Status(self)
        self.rcon_logged = {}

    async def on_ready(self):
        print(f"Logged in as {self.user}.", flush=True)

    async def setup_hook(self):

        for extension in self._extensions:
            try:
                await self.load_extension(extension)
            except:
                self.logger.error(f"Unable to load extension {extension}.")
                traceback.print_exc()
            else:
                self.logger.info(f"Loaded extension {extension}.")

bot = QueryBot()

load_dotenv()

async def setup():
    async with bot:
        await bot.start(os.getenv('TOKEN'))

async def cleanup():
    async with bot:
        await bot.close()

    bot.logger.info("Terminating all processes and stopping the loop...")

    await asyncio.sleep(1)

async def main():
    try:
        await trio_asyncio.aio_as_trio(setup)()
    except KeyboardInterrupt:
        await trio_asyncio.aio_as_trio(cleanup)()

trio_asyncio.run(main)