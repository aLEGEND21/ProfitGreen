import discord
from discord.ext import commands

import datetime

from extras import *


class PriceTargets(commands.Cog, name="Price Target Commands"):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot

        # Cog data
        self.emoji = ":dart:"
    
    """
    Example Price Target:
    {
        "_id": ObjectID("5e8f8f8f8f8f8f8f8f8f8f"),
        "_type": "price_alert",
        "user_id": 1234123412341234,
        "quote_ticker": "AAPL",
        "target_price": 210.98,
        "execute": "ABOVE" # (or "BELOW")
    }
    """
    
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
                execute = "BELOW"
            elif target_price > float(quote_data["price"]):
                execute = "ABOVE"
            else:
                return await ctx.send(f":x: The target price cannot be the same as the current price.")

            quote_ticker = quote_ticker.upper() # Capitalize the ticker
            target_price = round(target_price, 5) # Prevent long decimals from being stored
            
            # Check if the user already has 3 price targets for the quote
            cursor = self.bot.tasks.find(
                {
                    "_type": "price_alert",
                    "user_id": ctx.author.id,
                    "quote_ticker": quote_ticker,
                }
            )
            if len(await cursor.to_list(length=None)) >= 3:
                return await ctx.send(f":x: You cannot set more than 3 price targets for a quote.")

            # Add the quote_ticker and target_price to the database
            await self.bot.tasks.insert_one(
                {
                    "_type": "price_alert",
                    "user_id": ctx.author.id,
                    "quote_ticker": quote_ticker,
                    "target_price": target_price,
                    "execute": execute,
                }
            )
            await ctx.send(f":white_check_mark: You will be notified when `{quote_ticker}` goes {execute.lower()} `${target_price}`.")

    @commands.command(
        name="removepricetarget",
        brief="Removes a price target",
        description="Remove a price target you previously set. If you have set multiple price targets for a ticker, then you will be able to choose which one to remove.",
        aliases=["removept", "rpt", "deletepricetarget", "deletept", "delpt", "dpt"],
        extras={
            "usage_examples": ["AAPL", "TSLA", "BTC-USD"],
        }
    )
    async def remove_price_target(self, ctx: commands.Context, quote_ticker: str):
        # Format args
        quote_ticker = quote_ticker.upper()
        
        # Fetch all of the user's price targets for the ticker from the database
        cursor = self.bot.tasks.find(
            {
                "_type": "price_alert",
                "user_id": ctx.author.id,
                "quote_ticker": quote_ticker
            }
        )
        price_targets = await cursor.to_list(length=None)

        # Check if the user has any price targets for the ticker
        if len(price_targets) == 0:
            return await ctx.send(f":x: You do not have any price targets for `{quote_ticker}`.")

        # If the user only has one price target set for the ticker, remove it
        if len(price_targets) == 1:
            await self.bot.tasks.delete_one(
                {
                    "_id": price_targets[0]["_id"]
                }
            )
            return await ctx.send(f":white_check_mark: Your price target for `{quote_ticker}` has been removed.")

        # Create the embed containing all of the price targets
        em = discord.Embed(
            title=f"Price Targets for {quote_ticker}",
            description="```",
            color=self.bot.green,
        )
        em.set_footer(text=f"Select the price target to remove")
        
        # Generate the embed description
        for i, pt in enumerate(price_targets):
            em.description += f"[{i+1}] Executes {pt['execute']} ${pt['target_price']}\n"
        em.description += "```"

        # Declare the button callback
        async def btn_callback(interaction: discord.Interaction):
            # Check to make sure the correct user clicked the button
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message(":x: You're not allowed to click that button.", ephemeral=True)

            # Retrieve the selected price target
            btn_id = int(interaction.data['custom_id'])
            selected_pt = price_targets[btn_id]

            # Remove the price target from the database
            await self.bot.tasks.delete_one({"_id": selected_pt["_id"]})
            await interaction.response.send_message(f":white_check_mark: Removed price target for `{quote_ticker}`.")
            
            # Regenerate the embed and disable all the buttons
            em.description = "```"
            for i, pt in enumerate(price_targets):
                if i == btn_id:
                    em.description += f"[{i+1}] DELETED\n"
                else:
                    em.description += f"[{i+1}] Executes {pt['execute']} ${pt['target_price']}\n"
            em.description += "```"
            em.set_footer(text="Price target successfully removed")
            view.disable_all_items()
            await interaction.followup.edit_message(m.id, embeds=[em], view=view)

        # Create the buttons and add them to the view
        btns = {}
        for i, pt in enumerate(price_targets):
            btns[i] = discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                label=f"[{i+1}]",
                custom_id=str(i),
            )
            btns[i].callback = btn_callback
        view = discord.ui.View(*list(btns.values()))

        # Send the embed and wait for the user to select a price target
        m = await ctx.reply(embeds=[em], view=view)

    @commands.command(
        name="pricetargets",
        brief="Lists all your price targets",
        description="View all price targets that you have set. Once you are notified about a price target being reached, the target will no longer be displayed here.",
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
        price_targets = await cursor.to_list(length=None)

        # Check whether the user has any price targets
        if price_targets == []:
            return await ctx.send(f":x: You do not have any price targets. Create a price target by typing `{ctx.clean_prefix}addpricetarget <quote_ticker> <target_price>`.")

        # Store the price targets under the ticker they are for
        price_targets.sort(key=lambda p: p["quote_ticker"])
        _ = {}
        for i, pt in enumerate(price_targets):
            if pt["quote_ticker"] not in _:
                _[pt["quote_ticker"]] = []
            _[pt["quote_ticker"]].append(pt)
        price_targets = _

        # Construct and send the embed containing all the price targets
        em = discord.Embed(
            title=f":dart: {ctx.author.display_name}'s Price Targets",
            description="```",
            timestamp=datetime.datetime.now(),
            color=self.bot.green,
        )
        for quote_ticker, targets in price_targets.items():
            em.description += f"[{list(price_targets.keys()).index(quote_ticker)+1}] {quote_ticker.upper()}:\n"
            for pt in targets:
                em.description += f" - Executes {pt['execute']} ${pt['target_price']}\n"
            em.description += "\n"
        em.description += "```"
        
        await ctx.reply(embeds=[em])


def setup(bot):
    bot.add_cog(PriceTargets(bot))