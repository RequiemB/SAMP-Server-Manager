from samp_query import Client

import re
import asqlite

from .errors import *

ip_regex = "?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"

def is_ip(address: str):
    ip = re.compile(ip_regex)
    return re.match(ip, address)

async def get_server_info(ip: str, port: int):
    if not is_ip(ip):
        raise InvalidIP(ip)

    try:
        server = Client(ip, int(port))
    except:
        pass

    assert server is not None
    
    ping = await server.ping()
    info = await server.info()

    return ping, info

async def set_up_database(bot):
    conn = await asqlite.connect('./database/query.db')
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='query'")
        table = await cursor.fetchone()
        if table is None:
            query = """CREATE TABLE query (
                guild_id INTEGER PRIMARY KEY,
                ip VARCHAR(10),
                port VARCHAR(4)
            );"""
            await cursor.execute(query)
            await conn.commit()
            bot.logger.info("Database has been set up at database/query.db.")


    

    