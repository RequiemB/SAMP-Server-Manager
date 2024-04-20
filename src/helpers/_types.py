from typing import TypedDict
from samp_query import ServerInfo, RuleList, PlayerList

class ServerData(TypedDict):
    ip: str
    port: int
    info: ServerInfo
    rules: RuleList
    players: PlayerList | None
