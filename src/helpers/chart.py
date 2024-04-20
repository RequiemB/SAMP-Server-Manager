from __future__ import annotations

import matplotlib
matplotlib.use('agg')
from matplotlib import pyplot as plt
plt.ioff()

import discord
import os

from enum import Enum
from typing import List, Dict, Union, TYPE_CHECKING
from .errors import ChartNotFound

if TYPE_CHECKING:
    from bot import QueryBot
    from sqlite3 import Row

# Modes for chart making
class Mode(Enum):
    MODE_MONTH = 1
    MODE_DAY = 2

class ChartData:
    """A class for storing chart data of a day."""
    def __init__(self) -> None:
        self.max_playercount: int = 0
        self.time_data: Dict[str, int] = {}

class Chart:
    def __init__(self, bot: QueryBot) -> None:
        self.bot = bot

    def chart_data_from_res(self, res: List[Row]) -> Dict[str, ChartData]:
        filtered: Dict[str, ChartData] = {}

        current_date = ""
        for i, data in enumerate(res):
            if not current_date: # In the first iteration, this if condition would run and the current_date would be the first date received
                current_date = data[1] # data[1] is the date
                chart_data = ChartData()

            if data[1] == current_date: # This if condition will keep on running until the date changes
                chart_data.time_data[data[2]] = data[0]
            else: # When the date changes, save it into the dictionary and move on to the next date
                chart_data.max_playercount = max([i for i in chart_data.time_data.values()])
                filtered[current_date] = chart_data

                current_date = data[1]
                chart_data = ChartData() # create new instance
                chart_data.time_data[data[2]] = data[0] # data[2] is the time in 'hour:minute:' format and data[0] is the playercount

            # Check if this is the last item
            if (len(res) - 1) == i:
                chart_data.max_playercount = max([i for i in chart_data.time_data.values()])
                filtered[current_date] = chart_data 
                
        return filtered
    
    def can_chart_be_made(self, data: Union[Dict[str, ChartData], ChartData], mode: Mode = Mode.MODE_MONTH) -> bool:
        if mode == Mode.MODE_MONTH:
            return len(data) >= 6 # type: ignore
        else:
            return len(data.time_data) >= 6 # type: ignore
    
    def get_logged_days(self, data: Dict[str, ChartData]) -> List[str]:
        days = []
        for key in data.keys():
            days.append("-".join(key.split("-")[::-1])) # Reverse the date

        return days
    
    def round_to_lowest_hundred(self, num: int) -> int: # Used for chart y tick increment
        num -= num % 100
        return num

    def get_y_ticks(self, num: List[int]) -> range:
        if max(num) <= 5:
            return range(0, 6, 1)
        
        if max(num) <= 10:
            return range(0, 11, 2)
        
        if max(num) <= 50:
            return range(0, 51, 5)
        
        # Y ticks if the max playercount is bigger than 100

        if max(num) >= 100:
            return range(0, max(num) + 1, self.round_to_lowest_hundred(max(num)) // 10)
        
        return range(0, max(num) + 10, 10) # > 10 and < 100
        
    def make_chart_from_data(self, guild_id: int, header: str, data: Dict[str, ChartData], mode: Mode = Mode.MODE_MONTH) -> discord.File:
        if mode == Mode.MODE_MONTH:
            player_counts, dates = [], []
            for k, v in data.items():
                date = k[5:].split("-")[::-1]
                dates.append("-".join(date)) # Remove the year and put it in the format of DD-MM
                player_counts.append(v.max_playercount)

#            current = 15
#            for x in range(20):
#                dates.append(f"{current}-04")
#                current += 1
#                player_counts.append(random.choice([42, 12, 22, 1, 0, 29, 55, 23]))

            x_axis = dates
            x_label = "Dates"
        
        else:
            day_data = data.get(header, None)
            if not day_data:
                raise ChartNotFound(f"Data for {header} wasn't found.")
            player_counts, time_points = [], []
            for k, v in day_data.time_data.items():
                time_points.append(k)
                player_counts.append(v)

            x_axis = time_points
            x_label = "Time Points"

            # After getting the data, format the date
            header = "-".join(header.split("-")[::-1])

        plt.figure(figsize=(len(x_axis) / 2 + 5, 7))
        plt.plot(x_axis, player_counts, marker='o', linestyle='-', color='tab:blue', markersize=8, linewidth=2)
        plt.yticks(self.get_y_ticks(player_counts))
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.title(f'Server Player Count On {header}', fontsize=16)
        plt.xlabel(x_label, fontsize=14, fontweight='bold', color='darkslategray')
        plt.ylabel('Player Count', fontsize=14, fontweight='bold', color='darkslategray')
        plt.legend(['Player Count'], loc='upper right')

        # Adjust layout to prevent clipping of labels
        plt.tight_layout()

        dir = f"./charts/{guild_id}.png"
        if not os.path.exists(r"./charts"):
            os.mkdir(r"./charts")

        plt.savefig(dir)

        return discord.File(dir, filename="chart.png")

