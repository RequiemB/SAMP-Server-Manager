from __future__ import annotations

import discord
from discord.ext import commands, tasks
from discord import app_commands

import traceback
import asqlite
import aiohttp
import logging

from struct import error as structerror
from helpers import (
    config,
    status,
    query,
    utils,
    log,
    chart,
    ServerOffline
)
from pkgutil import iter_modules
from typing import Dict, Optional, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from samp_query import Client
    
    from helpers import _types
    ServerData = _types.ServerData

class QueryBotTree(app_commands.CommandTree):
    def __init__(self, bot: QueryBot) -> None:
        self.bot = bot
        super().__init__(self.bot)
        self.application_commands: Dict[Optional[int], List[app_commands.AppCommand]] = {}

    # https://gist.github.com/LeoCx1000/021dc52981299b95ea7790416e4f5ca4
    
    async def sync(self, *, guild: Optional[discord.abc.Snowflake] = None):
        """Method overwritten to store the commands."""
        ret = await super().sync(guild=guild)
        self.application_commands[guild.id if guild else None] = ret
        return ret

    async def fetch_commands(self, *, guild: Optional[discord.abc.Snowflake] = None):
        """Method overwritten to store the commands."""
        ret = await super().fetch_commands(guild=guild)
        self.application_commands[guild.id if guild else None] = ret
        return ret

    async def find_mention_for(
        self,
        command: app_commands.Command | app_commands.Group | str,
        *,
        guild: Optional[discord.abc.Snowflake] = None,
    ) -> Optional[str]:
        """Retrieves the mention of an AppCommand given a specific command name, and optionally, a guild.
        Parameters
        ----------
        name: Union[:class:`app_commands.Command`, :class:`app_commands.Group`, str]
            The command which it's mention we will attempt to retrieve.
        guild: Optional[:class:`discord.abc.Snowflake`]
            The scope (guild) from which to retrieve the commands from. If None is given or not passed,
            only the global scope will be searched, however the global scope will also be searched if
            a guild is passed.
        """

        check_global = self.fallback_to_global is True or guild is not None

        if isinstance(command, str):
            # Try and find a command by that name. discord.py does not return children from tree.get_command, but
            # using walk_commands and utils.get is a simple way around that.
            _command = discord.utils.get(self.walk_commands(guild=guild), qualified_name=command)

            if check_global and not _command:
                _command = discord.utils.get(self.walk_commands(), qualified_name=command)

        else:
            _command = command

        if not _command:
            return None

        if guild:
            try:
                local_commands = self.application_commands[guild.id]
            except KeyError:
                local_commands = await self.fetch_commands(guild=guild)

            app_command_found = discord.utils.get(local_commands, name=(_command.root_parent or _command).name)

        else:
            app_command_found = None

        if check_global and not app_command_found:
            try:
                global_commands = self.application_commands[None]
            except KeyError:
                global_commands = await self.fetch_commands()

            app_command_found = discord.utils.get(global_commands, name=(_command.root_parent or _command).name)

        if not app_command_found:
            return None

        return f"</{_command.qualified_name}:{app_command_found.id}>"

    async def on_error(self, interaction: discord.Interaction[QueryBot], error: app_commands.AppCommandError, /) -> None:
        self.bot.logger.error("Ignoring exception in on_app_command_error", exc_info=error)
        try:
            # Log the error in the console and discord
            tb = "".join(traceback.format_exception(exc=error)) # type: ignore
            await self.bot.log_error_via_webhook("on_app_command_error", tb)
        except Exception: # If this fails, it already logged to console so ignore
            pass

        await interaction.response.send_message("An error occured while executing your command. If this persists, join the [support server](https://discord.gg/GK8wPNjJXy).")

