from bot import QueryBot

import discord
from discord.ext import commands

import traceback
import asyncio
import os
import trio_asyncio

from dotenv import load_dotenv

bot = QueryBot()

@bot.command() 
@commands.is_owner()
async def sync(ctx: commands.Context) -> None:
    try: 
        synced = await bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} commands.")
    except Exception:
        e = discord.Embed(
            title = "Exception",
            color = discord.Color.red(),
            timestamp = discord.utils.utcnow()
        )
        e.description = f"```py\n{traceback.format_exc()}```"
        await ctx.send(embed=e)

load_dotenv()

async def setup() -> None:
    bot.setup_logger()
    token = os.getenv('TOKEN')
    if token:
        async with bot:
            await bot.start(token)
    else:
        raise RuntimeError("No login token was provided in the env file.")

async def cleanup() -> None:
    async with bot:
        await bot.close()

    bot.logger.info("Terminating all processes and stopping the loop...")

    # Check for running tasks before closing the pool
    for guild_id in bot._status.guild_status_tasks:
        if bot._status.guild_status_tasks[guild_id].is_running():
            bot._status.guild_status_tasks[guild_id].cancel()

    await asyncio.sleep(1)

    await bot.pool.close()
    await bot._session.close()

async def main() -> None:
    try:
        await trio_asyncio.aio_as_trio(setup)() # type: ignore # The module isn't typed properly
    except KeyboardInterrupt:
        await trio_asyncio.aio_as_trio(cleanup)() # type: ignore

trio_asyncio.run(main) # type: ignore