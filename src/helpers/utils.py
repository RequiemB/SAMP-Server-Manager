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
            guild_id INTEGER PRIMARY KEY NOT NULL,
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


    

    