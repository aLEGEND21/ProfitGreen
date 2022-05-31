import discord
from discord.ext import commands
from discord.ext import tasks

import asyncio
import datetime

from extras import *


class TaskManager(commands.Cog):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot

        self.check_price_targets.start()
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.tasks is online")
    
    # Create a task to check the database and see if price targets have been reached
    @tasks.loop(minutes=5)
    async def check_price_targets(self):
        db = TasksDataBase()
        price_targets = db.get_all_price_targets()
        db.disconnect()

        # Loop through each price target searching for ones that have been reached
        for pt in price_targets:
            quote_data = await self.bot.fetch_quote(pt[1])

            if float(quote_data["price"]) > pt[2]:
                # Fetch the user and generate the embed
                user = await self.bot.fetch_user(pt[0])
                em = discord.Embed(
                    title=":dart: Price Target Reached",
                    description=f"**`{pt[1]}`** Reached A Price Target of **`${pt[2]}`**",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )
                
                # Try to notify the user about their met price target. If a 403 Forbidden error is
                # raised, then do not delete the price target
                try:
                    await user.send(embeds=[em])
                    db = TasksDataBase()
                    db.remove_price_target(user.id, pt[1]) # Delete the price target since the user was notified
                    db.disconnect()
                except discord.Forbidden:
                    print(f"Unable to notify {user.name}#{user.discriminator} about price target on {pt[1]} for ${pt[2]} (403 Forbidden).")
            
            await asyncio.sleep(1) # Prevent Yahoo Finance from ratelimiting the bot


def setup(bot):
    bot.add_cog(TaskManager(bot))