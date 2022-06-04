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
            # Set cog title and loop through all the commands in the cog
            desc += f"{emoji}**{cog.qualified_name}:**\n" if cog is not None else ":notepad_spiral: **Uncategorized Commands:**\n"
            for cmd in mapping[cog]:
                # Skip over hidden commands
                if cmd.hidden:
                    continue
                # Add the command to the embed description
                desc += f"{indent}`{cmd.name}`{indent*2}*{cmd.short_doc}*\n" if cmd.short_doc != "" else f"{indent}`{cmd.name}`\n"
            desc += "\n"
        desc += f"*Type `{self.context.prefix}help <command>` for more info on a command*" # Add footer to description

        # Create the embed using the data generated above
        em = discord.Embed(
            title=f"ProfitGreen Bot Commands",
            description=desc,
            color=self.context.bot.green,
            timestamp=datetime.datetime.now()
        )

        await self.context.send(embeds=[em])
    
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

        # Generate the embed
        em = discord.Embed(
            title=f":notebook: Command Help: `{command.name}`",
            description=f"""
            **Description** :notebook:
            {command.description if command.description != "" else "No description available"}

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