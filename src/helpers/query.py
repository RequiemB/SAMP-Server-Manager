from samp_query import Client

import trio
import trio_asyncio

TIMEOUT = 5

class ServerOffline(Exception):
    "Raised when the server is unresponsive after 3 attempts."

class Query:
    def __init__(self, bot):
        self.bot = bot

    async def send_rcon_command(self, client: Client, command: str):
        response = await trio_asyncio.trio_as_aio(client.rcon)(command)
        return response

    async def _connect(self, host: str, port: int, rcon_password: str = None):
        client = Client(host, int(port), rcon_password)

        tries = 0

        while (tries < 3): # Retrying thrice
            try:
                with trio.fail_after(TIMEOUT):
                    ping = await client.ping()

            except (trio.TooSlowError, ConnectionRefusedError):
                tries += 1
                await trio.sleep(5)

            else:
                return client # Return the client if the server is responsive so that the exception isn't raised
            
        raise ServerOffline

    async def _get_server_data(self, host: str, port: int):
        client = await self.connect(host, port)

        ping = await client.ping()
        info = await client.info()
        rules = await client.rules()
        players = await client.players()

        data = {}

        data["ping"] = ping
        data["info"] = info
        data["rules"] = rules
        data["players"] = players

        return data
    
    async def _get_player_count(self, host: str, port: int):
        client = await self.connect(host, port)
        info = await client.info()

        return info.players, info.max_players

    async def connect(self, host: str, port: int, rcon_password: str = None):
        return await self._connect(host, port, rcon_password)

    async def get_server_data(self, host: str, port: int):
        return await trio_asyncio.trio_as_aio(self._get_server_data)(host, port)
    
    async def get_player_count(self, host: str, port: int):
        return await trio_asyncio.trio_as_aio(self._get_player_count)(host, port)