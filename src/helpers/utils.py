import re

ip = re.compile('^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.){3}(25[0-5]|(2[0-4]|1\d|[1-9]|)\d)$')

def is_ip(address: str):
    return re.search(ip, address)

async def set_up_database(bot):
    async with bot.pool.acquire() as conn:

        # Basic Query Info

        query = """CREATE TABLE IF NOT EXISTS query (
            guild_id INTEGER NOT NULL,
            ip CHAR(45),
            port INTEGER,
            interval INTEGER,
            channel_id INT
        )"""

        await conn.execute(query)

        # RCON Logs

        query = """CREATE TABLE IF NOT EXISTS logs (
            guild_id INTEGER NOT NULL,
            user_id INTEGER,
            action INTEGER,
            time BLOB
            command CHAR(45)
        )"""

        await conn.execute(query)

def command_mention_from_tree(bot, _type, fmt):
    commands = bot.command_list
    parent = commands[_type]        # _type 0 is RCON and 1 is Server
    return f"</{fmt}:{parent.id}>"

def command_mention_from_interaction(interaction):
    id = interaction.data['id']
    name = interaction.command.qualified_name

    return f"</{name}:{id}>"

def format_time(interval):
    pattern = '^(30|[5-9]|[1-2][0-9])m$'

    match = re.match(pattern, interval)

    if not match:
        return ""

    duration = int(match.group().replace("m", ""))  # Remove the m in the duration and return it
    return duration


    

    