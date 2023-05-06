from samp_query import Client

import discord

import asyncio
import asqlite
import trio
import trio_asyncio


def is_ip(address: str):
    ip = re.compile(ip_regex)
    return re.search(ip, address)

async def _get_server_info(ip: str, port: int):

    server = Client(ip, int(port))

    assert server is not None

    ping = await server.ping()
    info = await server.info()

    return ping, info

async def get_server_info(ip: str, port: int):
    return await trio_asyncio.trio_as_aio(_get_server_info)(ip, port)

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
                PORT INT NOT NULL,
                INTERVAL INT,
                FRACTION CHAR(6),
                channel_id INT
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
                message_id INT NOT NULL
            );"""
            await cursor.execute(query)
            await conn.commit()
            bot.logger.info("RCON database has been set up at database/query.db.")

        # Logs

        await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' and name='Logs'")
        table = await cursor.fetchone()
        if table is None:
            query = """CREATE TABLE Logs (
                guild_id INT NOT NULL,
                CURRENT INT
            );"""
            await cursor.execute(query)
            await conn.commit()
            bot.logger.info("Logs has been set up at database/query.db")

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

async def format_command_mention_from_command(bot, parent, sub_command):
    commands = await bot.tree.fetch_commands()
    for command in commands:
        if command.name == parent:
            return f"</{parent} {sub_command}:{command.id}>"

    return ""

def format_command_mention_from_interaction(interaction):
    data = interaction.data
    id = data['id']
    name = interaction.command.qualified_name

    return f"</{name}:{id}>"

def format_time(duration):
    raw_duration = duration
    fmt = list(duration)
    fraction = None
    if "m" not in fmt and "s" not in fmt:
        return "", ""
    if "m" in fmt and "s" in fmt:
        return "", ""
    if "s" in fmt:
        fraction = "s"
        time = int(duration.replace("s", ""))
        duration = time
    elif "m" in fmt:
        fraction = "m"
        time = int(duration.replace("m", ""))
        duration = time * 60


    if duration < 30 and fraction == "s":
        return "error", ""
    if fraction == "m":
        raw_duration = int(raw_duration.replace("m", ""))   
        if raw_duration > 30:
            return "error", ""
    
    if fraction == "s":
        fraction = "seconds"
    else:
        fraction = "minutes"

    return duration, fraction


    

    