class QueryBot(commands.Bot):
    def __init__(self) -> None:
        self.query = query.Query(self)
        self._extensions = [m.name for m in iter_modules(['modules'], prefix='modules.')]
        self._extensions.append("jishaku") # For debugging purposes
        self._status = status.Status(self)
        self.rcon_logged: Dict[int, Dict[int, Client]] = {}
        self.server_data: Dict[int, ServerData] = {} # Server info per guild
        self.chart = chart.Chart(self)

        self._intents = discord.Intents.default()
        self._intents.message_content = True # For the on_message and on_message_delete events, if you don't want those events to run this can be disabled
        self._intents.members = True

        super().__init__(
            command_prefix = config.PREFIX,
            intents = self._intents,
            owner_id = config.OWNER_IDS,
            status=discord.Status.dnd, 
            activity=discord.Activity(name="your SAMP server", type=discord.ActivityType.watching),
            tree_cls=QueryBotTree
        )
        self.tree: QueryBotTree 

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user}.", flush=True)

        if self.logger_webhook and self.user:
            timestamp = discord.utils.format_dt(self.start_time, style="R")
            await self.logger_webhook.send(f"The bot was initialized {timestamp}.", username=f"{self.user.name} Logger", avatar_url=self.user.avatar.url if self.user.avatar else None)

    async def setup_hook(self) -> None:
        self.pool = await asqlite.create_pool("./database/query.db")
        self.logger.info("Created database connection pool.")
        async with self.pool.acquire() as conn:
            await utils.set_up_database(conn)
        
        for extension in self._extensions:
            try:
                await self.load_extension(extension)
            except Exception:
                self.logger.error(f"Unable to load extension {extension}.")
                traceback.print_exc()
            else:
                self.logger.info(f"Loaded extension {extension}.")

        self._session = aiohttp.ClientSession()
        self.start_time = discord.utils.utcnow()

        self.startup_task.start() # Start the start-up task in an async context

        self.logger_webhook = None

        if config.LOGGER_WEBHOOK is not None:
            try:
                self.logger_webhook = discord.Webhook.from_url(config.LOGGER_WEBHOOK, session=self._session)
            except ValueError: # Invalid Webhook URL
                self.logger.warning("Invalid Webhook URL was provided. Either set it to None or provide a valid webhook URL.")
                self.logger_webhook = None
    
    def setup_logger(self):
        self.logger = logging.getLogger("discord")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        logging.basicConfig(filename='logs.log', encoding='utf-8', level=logging.DEBUG)

        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(log.Logger()) 
        self.logger.addHandler(handler)
    
    async def log_error_via_webhook(self, func_name: str, tb: str, *args, **kwargs) -> None:
        header = f"Ignoring exception in {func_name}"
        extra = kwargs.get("extra", None) # Something extra to add to the header
        if extra is not None:
            header = f"{header} {extra}"

        if self.logger_webhook is not None:
            try:
                assert self.user
                e = discord.Embed(title="Exception Logger", color=discord.Color.red(), timestamp=discord.utils.utcnow())
                e.description = f"{header}.\n\n"
                e.description += f"```py\n{tb}```"
                await self.logger_webhook.send(embed=e, username=f"{self.user.name} Logger", avatar_url=self.user.avatar.url if self.user.avatar else None)
            except Exception:
                pass
            else: 
                return

        self.logger.error(header) # If a webhook isn't set or if the sending raises an exception, log the error in the console
        print(tb)

    @tasks.loop(count=1) 
    async def startup_task(self):      # The task which starts the all the tasks and auto-syncs the commands (optional)
        await self._status.start_global_status()
        self.logger.info("Global querying task was started.")
        self._status.update_stats.add_exception_type(structerror, ServerOffline)
        self._status.update_stats.start()
        self.logger.info("update_stats task was started.")

#       Uncomment these lines if you want commands to be auto-synced (not recommended, you can use the text command to auto-sync)
#        self.command_list = await self.tree.sync()
#        self.logger.info("Synced all application commands globally.")

    @startup_task.before_loop
    async def before_startup_task(self):
        await self.wait_until_ready()