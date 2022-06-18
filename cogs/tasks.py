import discord
from discord.ext import commands
from discord.ext import tasks

import asyncio
import datetime

from extras import *
from config import Config


class TaskManager(commands.Cog):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot

        if Config.PRODUCTION:
            self.check_price_targets.start()
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.tasks is online")
    
    # Create a task to check the database and see if price targets have been reached
    @tasks.loop(minutes=5)
    async def check_price_targets(self):
        cursor = self.bot.tasks.find({"_type": "price_alert"})

        # Loop through each price target searching for ones that have been reached
        for pt in await cursor.to_list(length=None):
            quote_data = await self.bot.fetch_quote(pt["quote_ticker"])

            if float(quote_data["price"]) > pt["target_price"]:
                # Fetch the user and generate the embed
                user = await self.bot.fetch_user(pt["user_id"])
                em = discord.Embed(
                    title=":dart: Price Target Reached",
                    description=f"**`{pt['quote_ticker']}`** Reached A Price Target of **`${pt['target_price']}`**",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )
                
                # Try to notify the user about their met price target. If a 403 Forbidden error is
                # raised, then do not delete the price target
                try:
                    await user.send(embeds=[em])
                    await self.bot.tasks.delete_one(
                        {
                            "_id": pt["_id"],
                        }
                    )
                except discord.Forbidden:
                    print(f"Unable to notify {user.name}#{user.discriminator} about price target on {pt[1]} for ${pt[2]} (403 Forbidden).")
            
            await asyncio.sleep(1) # Prevent Yahoo Finance from ratelimiting the bot


def setup(bot):
    bot.add_cog(TaskManager(bot))