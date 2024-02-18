from matplotlib import pyplot as plt

import discord
from discord.ext import commands, tasks

import asqlite

from datetime import datetime
from collections import deque
from .query import ServerOffline

time_points = []
player_counts = []

def plot_graph():
    plt.figure(figsize=(10, 6))  # Set figure size
    plt.plot(time_points, player_counts, marker='o', linestyle='-', color='b')  # Blue solid line with markers
    plt.grid(True, linestyle='--', alpha=0.7)  # Dashed grid lines with some transparency
    plt.title('SA-MP Server Player Count Over Time', fontsize=16)
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Player Count', fontsize=12)
    plt.legend(['Player Count'], loc='upper right')
    plt.gca().set_facecolor('#F5F5F5')  # Light gray background color
    plt.show()

#plot_graph()

class Chart:
    def __init__(self, bot: commands.Bot, guild: discord.Guild, max_time_points: int = 10):
        self.bot = bot
        self.guild = guild
        self.max_time_points = max_time_points

        self.time_points = deque(maxlen=self.max_time_points)
        self.player_counts = deque(maxlen=self.max_time_points)

    def is_chart_ready(self):
        return len(time_points) > 4 

    def make_chart(self):
        pass

    async def send_chart(self):
        pass


    @tasks.loop(hours=1, reconnect=True)
    async def get_player_count(self, host: str, port: int):
        self.time_points.append(datetime.now().strftime("%H:%M"))
        try:
            player_count, _ = self.bot.query.get_player_count(host, port)
        except ServerOffline:
            self.player_counts.append(0)
        else:
            self.player_counts.append(player_count)

        if self.is_chart_ready():
            await self.send_chart()
