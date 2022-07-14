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
            self.check_limit_orders.start()
        
    """
    Limit Order Example Task:
    {
        "_id": ObjectID("5e9f8f8f8f8f8f8f8f8f8f8"),
        "_type": "LIMIT_ORDER",
        "limit_order_type": "BUY",
        "ticker": "AAPL",
        "execute_price": 123.45,
        "quantity": 67,
        "timestamp": 123412341234,
        "user_id": 81234818238418324,
        "notified": False # Used if the order fails
    }
    """
    
    def cog_unload(self):
        """Cancels all tasks when cog is unloaded"""
        self.check_price_targets.stop()
        self.check_limit_orders.stop()

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
            
            # Check if the quote has reached the target price
            reached = False
            if pt['execute'] == "ABOVE" and float(quote_data["price"]) > pt['target_price']:
                reached = True
            elif pt['execute'] == "BELOW" and float(quote_data["price"]) < pt['target_price']:
                reached = True

            if reached:
                # Fetch the user and generate the embed
                user = await self.bot.fetch_user(pt["user_id"])
                em = discord.Embed(
                    title=":dart: Price Target Reached",
                    description=f"**`{pt['quote_ticker']}`** has gone `{pt['execute']}` the target price of **`${pt['target_price']}`**",
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
                except discord.errors.Forbidden:
                    print(f"Unable to notify {user.name}#{user.discriminator} about price target on {pt['quote_ticker']} for ${pt['target_price']} (403 Forbidden).")
            
            await asyncio.sleep(1) # Prevent Yahoo Finance from ratelimiting the bot
    
    @tasks.loop(minutes=5)
    async def check_limit_orders(self):
        cursor = self.bot.tasks.find({"_type": "LIMIT_ORDER"})

        # Loop through each limit order searching for ones that need to execute
        for lo in await cursor.to_list(length=None):
            quote_data = await self.bot.fetch_brief(lo["ticker"])

            # Check if the order should execute
            execute = False
            if lo['limit_order_type'] == "BUY" and float(quote_data["price"]) <= lo['execute_price']:
                execute = True
            elif lo['limit_order_type'] == "SELL" and float(quote_data["price"]) >= lo['execute_price']:
                execute = True
            
            if execute:
                portfolio_data = await self.bot.fetch_portfolio(lo["user_id"])
                order_total = round(lo['quantity'] * quote_data['price'], 5)
                
                # Handle limit BUY orders
                if lo['limit_order_type'] == "BUY":
                    # Check if the user has enough money for the order. If they don't, notify them
                    if order_total > portfolio_data['balance']:
                        user = await self.bot.fetch_user(lo['user_id'])
                        em = discord.Embed(
                            title=f":x: Limit BUY Order Failed for `{lo['ticker']}`",
                            description=f"Hey {user.name}, you have a pending limit order for `{lo['ticker']}` which has reached it's strike price of `{self.bot.commify(lo['execute_price'])}`, but you don't have enough cash in your portfolio to cover the order total of `${self.bot.commify(order_total)}`.\n\nSell some stocks in order to gain enough money for the order to execute automatically or cancel the pending order.",
                            color=discord.Color.red(),
                            timestamp=datetime.datetime.now()
                        )
                        try:
                            # Only notify the user if they haven't been notified before
                            if lo['notified'] == False:
                                await user.send(embeds=[em])
                                lo['notified'] = True
                                await self.bot.tasks.update_one(
                                    {"_id": lo["_id"]},
                                    {"$set": lo}
                                )
                        except discord.errors.Forbidden: # User disabled DMs with the bot
                            print(f"Unable to notify {user.name}#{user.discriminator} about their failed limit BUY on {lo['ticker']} for {lo['quantity']} shares at a strike price of ${lo['execute_price']} (403 Forbidden).")
                        continue # Move on to the next limit order

                    # Update the user's balance
                    portfolio_data['balance'] = round(portfolio_data['balance'] - order_total, 3)
                    # Update the quantity and the buy price if the user already has the quote in their portfolio
                    for q in portfolio_data["portfolio"]:
                        if q["ticker"] == lo['ticker']:
                            q["quantity"] += lo['quantity']
                            q["buy_price"] = round((q["buy_price"] * q["quantity"] + quote_data["price"] * lo['quantity']) / (q["quantity"] + lo['quantity']), 3)
                            break
                    # Otherwise, add the quote to the portfolio in a new entry
                    else:
                        portfolio_data["portfolio"].append(
                            {
                                "ticker": lo['ticker'],
                                "quantity": lo['quantity'],
                                "buy_price": quote_data['price']
                            }
                        )
                    # Update the database with the revised portfolio
                    await self.bot.portfolio.update_one(
                        {"_id": lo['user_id']},
                        {"$set": portfolio_data}
                    )
                    await self.bot.log_trade(lo['user_id'], "BUY", lo['ticker'], lo['quantity'], quote_data['price']) # Log the trade in the database as well
                    await self.bot.tasks.delete_one({"_id": lo["_id"]})

                # Handle limit SELL orders
                elif lo['limit_order_type'] == "SELL":
                    # Reduce the number of shares the user has in their portfolio. While updating
                    # the number of shares the user has, make sure they have enough shares for the
                    # order to be placed, otherwise, notify them.
                    failure = False
                    for q in portfolio_data['portfolio']:
                        if q["ticker"] == lo['ticker']:
                            if q["quantity"] < lo["quantity"]:
                                failure = True
                            else:
                                q["quantity"] -= lo["quantity"]
                                if q["quantity"] == 0:
                                    portfolio_data["portfolio"].remove(q)
                            break
                    else:
                        self.bot.tasks.delete_one({"_id": lo['_id']}) # Delete the limit order since the user already sold all of their shares of the quote
                        continue # Move on to the next limit order
                    # Check if the order failed. If it did, then notify the user about it
                    if failure:
                        user = await self.bot.fetch_user(lo['user_id'])
                        em = discord.Embed(
                            title=f":x: Limit SELL Order Failed for `{lo['ticker']}`",
                            description=f"Hi {user.name}, your order was unable to execute successfully because you don't own at least `{self.bot.commify(lo['quantity'])}` shares of `{lo['ticker']}` to sell at a strike price of `${self.bot.commify(lo['execute_price'])}`.\n\nBuy at least `{self.bot.commify(lo['quantity'] - q['quantity'])}` more shares of `{lo['ticker']}` for the limit order to execute automatically or delete the pending order.",
                            color=discord.Color.red(),
                            timestamp=datetime.datetime.now()
                        )
                        try:
                            # Only notify the user if they haven't been notified before
                            if lo['notified'] == False:
                                await user.send(embeds=[em])
                                lo['notified'] = True
                                await self.bot.tasks.update_one(
                                    {"_id": lo["_id"]},
                                    {"$set": lo}
                                )
                        except discord.errors.Forbidden: # User has DMs disabled
                            print(f"Unable to notify {user.name}#{user.discriminator} about their failed limit SELL order on {lo['ticker']} for {lo['quantity']} shares at a strike price of ${lo['strike_price']} (403 Forbidden).")
                        continue # Move on to the next order
                    # Order succeeded, so increase the user's balance and update the database
                    else:
                        portfolio_data['balance'] = round(portfolio_data['balance'] + order_total, 3)
                        await self.bot.portfolio.update_one(
                            {"_id": lo['user_id']},
                            {"$set": portfolio_data}
                        )
                        await self.bot.log_trade(lo['user_id'], "SELL", lo['ticker'], lo['quantity'], quote_data['price'])
                        await self.bot.tasks.delete_one({"_id": lo["_id"]})

                # Send the user a DM that their order was successful
                user = await self.bot.fetch_user(lo["user_id"])
                em = discord.Embed(
                    title=":moneybag: Limit Order Executed",
                    description=f"Your limit **`{lo['limit_order_type']}`** on **`{lo['ticker']}`** for `{self.bot.commify(lo['quantity'])}` shares has been executed at **`${self.bot.commify(quote_data['price'])}`**. The total {'cost' if lo['limit_order_type'] == 'BUY' else 'profit'} was **`${self.bot.commify(order_total)}`**.\n\n:dollar: You now have **`${self.bot.commify(portfolio_data['balance'])}`** of cash.",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )
                try:
                    await user.send(embeds=[em])
                except discord.errors.Forbidden: # User has DMs disabled
                    print(f"Unable to notify {user.name}#{user.discriminator} about successful {lo['limit_order_type']} limit order on {lo['ticker']} for {lo['quantity']} shares at a strike price of ${lo['strike_price']} (403 Forbidden).")

            await asyncio.sleep(1) # Prevent ratelimits


def setup(bot):
    bot.add_cog(TaskManager(bot))