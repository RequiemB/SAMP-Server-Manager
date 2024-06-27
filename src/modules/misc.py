from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from helpers import (
    config, 
    utils as _utils
)
from inspect import cleandoc
from typing import Dict, Optional, List, TYPE_CHECKING
from copy import deepcopy

if TYPE_CHECKING:
    from bot import QueryBot

class HelpSelect(discord.ui.Select):
    def __init__(self, bot: QueryBot) -> None:
        self.bot = bot
        self._options = [
            discord.SelectOption(label=k, value=k, description=v.description, emoji=v.emoji) for k, v in bot.cogs.items() if k.lower() not in ("jishaku", "events") # type: ignore
        ]
        super().__init__(
            placeholder="Select a category",
            min_values=1,
            max_values=1,
            options=self._options,
            row=0
        )
        self.view: HelpPaginator

    async def callback(self, interaction: discord.Interaction[QueryBot]) -> None:
        await self.view.select_callback(interaction, self.values[0]) # type: ignore # This is implemented in the View

class HelpPaginator(discord.ui.View):
    def __init__(self, bot: QueryBot, *, home_embed: Optional[discord.Embed] = None) -> None:
        super().__init__(timeout=300)
        self.add_item(HelpSelect(bot))

        self.bot = bot
        self.current_cog: str = ""
        self.current_page: int = 0
        self.home_embed = home_embed
        self.pages: Dict[str, List[discord.Embed]] = {}
        self.prepared: bool = False
        self.message: Optional[discord.Message] = None

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
            
        if self.message:
            await self.message.edit(view=self)

    def get_command_signature(self, command: app_commands.Command) -> str:
        params = command.parameters
        signature = []
        if not params:
            return ""
        
        for param in params:
            name = param.display_name or param.name

            if param.required:
                name = f"<{name}>"
            else:
                name = f"[{name}]"

            signature.append(name)

        return " ".join(signature)
    
    async def prepare_pages(self) -> None:
        for i, name in enumerate(self.bot.cogs): 
            if name.lower() in ("events", "jishaku"):
                continue

            cog = self.bot.cogs[name]
            self.pages[name] = []

            e = discord.Embed(
                title = f"{_utils.get_cog_emoji(name)} {name} Commands",
                description = f"Use {await self.bot.tree.find_mention_for('help')} [command] for help with a specific command.\n\nIf a parameter is in the format **<parameter>**, that parameter is **required.**\nIf a parameter is in the format **[parameter]**, that parameter is **not required**.",
                color = discord.Color.blue(),
                timestamp = discord.utils.utcnow()
            )

            counter = 0
            for command in cog.walk_app_commands():
                if isinstance(command, app_commands.Group): # Ignore groups
                    continue

                if counter != 0 and (counter % 4 == 0): # We're only fitting 4 commands in one embed, for more we use another embed.
                    self.pages[name].append(deepcopy(e)) # Make a deep copy of the embed
                    e.clear_fields()

                mention = await self.bot.tree.find_mention_for(command.qualified_name)
                e.add_field(
                    name =  f"{mention} {self.get_command_signature(command)}",
                    value = command.description,
                    inline = False
                )
                counter += 1

            self.pages[name].append(e)

            # Add page number to footer
            for page_no, embed in enumerate(self.pages[name], start=1):
                embed.set_footer(text=f"Page: {page_no}/{len(self.pages[name])}")

    def configure_button_availability(self, pages: int) -> None:
        if pages > 1:
            if self.current_page == 1: # First page 
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        if item.label in ("<<", "Backward"):
                            item.disabled = True
                        else:
                            item.disabled = False

            elif self.current_page == pages: # Last page
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        if item.label in (">>", "Forward"):
                            item.disabled = True
                        else:
                            item.disabled = False

            else: # Middle page
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = False 

        else: # There is only one page, disable all the buttons
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
        
    async def select_callback(self, interaction: discord.Interaction, selected: str) -> None:
        if not self.prepared:
            await self.prepare_pages()
            self.prepared = True
            
        self.current_page = 1
        self.current_cog = selected
        self.configure_button_availability(len(self.pages[selected]))
        await interaction.response.edit_message(embed=self.pages[selected][self.current_page-1], view=self)

    @discord.ui.button(label="<<", style=discord.ButtonStyle.grey, row=1)
    async def rewind(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = 1
        self.configure_button_availability(len(self.pages[self.current_cog]))
        await interaction.response.edit_message(embed=self.pages[self.current_cog][self.current_page-1], view=self)

    @discord.ui.button(label="Backward", style=discord.ButtonStyle.blurple, row=1)
    async def backward(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page -= 1
        self.configure_button_availability(len(self.pages[self.current_cog]))
        await interaction.response.edit_message(embed=self.pages[self.current_cog][self.current_page-1], view=self)

    @discord.ui.button(label="Forward", style=discord.ButtonStyle.blurple, row=1)
    async def forward(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page += 1
        self.configure_button_availability(len(self.pages[self.current_cog]))
        await interaction.response.edit_message(embed=self.pages[self.current_cog][self.current_page-1], view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.grey, row=1)
    async def fast_forward(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = len(self.pages[self.current_cog]) # Last page
        self.configure_button_availability(len(self.pages[self.current_cog]))
        await interaction.response.edit_message(embed=self.pages[self.current_cog][self.current_page-1], view=self)

class Misc(commands.Cog):
    "Miscellanous commands."
    def __init__(self, bot):
        self.bot: QueryBot = bot
        self.emoji = _utils.get_result_emoji()
        self.query = self.bot.query

    def get_command_help(self, command_str: str, *, group_str: Optional[str] = None) -> Optional[discord.Embed]:
        if group_str:
            group = self.bot.tree.get_command(group_str)
            if not group or not isinstance(group, app_commands.Group):
                return None
            
            command = group.get_command(command_str)

        else:
            command = self.bot.tree.get_command(command_str)

        if not command or isinstance(command, app_commands.Group):
            return None
        
        e = discord.Embed(
            title = f"Help for /{command.qualified_name}",
            color = discord.Color.blue(),
            timestamp = discord.utils.utcnow()
        )

        e.description = command.description if command.description else "No description was provided."

        e.description += "\n## Arguments"
        if command.parameters:
            for param in command.parameters:
                e.description += f"\n* {param.name}\nRequired: **{param.required}**.\nDescription: {param.description}\n"
                try:
                    e.description += f"Examples: **{', '.join(command.extras[param.name])}**.\n"
                except KeyError:
                    pass

        else:
            e.description += "\nThis command requires no arguments."

        return e

    @app_commands.command(name="bugreport", description="Use this command to report a bug found in the bot.", extras={"Cog": "Misc"})
    @app_commands.describe(bug="The bug that was found.")
    async def bugreport(self, interaction: discord.Interaction[QueryBot], *, bug: str) -> None:
        if len(bug) > 1023: # Discord char limit for embed fields
            e = discord.Embed(description=f"{_utils.get_result_emoji('failure')} The bug text must be lower than 1024 char in length.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)
            return
        
        channel = interaction.client.get_channel(int(config.BUG_REPORT_CHANNEL))
        if channel is None:
            e = discord.Embed(description=f"{_utils.get_result_emoji('failure')} No channel for bug reports is configured.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)
            return

        e = discord.Embed(
            title=f"Report by {interaction.user}", 
            description=f"Bug report was made by {interaction.user} (ID: {interaction.user.id}).",
            color = discord.Color.blue(),
            timestamp = discord.utils.utcnow()
        )

        e.add_field(name="Bug Report", value=f"```{bug}```")
        if (isinstance(channel, discord.TextChannel) or isinstance(channel, discord.Thread)):
            await channel.send(embed=e)
            e = discord.Embed(description=f"{_utils.get_result_emoji('success')} Your bug report has been sent successfully. Join the [support server](https://discord.gg/z9j2kb9kB3) to know the status.", color=discord.Color.green())
            await interaction.response.send_message(embed=e)
        else:
            e = discord.Embed(description=f"{_utils.get_result_emoji('failure')} No channel for bug reports is configured.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)

    @app_commands.command(name="help", description="Shows the help for the bot.")
    @app_commands.describe(command="The command to display help for. If this isn't specified, then the global help command is shown.")
    async def help(self, interaction: discord.Interaction[QueryBot], *, command: Optional[str] = None) -> None:
        assert interaction.guild and self.bot.user

        if command:
            cmd = command.split()
            if len(cmd) >= 2: # It's a group
                e = self.get_command_help(cmd[1], group_str=cmd[0])
            else:
                e = self.get_command_help(cmd[0])

            if not e:
                await interaction.response.send_message(embed=discord.Embed(description=f"{_utils.get_result_emoji('failure')} Command **{command}** was not found.", color=discord.Color.red()))
                return

            view = HelpPaginator(self.bot) # just for good looking embed
            for item in view.children:
                if isinstance(item, (discord.ui.Button, discord.ui.Select)): 
                    item.disabled = True

            await interaction.response.send_message(embed=e, view=view)
            return

        e = discord.Embed(
            title = self.bot.user.name + " Help",
            description = cleandoc(f"""
                Welcome to the help menu of the bot.
                                   
                Use {_utils.command_mention_from_interaction(interaction)} [command] for help with a specific command.
                Use the drop-down menu below to get help of commands in different categories.
            """),
            color = discord.Color.blue(),
            timestamp = discord.utils.utcnow()
        )

        e.add_field(
            name="Description", 
            value=(
                f"{self.bot.user.name} is a bot made by Blitz (requiem.b). The bot can query SAMP game-servers "
                "and display information about them. It can be configured to display the information in a channel "
                "at a given interval. It also saves run a background task which saves statistics of the server. "
                "The bot also has a chart system which users can use to get the chart of playercounts in a specific day or month."
            ),
            inline = False
        )
        e.add_field(
            name="Support Server",
            value = "You can join the support server by clicking [here](https://discord.gg/GK8wPNjJXy).",
            inline=False
        )
        view = HelpPaginator(self.bot, home_embed=e)
        # Disable all the buttons since the front page has only one embed
        for item in view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        await interaction.response.send_message(embed=e, view=view)
        view.message = await interaction.original_response()

    @help.autocomplete('command')
    async def command_autocomplete(self, interaction: discord.Interaction[QueryBot], current: str) -> List[app_commands.Choice]:
        commands: List[str] = []

        for command in interaction.client.tree.get_commands():
            if len(commands) > 25:
                break

            if command.name == "help": # Ignore help
                continue
            
            if isinstance(command, app_commands.Group):
                if len(commands) > 25:
                    break

                commands.extend([cmd.qualified_name for cmd in command.walk_commands()]) 
                continue

            commands.append(command.name)

        if not current: # User didn't type anything, so show all the commands
            return [
                app_commands.Choice(name=cmd, value=cmd) for cmd in commands
            ]
        else:
            return [
                app_commands.Choice(name=cmd, value=cmd) for cmd in commands if current.lower() in cmd.lower()
            ]
    
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Misc(bot))