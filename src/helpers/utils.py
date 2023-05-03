from samp_query import Client

import re
import asyncio
import asqlite
import traceback
import trio

from .errors import *

ip_regex = "^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.){3}(25[0-5]|(2[0-4]|1\d|[1-9]|)\d)$"

host_uses_signal_set_wakeup_fd = True

def is_ip(address: str):
    ip = re.compile(ip_regex)
    return re.search(ip, address)

async def _get_server_info(ip: str, port: int):
    if not is_ip(ip):
        raise InvalidIP(ip)

    server = Client(ip, int(port))

    assert server is not None

    try:
        ping = await server.ping()
        info = await server.info()
    except Exception as e:
        print(f"{e.__class__}: {e}", flush=True)

    return ping, info

async def get_server_info(ip: str, port: int):
    return trio.run(_get_server_info, ip, port)

async def set_up_database(bot):
    conn = await asqlite.connect('./database/query.db')
    async with conn.cursor() as cursor:

        # Basic Query Info

        await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='query'")
        table = await cursor.fetchone()
        if table is None:
            query = """CREATE TABLE query (
                guild_id INT NOT NULL,
                IP CHAR(45) NOT NULL,
                PORT INT NOT NULL
            );"""
            await cursor.execute(query)
            await conn.commit()
            bot.logger.info("Query database has been set up at database/query.db.")

        # RCON

        await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' and name='RCON'")
        table = await cursor.fetchone()
        if table is None:
            query = """CREATE TABLE RCON (
                guild_id INT NOT NULL,
                PASS CHAR(32) NOT NULL
            );"""
            await cursor.execute(query)
            await conn.commit()
            bot.logger.info("RCON database has been set up at database/query.db.")

    await conn.close()

async def execute_query(query: str):
    conn = await asqlite.connect('./database/query.db')
    cursor = await conn.cursor()
    await cursor.execute(query)
    
    return conn, cursor

async def configure_server_for_guild(guild, ip, port):
    conn = await asqlite.connect('./database/query.db')
    cursor = await conn.cursor()
    await cursor.execute("INSERT INTO query(guild_id, IP, PORT) VALUES (?, ?, ?)", (guild.id, ip, port))
    await conn.commit()
    await conn.close()

async def update_server_for_guild(guild, ip, port):
    conn = await asqlite.connect('./database/query.db')
    cursor = await conn.cursor()
    await cursor.execute("UPDATE query SET IP = ?, PORT = ? where guild_id = ?", (ip, port, guild.id))
    await conn.commit()
    await conn.close()

async def format_command_mention_from_command(bot, parent, sub_command, guild=None):
    commands = await bot.tree.fetch_commands(guild=guild)
    for command in commands:
        if command.name == parent:
            return f"</{parent} {sub_command}:{command.id}>"

    return ""

def format_command_mention_from_interaction(interaction):
    data = interaction.data
    id = data['id']
    name = interaction.command.qualified_name

    return f"</{name}:{id}>"


    

    