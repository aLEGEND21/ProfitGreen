# cogs/utils.py - A cog to store all utility functions for ProfitGreen
import discord
from discord.ext import commands
from discord.ext import tasks

import topgg

from extras import *


class Utils(commands.Cog):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot
        self.bot.topggpy = topgg.DBLClient(bot, bot.topgg_token)

        self.update_stats.start()
    
    @tasks.loop(minutes=30)
    async def update_stats(self):
        """This function runs every 30 minutes to automatically update your server count."""
        try:
            await self.bot.topggpy.http.post_guild_count(10 ** 4, self.bot.shard_count, self.bot.shard_id) # Post a fake server count to Top.gg
            print(f"Posted server count to Top.gg")
        except Exception as e:
            print(f"Failed to post server count\n{e.__class__.__name__}: {e}")
    

def setup(bot):
    bot.add_cog(Utils(bot))