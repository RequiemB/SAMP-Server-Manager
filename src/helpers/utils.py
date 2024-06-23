from __future__ import annotations

import re
import discord

from typing import Literal
from datetime import datetime
from helpers import config, _types

from typing import List, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from samp_query import RuleList
    from asqlite import ProxiedConnection
    from bot import QueryBot
    from sqlite3 import Row

    from helpers import _types
    ServerData = _types.ServerData

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def get_uptime_emoji(emoji: Literal['GREEN', 'ORANGE', 'RED']) -> str:
    match emoji:
        case 'GREEN':
            return config.GREEN_UPTIME if config.GREEN_UPTIME else config.DEFAULT_GREEN_UPTIME
        case 'ORANGE':
            return config.ORANGE_UPTIME if config.ORANGE_UPTIME else config.DEFAULT_ORANGE_UPTIME
        case 'RED':
            return config.RED_UPTIME if config.RED_UPTIME else config.DEFAULT_RED_UPTIME
        
def get_result_emoji(_type: Literal['success', 'failure', 'timeout'] = 'success') -> str:
    if _type == 'success':
        return config.REACTION_SUCCESS if config.REACTION_SUCCESS else config.DEFAULT_REACTION_SUCCESS
    elif _type == 'timeout':
        return config.REACTION_TIMEOUT if config.REACTION_TIMEOUT else config.DEFAULT_REACTION_TIMEOUT
    else:
        return config.REACTION_FAILURE if config.REACTION_FAILURE else config.DEFAULT_REACTION_FAILURE
    
def get_cog_emoji(cog: str) -> str:
    return get_result_emoji('success')

def is_ip(address: str) -> bool:
    try:
        ip, port = address.split(":")
        octets = map(int, ip.split("."))
        octets = [i for i in octets]
        port = int(port)
    except ValueError:
        return False

    return all([
        len(octets) == 4,
        port > 1023 and port < 65536,
        len([octet for i, octet in enumerate(octets) if ((octet >= 0 if i != 0 else octet > 0) and octet <= 255)]) == 4
    ])

async def set_up_database(conn: ProxiedConnection) -> None:
    """Function to set up the database tables."""

    sql_script = """
        CREATE TABLE IF NOT EXISTS query (
            guild_id INTEGER NOT NULL,
            ip CHAR(45),
            port SMALLINT,
            interval SMALLINT,
            channel_id INT,
            logs INT,
            message_id INT,
            timezone CHAR(40),
            PRIMARY KEY (guild_id)
        );

        CREATE TABLE IF NOT EXISTS stats (
            ip CHAR(45),
            port SMALLINT,
            highest_playercount SMALLINT,
            peak_hour CHAR(10),
            PRIMARY KEY (ip, port)
        );

        CREATE TABLE IF NOT EXISTS dailystats (
            guild_id INT,
            ip CHAR(45),
            port SMALLINT,
            playercount SMALLINT,
            date DATE,
            time CHAR(6),
            status CHAR(8)
        );
    """ 
    await conn.executescript(sql_script)
    await conn.commit()

def command_mention_from_interaction(interaction: discord.Interaction[QueryBot]) -> str:
    id = interaction.data['id'] # type: ignore
    name = interaction.command.qualified_name # type: ignore

    return f"</{name}:{id}>"

def format_time(interval) -> Optional[int]:
    pattern = '^(30|[5-9]|[1-2][0-9])m$'

    match = re.match(pattern, interval)

    if not match:
        return None

    duration = int(match.group().replace("m", ""))  # Remove the m in the duration and return it
    return duration

