import discord
from discord.ext import commands
from discord import app_commands

import traceback
import asyncio
import os
import logging
import trio_asyncio
import asqlite

from helpers import (
    config,
    log, 
    status,
    query
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
    def __init__(self) -> None:
        self.query = query.Query(self)
        self._extensions = [m.name for m in iter_modules(['modules'], prefix='modules.')]
        self._extensions.append("jishaku")
        self.logger = logger
        self._status = status.Status(self)
        self.rcon_logged = {}
        self.pool = None

        super().__init__(
            command_prefix = config.PREFIX,
            intents = discord.Intents.all(),
            owner_ids = config.OWNER_IDS,
            status=discord.Status.dnd, 
            activity=discord.Activity(name="your SAMP server", type=discord.ActivityType.watching),
        )

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user}.", flush=True)

    async def setup_hook(self) -> None:
        self.pool = await asqlite.create_pool("./database/query.db")
        self.logger.info("Created database connection pool.")

        self.command_list = await self.tree.fetch_commands()
        
        for extension in self._extensions:
            try:
                await self.load_extension(extension)
            except:
                self.logger.error(f"Unable to load extension {extension}.")
                traceback.print_exc()
            else:
                self.logger.info(f"Loaded extension {extension}.")

bot = QueryBot()

@bot.command() 
@commands.is_owner()
async def sync(ctx: commands.Context) -> None:
    try: 
        bot.command_list = await bot.tree.sync()

        await ctx.send(f"Synced {len(bot.command_list)} commands.")
    except:
        pass

load_dotenv()

async def setup() -> None:
    async with bot:
        await bot.start(os.getenv('TOKEN'))

async def cleanup() -> None:
    async with bot:
        await bot.close()

    bot.logger.info("Terminating all processes and stopping the loop...")

    await bot.pool.close()

    await asyncio.sleep(1)

async def main() -> None:
    try:
        await trio_asyncio.aio_as_trio(setup)()
    except KeyboardInterrupt:
        await trio_asyncio.aio_as_trio(cleanup)()

trio_asyncio.run(main)