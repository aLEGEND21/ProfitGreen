import discord
from discord.ext import commands

import datetime

from extras import *


class HelpCommand(commands.Cog):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot
        self.bot.help_command = ProfitGreenHelpCommand()
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.help is online")


class ProfitGreenHelpCommand(commands.HelpCommand):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    async def send_bot_help(self, mapping: dict):
        # Figure out how much the spacing should be between the commands and the description
        max_len = 0
        for cmd in self.context.bot.commands:
            if not isinstance(cmd, commands.Command) or cmd.hidden:
                continue 
            if len(cmd.name) > max_len:
                max_len = len(cmd.name)
        max_len += 2

        # Generate the embed description from the mapping object
        desc = ""
        indent = "\u200b " * 6
        for cog in mapping:
            # Skip over cogs with no commands
            if cog is not None and cog.get_commands() == []:
                continue
            # Add an emoji to cogs who have emojis set
            if getattr(cog, "emoji", False):
                emoji = cog.emoji + " "
            else:
                emoji = "\u200b"
            # Set cog title
            desc += f"{emoji}**{cog.qualified_name}:**\n" if cog is not None else ":notepad_spiral: **Uncategorized Commands:**\n"
            for cmd in mapping[cog]:
                # Skip over hidden commands and commands that aren't prefixed commands
                if not isinstance(cmd, commands.Command) or cmd.hidden:
                    continue
                # Set the amount of spacing between the command and the short_docs
                spacing = "." * (max_len - len(cmd.name)) # Use periods because \u200b has variable width which messes up the spacing
                # Add the command to the embed description
                desc += f"{indent}`{cmd.name}` `{spacing}` *{cmd.short_doc}*\n" if cmd.short_doc != "" else f"{indent}`{cmd.name}`\n"
            desc += "\n"
        desc += f"*Type `{self.context.prefix}help <command>` for more info on a command*" # Add footer to description
        
        # Create the embed using the data generated above
        em = discord.Embed(
            title=f"ProfitGreen Bot Commands",
            description=desc,
            color=self.context.bot.green,
            timestamp=datetime.datetime.now()
        )

        # Create the view containing buttons for different functions
        view = discord.ui.View(
            discord.ui.Button(
                label="Support",
                url="https://discord.gg/xBSBYk5Adj"
            ),
            discord.ui.Button(
                label="Invite",
                url=f"https://top.gg/bot/{self.context.bot.user.id}/invite"
            ),
            discord.ui.Button(
                label="Vote",
                url=f"https://top.gg/bot/{self.context.bot.user.id}/vote"
            )
        )

        await self.context.send(embeds=[em], view=view)
    
    async def send_command_help(self, command: commands.Command):
        # Create something showing proper command usage from the usage examples
        # TODO: Do this after creating the full help command ^

        # Format the command aliases
        if command.aliases != []:
            aliases = ""
            for a in command.aliases:
                aliases += f"`{a}`, "
            aliases = aliases[:-2]
        else:
            aliases = "No Aliases Available"
        
        # Set the command description
        if command.description != "":
            cmd_desc = command.description
        elif command.brief != "":
            cmd_desc = command.brief
        else:
            cmd_desc = "No description available"

        # Generate the embed
        em = discord.Embed(
            title=f":notebook: Command Help: `{command.name}`",
            description=f"""
            **Description** :notepad_spiral:
            {cmd_desc}

            **Aliases** :name_badge:
            {aliases}

            **Usage** :wrench:
            `{self.context.prefix}{command.name} {command.signature}`
            """,
            color=self.context.bot.green,
            timestamp=datetime.datetime.now()
        )

        await self.context.send(embeds=[em])


def setup(bot):
    bot.add_cog(HelpCommand(bot))