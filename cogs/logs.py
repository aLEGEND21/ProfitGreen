# cogs/logs.py - A cog to log all events for ProfitGreen
import discord
from discord.ext import commands

from extras import *


class Logger(commands.Cog):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.logs is online")
    
    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        """Logs all commands run on the bot to the logging channel.
        
        Parameters
        ----------
        ctx : commands.Context
            The context of the command.
            
        Returns
        -------
        None
        """

        # Ignore commands run by the developer
        if ctx.author.id == self.bot.owner_id:
            return
        
        # Get the guild user count and bot count
        user_ct = 0
        bot_ct = 0
        for m in ctx.guild.members:
            if m.bot:
                bot_ct += 1
            else:
                user_ct += 1
        
        # Generate the embed
        em = discord.Embed(
            title=f":robot: Command Used: {ctx.command.name}",
            description=f"""
            :notepad_spiral: Full Command: `{ctx.message.content}`
            :bust_in_silhouette: Command Author, ID: `{ctx.author}`, `{ctx.author.id}`
            :satellite: Guild Name, ID: `{ctx.guild.name}`, `{ctx.guild.id}`
            :busts_in_silhouette: Guild Member Count, User Count, Bot Count: `{ctx.guild.member_count}`, `{user_ct}`, `{bot_ct}`
            :speech_balloon: Channel Name, ID: `{ctx.channel.name}`, `{ctx.channel.id}`
            :checkered_flag: Command Failure: `{ctx.command_failed}`
            """
        )
        em.set_thumbnail(url=ctx.author.avatar.url)
        if ctx.command_failed:
            em.color = discord.Color.red()
        else:
            em.color = discord.Color.green()

        # Send the embed to the logging channel
        channel = self.bot.get_channel(self.bot.log_channels[0])
        await channel.send(embed=em)


def setup(bot):
    bot.add_cog(Logger(bot))