class StatusView(discord.ui.View):
    def __init__(self, data: ServerData) -> None:
        self.server_name: Optional[str] = data["info"].name if data["info"] else None
        self.rules: Optional[RuleList] = data.get("rules", None)
        self.player_list: Optional[str] = None
        self.ip: str = data["ip"]
        self.port: int = data["port"]
        self.current_players: int = data["info"].players # type: ignore
        self.stats_data: bool = True
        super().__init__(timeout=None)

    def run_check(self) -> None:
        """Check to determine whether to keep the buttons or not."""
        if not self.player_list:
            self.remove_item(self.button_playerlist)

        if not self.rules:
            self.remove_item(self.button_rules)

        if not self.stats_data:
            self.remove_item(self.button_stats)

    @discord.ui.button(label="Player List", style=discord.ButtonStyle.blurple)
    async def button_playerlist(self, interaction: discord.Interaction[QueryBot], _button: discord.ui.Button) -> None:
        e = discord.Embed(
            title = f"List of players online in {self.server_name}",
            description = self.player_list,
            color = discord.Color.blue(),
            timestamp = discord.utils.utcnow()
        )

        await interaction.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="Server Rules", style=discord.ButtonStyle.blurple)
    async def button_rules(self, interaction: discord.Interaction[QueryBot], _button: discord.ui.Button) -> None:
        assert self.rules
        
        e = discord.Embed(
            title = f"Rules of {self.server_name}",
            color = discord.Color.blue(),
            timestamp = discord.utils.utcnow()
        )

        for rule in self.rules.rules:
            e.add_field(name=rule.name, value=rule.value)

        await interaction.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="Server Statistics", style=discord.ButtonStyle.blurple)
    async def button_stats(self, interaction: discord.Interaction[QueryBot], _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        e = discord.Embed(
            title=f"Statistics of {self.server_name}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        async with interaction.client.pool.acquire() as conn:
            stats = await conn.fetchone("SELECT highest_playercount, peak_hour FROM stats WHERE ip = ? AND port = ?", (self.ip, self.port,))
            uptime_data = await conn.fetchall("SELECT status FROM dailystats WHERE ip = ? AND port = ?", (self.ip, self.port,))
        
            highest_playerc = stats[0] 
            peak_hour = stats[1]
    
            if not highest_playerc or self.current_players > highest_playerc: 
                peak_hour = get_peak_hour() if highest_playerc else None
                query, params = "UPDATE stats SET highest_playercount = ?, peak_hour = ? WHERE ip = ? AND port = ?", (self.current_players, peak_hour, self.ip, self.port,)
                await conn.execute(query, params)
                await conn.commit()

        uptime_percentage = calc_uptime(uptime_data)

        e.add_field(name="Highest Recorded Player Count", value=highest_playerc)
        e.add_field(name="Current Players Online", value=self.current_players)
        e.add_field(name="Recorded Peak Time", value=f"`{peak_hour}`", inline=False)
        e.add_field(name="Uptime Percentage", value=uptime_percentage, inline=True)

        await interaction.followup.send(embed=e)        

def make_svinfo_embed(data: ServerData, *, server_stats: bool = True) -> Tuple[discord.Embed, StatusView]:
    info = data["info"]
    rules = data["rules"]

    assert info

    e = discord.Embed(
        title = info.name,
        description = f"Basic information of {info.name}:",
        color = discord.Color.blue(),
        timestamp = discord.utils.utcnow()
    )

    version = [rule.value for rule in rules.rules if rule.name == "version"][0]
    weburl = [rule.value for rule in rules.rules if rule.name == "weburl"][0]

    if not weburl.startswith("http"):
        weburl = f"https://{weburl}"

    ip = data["ip"]
    port = data["port"]

    e.add_field(name="IP Address", value=f"{ip}:{port}")
    e.add_field(name="Gamemode", value=info.gamemode)
    e.add_field(name="Players", value=f"{info.players}/{info.max_players}")
    e.add_field(name="Web URL", value=f"{weburl}")
    e.add_field(name="Language", value=info.language)
    e.add_field(name="Version", value=version)

    status_view = StatusView(data)    

    if data["players"]:
        if len(data["players"].players) != 0:

            maxlen = max(len(player.name) for player in data["players"].players) + 4

            player_list = f"{'Name':<{maxlen}}{'Score':>2}\n"

            for player in data["players"].players:
                player_list += f"{player.name:<{maxlen}}{player.score:>2}\n"

            player_list = f"```{player_list}```\n"

            if len(player_list) > 4096: # Can't display the playerlist as it exceeds max description char limit
                player_list = None

            elif len(player_list) > 1024 and len(player_list) < 4096:
                status_view.player_list = player_list

            else:
                e.add_field(name="Player List", value=player_list, inline=False)

    status_view.stats_data = server_stats
    status_view.run_check()
        
    return e, status_view

def calc_uptime(data: List[Row]) -> str:
    total_status, total_uptime = len(data), 0
    for row in data:
        if row[0] == "online":
            total_uptime += 1

    try:
        percentage = (total_uptime / total_status) * 100
    except ZeroDivisionError:
        return "Hasn't been calculated yet."
    if percentage > 95:
        emoji = get_uptime_emoji('GREEN')
        return f"{emoji} {percentage:.2f}%"
    elif percentage >= 90:
        emoji = get_uptime_emoji('ORANGE')
        return f"{emoji} {percentage:.2f}%"
    else:
        emoji = get_uptime_emoji('RED')
        return f"{emoji} {percentage:.2f}%"

def get_peak_hour() -> str:
    current_hour = datetime.now().hour
    indicator = "am" if current_hour < 12 else "pm"
    current_hour %= 12
    hour = current_hour if current_hour else 12 # To display 00:00 as 12 am
    return f"{hour}{indicator}"

def get_month_name(month: int) -> str:
    try:
        return MONTHS[month-1]
    except IndexError:
        raise IndexError("Invalid month was given.")
        

    

    