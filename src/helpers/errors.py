class StatusChannelNotFound(Exception):
    """Exception raised when the status channel is not found."""
    def __init__(self, guild_id: int) -> None:
        super().__init__(f"Status channel set up at {guild_id} was not found.")

class ServerOffline(Exception):
    "Raised when the server is unresponsive."
    def __init__(self, host: str, port: int) -> None:
        super().__init__(f"{host}:{port} is offline.")

class ChartNotFound(Exception):
    "Raised when the chart specified by the user is not found."