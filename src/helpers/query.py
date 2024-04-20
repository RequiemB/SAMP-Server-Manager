from __future__ import annotations

from samp_query import Client, ServerInfo

import trio
import trio_asyncio
import struct

from typing import Optional, TYPE_CHECKING
from ._types import ServerData
from .errors import ServerOffline

if TYPE_CHECKING:
    from bot import QueryBot

TIMEOUT = 5

class Query:
    def __init__(self, bot: QueryBot) -> None:
        self.bot = bot

    async def send_rcon_command(self, client: Client, command: str) -> str:
        response = await trio_asyncio.trio_as_aio(client.rcon)(command) # type: ignore
        return response

    async def _connect(self, host: str, port: int, *, rcon_password: Optional[str] = None, retry: Optional[bool] = True) -> Client:
        client = Client(host, int(port), rcon_password)

        tries = 0

        while (tries < 3): # Retrying thrice
            try:
                with trio.fail_after(TIMEOUT - 2):
                    ping = await client.ping()

            except (trio.TooSlowError, ConnectionRefusedError, ConnectionResetError):
                if not retry:
                    break
                else:
                    tries += 1
                    await trio.sleep(1)

            else:
                return client # Return the client if the server is responsive so that the exception isn't raised
            
        raise ServerOffline(host, port)

    async def _get_server_data(self, host: str, port: int, *, retry: Optional[bool] = True) -> ServerData:
        client = await self.connect(host, port, rcon_password=None, retry=retry)

        try:
            with trio.fail_after(TIMEOUT): 
                info = await client.info()
        except trio.TooSlowError: # We didn't receive info from the server, there is nothing to send so raise ServerOffline
            raise ServerOffline(host, port)
        
        rules = await client.rules()
        try:
            with trio.fail_after(TIMEOUT):
                players = await client.players()
        except (trio.TooSlowError, struct.error): # error while unpacking player data received from the server
            players = None

        data: ServerData = {
            "ip": host,
            "port": port,
            "info": info,
            "rules": rules,
            "players": players
        }
        
        return data
    
    async def _get_server_info(self, host: str, port: int, *, retry: bool = True) -> ServerInfo: # This is different from get_server_data as this only requests for info
        client = await self.connect(host, port, retry=retry)
        info = await client.info()

        return info

    async def connect(self, host: str, port: int, *, rcon_password: Optional[str] = None, retry: Optional[bool] = True) -> Client:
        return await self._connect(host, port, rcon_password=rcon_password, retry=retry)

    async def get_server_data(self, host: str, port: int, *, retry: bool = True) -> ServerData:
        return await trio_asyncio.trio_as_aio(self._get_server_data)(host, port, retry=retry) # type: ignore
    
    async def get_server_info(self, host: str, port: int, *, retry: bool = True) -> ServerInfo:
        return await trio_asyncio.trio_as_aio(self._get_server_info)(host, port, retry=retry) # type: ignore