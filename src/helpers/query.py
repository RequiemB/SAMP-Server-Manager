from samp_query import Client

import trio
import trio_asyncio

TIMEOUT = 5

class ServerOffline(Exception):
    pass

class Query:
    def __init__(self, bot):
        self.bot = bot

    async def send_rcon_command(self, client: Client, command: str):
        response = await trio_asyncio.trio_as_aio(client.rcon)(command)
        return response

    async def _connect(self, host: str, port: int, rcon_password: str = None):
        client = Client(host, int(port), rcon_password)

        try:
            with trio.fail_after(TIMEOUT):
                ping = await client.ping()

        except (trio.TooSlowError, ConnectionRefusedError):
            return None
        
        return client

    async def _get_server_data(self, host: str, port: int):

        client = await self.connect(host, port)
        if client is None:
            tries = 1

            while (tries <= 3 and client is None): # Retrying thrice 
                await trio.sleep(5)
                
                tries += 1
                client = await self.connect(host, port)

            if client is None:
                raise ServerOffline

        ping = await client.ping()
        info = await client.info()
        is_omp = await client.is_omp()
        rules = await client.rules()
        players = await client.players()

        data = {}

        data["ping"] = ping
        data["info"] = info
        data["is_omp"] = is_omp
        data["rules"] = rules
        data["players"] = players

        return data

    async def connect(self, host: str, port: int, rcon_password: str = None):
        return await self._connect(host, port, rcon_password)

    async def get_server_data(self, host: str, port: int):
        return await trio_asyncio.trio_as_aio(self._get_server_data)(host, port)