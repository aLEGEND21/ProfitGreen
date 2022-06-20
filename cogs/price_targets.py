import discord
from discord.ext import commands

import datetime

from extras import *


class PriceTargets(commands.Cog, name="Price Target Commands"):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot

        # Cog data
        self.emoji = ":dart:"
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.price_targets is online")
    
    @commands.command(
        name="addpricetarget",
        brief="Adds a new price target",
        description="Add a new price target. When the selected quote reaches that price target, you will be notified. In order to get notified, make sure your DMs are enabled so that the bot can DM you.",
        aliases=["addpt", "apt"],
        extras={
            "usage_examples": ["AAPL 150.43", "TSLA 800.01", "BTC-USD 59000"],
        }
    )
    async def add_price_target(self, ctx: commands.Context, quote_ticker: str, target_price: str):
        await ctx.trigger_typing()
        # Check that the ticker is a valid ticker
        quote_data = await self.bot.fetch_quote(quote_ticker)
        if quote_data.get("error") is not None:
            return await ctx.send(f":x: I could not find a quote with ticker `{quote_ticker.upper()}`.")
        
        # Check that the target price is a valid price
        try:
            target_price = float(target_price)
        except ValueError:
            return await ctx.send(f":x: Please provide a valid price for `target_price` instead of `{target_price}`.")
        
        else:
            # Prevent the user from providing a target price that is lower than the current price
            if target_price < float(quote_data["price"]):
                return await ctx.send(f":x: You must specify a target price that is above the current quote price.")
            
            quote_ticker = quote_ticker.upper() # Capitalize the ticker
            target_price = round(target_price, 5) # Prevent long decimals from being stored
            
            # Check if the user already has a price target for this quote
            doc = await self.bot.tasks.find_one(
                {
                    "_type": "price_alert",
                    "user_id": ctx.author.id,
                    "quote_ticker": quote_ticker,
                }
            )
            if doc is not None:
                return await ctx.send(f":x: You already have a price target for this quote.")

            # Add the quote_ticker and target_price to the database
            await self.bot.tasks.insert_one(
                {
                    "_type": "price_alert",
                    "user_id": ctx.author.id,
                    "quote_ticker": quote_ticker,
                    "target_price": target_price,
                }
            )
            await ctx.send(f"Price target added for `{quote_ticker}` at `{target_price}`.")

    @commands.command(
        name="removepricetarget",
        brief="Removes a price target",
        description="Remove a price target you previously set.",
        aliases=["removept", "rpt", "deletepricetarget", "deletept", "delpt", "dpt"],
        extras={
            "usage_examples": ["AAPL", "TSLA", "BTC-USD"],
        }
    )
    async def remove_price_target(self, ctx: commands.Context, quote_ticker: str):
        # Format args
        quote_ticker = quote_ticker.upper()

        """# Check that the ticker is a valid ticker
        if await self.bot.fetch_quote(quote_ticker) == False:
            return await ctx.send(f"I could not find a quote with ticker `{quote_ticker.upper()}`.")"""
        
        # Delete the price target from the database
        result = await self.bot.tasks.delete_one(
            {
                "_type": "price_alert",
                "user_id": ctx.author.id,
                "quote_ticker": quote_ticker,
            }
        )

        # Send a success or failure message
        if result.deleted_count == 1:
            await ctx.send(f"Price target successfully removed from `{quote_ticker.upper()}`.")
        else:
            await ctx.send(f":x: You have not set a price target for `{quote_ticker.upper()}`.")

    @commands.command(
        name="pricetargets",
        brief="Lists all your price targets",
        description="View all price targets that you have set. Price targets that have reached their target price will not be displayed.",
        aliases=["pricetarget", "pt"]
    )
    async def pricetargets(self, ctx: commands.Context):
        # Connect to the database and fetch all price targets for the user
        cursor = self.bot.tasks.find(
            {
                "_type": "price_alert",
                "user_id": ctx.author.id,
            }
        )

        price_targets = []
        for doc in await cursor.to_list(length=None):
            price_targets.append(doc)

        # Check whether the user has any price targets
        if price_targets == []:
            return await ctx.send(f":x: You do not have any price targets. Create a price target by typing `{ctx.clean_prefix}addpricetarget <quote_ticker> <target_price>`.")

        # Construct and send the embed containing all the price targets
        em_desc = ""
        price_targets.sort(key=lambda p: p["quote_ticker"])
        for pt in price_targets:
            em_desc = f"{em_desc}\nTicker: **`{pt['quote_ticker']}`** --- Target Price: **`${pt['target_price']}`**"
        em = discord.Embed(
            title=f":dart: {ctx.author.display_name}'s Price Targets",
            description=em_desc,
            timestamp=datetime.datetime.now(),
            color=discord.Color.blurple()
        )
        await ctx.send(embeds=[em])


def setup(bot):
    bot.add_cog(PriceTargets(bot))