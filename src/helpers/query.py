from samp_query import (
    Client,
    InvalidRCONPassword,
    RCONDisabled
)

import discord
import trio

class ServerOffline(Exception):
    pass

class Query:
    TIMEOUT = 5

    def __init__(self, bot):
        self.bot = bot

    async def is_rcon_enabled(self, host: str, port: int, rcon_password: str):
        client = await self.connect(host, port, rcon_password)

        try:
            await client.rcon("echo")
        except RCONDisabled:
            return False
        else:
            return True

    async def _connect(self, host: str, port: int, rcon_password: str = None):
        client = Client(host, int(port), rcon_password)

        try:
            with trio.fail_after(TIMEOUT):
                ping = await client.ping()

        except (trio.TooSlowError, ConnectionRefusedError):
            raise ServerOffline
        
        return client

    async def _get_server_data(self, host: str, port: int):

        client = await self.connect(host, port)

        ping = await client.ping()
        info = await client.info()
        is_omp = await client.is_omp()
        rules = await client.rules()

        data = {}

        data["ping"] = ping
        data["info"] = info
        data["is_omp"] = is_omp
        data["rules"] = rules

        return data

    async def connect(self, host: str, port: int, rcon_password: str = None):
        return await trio_asyncio.trio_as_aio(self._connect)(host, port, rcon_password)

    async def get_server_data(self, host: str, port: int):
        return await trio_asyncio.trio_as_aio(self._get_server_data)(host, port)