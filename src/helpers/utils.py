import re
import discord

ip_re = re.compile('^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.){3}(25[0-5]|(2[0-4]|1\d|[1-9]|)\d)$')

def is_ip(address: str):
    return re.search(ip_re, address)

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

def make_svinfo_embed(ip: str, port: int, data: dict):
    info = data["info"]
    rules = data["rules"]

    e = discord.Embed(
        title = info.name,
        description = f"Basic information of {info.name}:",
        color = discord.Color.blue(),
        timestamp = discord.utils.utcnow()
    )

    for rule in rules.rules:
        if rule.name == "version":
            version = rule.value

    e.add_field(name="IP Address", value=f"{ip}:{port}")
    e.add_field(name="Gamemode", value=info.gamemode)
    e.add_field(name="Players", value=f"{info.players}/{info.max_players}")
    e.add_field(name="Latency", value=f"{data['ping'] * 1000:.0f}ms")
    e.add_field(name="Language", value=info.language)
    e.add_field(name="Version", value=version)

    if len(data["players"].players) != 0:

        maxlen = max(len(player.name) for player in data["players"].players) + 4
    
        player_list = f"{'#':<2}{'Name':^{maxlen}}{'Score':>2}\n"
    
        for i, player in enumerate(data["players"].players):
            if i < 10:
                player_list += f"{i+1:<2}{player.name:^{maxlen}}{player.score:>2}\n"
            else:
                player_list += f"{i+1:<1}{player.name:^{maxlen}}{player.score:>2}\n"
                
        e.add_field(name="Players", value=f"```{player_list}```", inline=False)

    return e

    

    