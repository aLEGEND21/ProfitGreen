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

        # OLD System - Single embed
        '''# Generate the embed description from the mapping object
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
        )'''

        # Create a new cog object for the commands that aren't under a cog
        misc_cog = commands.Cog(name="Uncategorized Commands")
        misc_cog.emoji = "notepad_spiral"
        mapping[misc_cog] = mapping[None]
        del mapping[None]

        # Remove cogs with no commands from the mapping
        _mapping = {}
        for cog, cmds in mapping.items():
            if cog.get_commands() == []:
                continue
            else:
                _mapping[cog] = cmds
        mapping = _mapping

        # Create each embed page
        pages = [
            discord.Embed(
                title=f"ProfitGreen Bot Help",
                description=f"{self.context.bot._emojis['profitgreen']} ProfitGreen is a Discord bot with a wide array of finance and investing related commands, allowing you to do everything from invest in stocks and cryptos to viewing the sentiment of individual stocks or the entire stock market.\n\n*Use the select menu below to view the commands for a specific category.*",
                color=self.context.bot.green,
                timestamp=datetime.datetime.now()
            )
        ]
        indent = "\u200b " * 6
        for cog, cmds in mapping.items():
            # Create the embed
            p = discord.Embed(
                description=f"**{cog.emoji if getattr(cog, 'emoji', False) else ''} {cog.qualified_name}:**\n",
                color=self.context.bot.green,
                timestamp=datetime.datetime.now()
            )
            # Set the embed description
            for c in cmds:
                # Skip over hidden commands and commands that aren't prefixed commands
                if not isinstance(c, commands.Command) or c.hidden:
                    continue
                # Set the amount of spacing between the command and the short_docs
                spacing = "." * (max_len - len(c.name)) # Use periods because \u200b has variable width which messes up the spacing
                # Add the command to the embed description
                p.description += f"{indent}`{c.name}` `{spacing}` *{c.short_doc}*\n" if c.short_doc != "" else f"{indent}`{c.name}`\n"
            pages.append(p)

        # Create the callback for the select menu
        async def select_callback(interaction: discord.Interaction):
            # Retrieve the selected cog's index
            selected_category = interaction.data['values'][0]
            for cog in mapping:
                if cog.qualified_name == selected_category:
                    cog_index = list(mapping.keys()).index(cog) + 1 # +1 is to account for the default page
                    break
            else:
                cog_index = 0 # Handle the category being the bot overview page
            # Update the message
            await interaction.response.edit_message(embeds=[pages[cog_index]])

        # Create the view containing buttons for different functions and the select menu
        btns = [
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
        ]
        select_options = [
            discord.SelectOption(
                label="Overview",
                #emoji=self.context.bot._emojis['profitgreen']
            )
        ]
        for cog in mapping:
            if cog.get_commands() == []:
                continue
            select_options.append(
                discord.SelectOption(
                    label=cog.qualified_name,
                    #emoji=cog.emoji if getattr(cog, 'emoji', False) else None, # TODO: Figure out why tis doesn't work
                )
            )
        select_menu = discord.ui.Select(options=select_options, placeholder="Select a Category")
        select_menu.callback = select_callback
        view = discord.ui.View(select_menu, *btns)

        await self.context.send(embeds=[pages[0]], view=view)
    
    async def send_command_help(self, command: commands.Command):
        # TODO: Create something showing proper command usage from the usage examples

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

        # Generate any buttons needed for the help command
        view = discord.ui.View()
        if command.extras.get("links") is not None:
            for label, url in command.extras["links"].items():
                view.add_item(discord.ui.Button(
                    label=label,
                    url=url
                ))

        await self.context.send(embeds=[em], view=view)


def setup(bot):
    bot.add_cog(HelpCommand(bot))