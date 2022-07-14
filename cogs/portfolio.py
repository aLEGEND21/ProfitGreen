import discord
from discord.ext import commands
from discord.ext import pages

import datetime
import inspect

from extras import *


class Portfolio(commands.Cog, name="Portfolio Commands"):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot

        # Cog data
        self.emoji = ":dollar:"
    
    """
    Trade Logging:
    "trade_history": [
        {
            "_type": "BUY",
            "datetime": "2022-07-06 10:10:52.165995",
            "timestamp": 1657116677.7689857,
            "ticker": "AAPL",
            "quantity": 100,
            "price": 123.456,
            "vote_reward": True
        }
    ]
    """

    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.portfolio.py is online")

    async def cog_before_invoke(self, ctx: commands.Context):
        # Make the user an account in the database if they don't have an account in the portfolio collection
        await self.bot.create_portfolio(ctx.author)

    @commands.command(
        name="portfolio",
        brief="Displays your portfolio",
        description="Shows a detailed view of your portfolio. This includes your total portfolio value, the amount of cash you have, your net worth, number of holdings, and also data about each individual holding. The data for each holding includes the total value of that holding, your gain/loss, the buy price, and the number of shares you own. If you wish to see the portfolio of another user, mention them for the `user` parameter.",
        aliases=["myportfolio", "mp"]
    )
    async def portfolio(self, ctx: commands.Context, user: discord.Member = None):
        await ctx.trigger_typing()

        if user is None:
            user = ctx.author
        else:
            await self.bot.create_portfolio(user) # Make sure the user has an account in the portfolio collection

        # Retrieve the user's portfolio data from the database
        portfolio_data = await self.bot.fetch_portfolio(user.id)
        balance = portfolio_data["balance"]
        portfolio = portfolio_data["portfolio"]

        # Check to make sure the user has quotes in their portfolio
        if portfolio == []:
            em = discord.Embed(
                title=f"{user.name}'s Portfolio",
                description=f"""
                :dollar: Total Cash: `${self.bot.commify(balance)}`
                
                :exclamation: {"You don't" if user == ctx.author else user.name + " doesn't"} own any quotes yet. 
                
                :moneybag: Buy a stock or crypto by typing `{ctx.clean_prefix}buy <ticker> [amount]`
                """,
                color=self.bot.green,
                timestamp=datetime.datetime.now()
            )
            em.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar)
            return await ctx.send(embeds=[em])

        # Retrieve the current prices of the quotes in the user's portfolio
        coroutines = []
        for quote in portfolio:
            coroutines.append(self.bot.fetch_brief(quote["ticker"]))
        price_data = list(await asyncio.gather(*coroutines)) # Run the coroutines in parallel
        price_data.sort(key=lambda p: p["ticker"])

        # Get the total value of the portfolio
        total_val = 0
        for quote in portfolio:
            for item in price_data:
                if item["ticker"] == quote["ticker"]:
                    break
            total_val += round(item["price"] * quote["quantity"], 3)
        total_val = round(total_val, 3)
        
        # Find the net worth of the user
        net_worth = round(balance + total_val, 3)
        
        # Update price_data to also contain user-specific data about the quotes
        for quote in price_data:
            for holding in portfolio:
                if quote["ticker"] == holding["ticker"]:
                    break
            i = price_data.index(quote)
            price_data[i]["buy_price"] = holding["buy_price"] # Transfer the buy price over
            price_data[i]["quantity"] = holding["quantity"] # Transfer the quantity over
            price_data[i]["total_val"] = round(holding["quantity"] * quote["price"], 3) # The total value of the holding
            price_data[i]["invested_weight"] = round(price_data[i]["total_val"] / total_val * 100, 2) # Percent the quote takes up of only the invested capital (excluding cash)
            price_data[i]["total_weight"] = round(price_data[i]["total_val"] / net_worth * 100, 2) # Percent the quote takes up in the user's portfolio (including cash)
            price_data[i]["holding_change_dollar"] = round((price_data[i]["price"] - holding["buy_price"]) * holding["quantity"], 3) # The dollar change in price since the quote was bought
            price_data[i]["holding_change_pct"] = round((price_data[i]["price"] - holding["buy_price"]) / holding["buy_price"] * 100, 2) # The percent change in price since the quote was bought

        # Calculate other data to display
        pct_cash = round(balance / net_worth * 100, 2)
        dollar_change = round(sum([q["total_val"] for q in price_data]) - sum(q["buy_price"] * q["quantity"] for q in portfolio), 3)
        pct_change = round(dollar_change / sum(q["buy_price"] * q["quantity"] for q in portfolio) * 100, 2)
        total_num_shares = sum([holding["quantity"] for holding in portfolio])

        # Create the summary page embed
        summary_em = discord.Embed(
            title=f"{user.display_name}'s Portfolio",
            description=f"""
            __**Portfolio Summary**__
            :moneybag: Total Portfolio Value: `${self.bot.commify(total_val)}`
            :chart: Dollar Change: `${self.bot.commify(dollar_change)}`
            :chart_with_upwards_trend: Percent Change: `{self.bot.commify(pct_change)}%`

            __**Account Summary**__
            :credit_card: Net Worth: `${self.bot.commify(net_worth)}`
            :dollar: Cash: `${self.bot.commify(balance)}`
            :dividers: Percent Cash: `{self.bot.commify(pct_cash)}%`

            __**Portfolio Statistics**__
            :card_index: Total Number of Holdings: `{self.bot.commify(len(portfolio))}`
            :1234: Total Number of Shares: `{self.bot.commify(total_num_shares)}`

            *Use the select menu below to view {"your" if ctx.author == user else user.name + "'s"} holdings in more detail*
            """,
            timestamp=datetime.datetime.now(),
            color=discord.Color.green() if pct_change >= 0 else discord.Color.red()
        )
        summary_em.set_thumbnail(url=user.display_avatar)
        summary_em.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar)

        # Create the embeds for each quote in the user's portfolio
        quote_pages = [summary_em]
        for quote_data in price_data:
            em = discord.Embed(
                title=f"{user.display_name}'s Portfolio: `{quote_data['ticker']}`",
                description=f"""
                __**Holding Summary**__
                :moneybag: Total Value: `${self.bot.commify(quote_data['total_val'])}`
                :chart: Dollar Change: `${self.bot.commify(quote_data['holding_change_dollar'])}`
                :chart_with_upwards_trend: Percent Change: `{self.bot.commify(quote_data['holding_change_pct'])}%`

                __**Other Information**__
                :dollar: Average Buy Price: `${self.bot.commify(quote_data['buy_price'])}`
                :1234: Number of Shares: `{self.bot.commify(quote_data['quantity'])}`
                :money_with_wings: Invested Weight: `{self.bot.commify(quote_data['invested_weight'])}%`
                :bar_chart: Total Portfolio Weight: `{self.bot.commify(quote_data['total_weight'])}%`
                """,
                timestamp=datetime.datetime.now(),
                color=discord.Color.green() if quote_data['holding_change_pct'] >= 0 else discord.Color.red()
            )
            em.set_thumbnail(url=user.display_avatar)
            em.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar)
            quote_pages.append(em)

        # Create the select menu callback
        async def select_menu_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("You're not allowed to use this menu.", ephemeral=True)
            selected_page_value = interaction.data['values'][0]
            if selected_page_value == "Portfolio Overview":
                await paginator.goto_page(0, interaction=interaction)
            else:
                page_index = None
                for i, quote in enumerate(price_data):
                    if quote["ticker"] == selected_page_value:
                        page_index = i + 1
                await paginator.goto_page(page_index, interaction=interaction)

        # Generate the select menu and the select options
        menu = discord.ui.Select(placeholder="Select a Holding to View")
        menu_options = [
            discord.SelectOption(label=f"Portfolio Overview"),
        ]
        for quote in price_data:
            menu_options.append(
                discord.SelectOption(
                    label=f"{quote['name']} ({quote['ticker']})",
                    value=quote['ticker']
                )
            )
        menu.callback = select_menu_callback
        menu.options = menu_options
        view = discord.ui.View(menu)

        # Create the paginator and send it to the user
        paginator = pages.Paginator(pages=quote_pages, custom_view=view, use_default_buttons=False, show_indicator=False)
        await paginator.send(ctx)
    
    @commands.command(
        name="buy",
        brief="Buy a quote",
        description="Buy more shares of a quote for your portfolio. If you want to buy multiple shares at a time, supply the number of shares you wish to buy for the `quantity` parameter.\n\nIf you wish to place a limit order, provide `limit` for the `order_type` parameter and the specified price at which the order should execute for the `execute_price` parameter. All orders are treated as market orders by default so don't worry if you don't know what a limit order is.",
        extras={
            "usage_examples": ["AAPL", "XLE 5", "MSFT 23 limit 232.12"],
            "links": {
                "What is a limit order?": "https://www.investopedia.com/terms/l/limitorder.asp"
            }
        }
    )
    async def buy(self, ctx: commands.Context, ticker: str, quantity: str = "1", order_type: str = "market", execute_price: str = None):
        # TODO: Limit the number of quotes that people can buy to a maximum of 24
        await ctx.trigger_typing()
        
        # Format variables
        ticker = ticker.upper()
        order_type = order_type.upper()
        if order_type == "L": order_type = "LIMIT"
        if order_type == "M": order_type = "MARKET"
        if order_type not in ["MARKET", "LIMIT"]:
            return await ctx.send(f":x: The `order_type` parameter must be either `market` or `limit`.")
        try:
            quantity = int(quantity)
            if quantity < 1:
                return await ctx.send(":x: You have to buy at least one share.") 
        except ValueError:
            return await ctx.send(":x: The `quantity` parameter only accepts positive whole numbers.")
        if order_type == "LIMIT":
            if execute_price is None: # Make sure the user provides the execute_price
                raise commands.MissingRequiredArgument(param=inspect.Parameter("execute_price", inspect.Parameter.POSITIONAL_ONLY))
            try:
                execute_price = float(execute_price)
            except ValueError:
                return await ctx.send(":x: The `execute_price` parameter must be a valid number.")

        # Retrieve all data
        price_data = await self.bot.fetch_brief(ticker)
        portfolio_data = await self.bot.fetch_portfolio(ctx.author.id)
        balance = round(portfolio_data["balance"], 3)

        # Check if it is a valid ticker
        if price_data.get("error_code") is not None:
            return await ctx.send(":x: Please enter a valid ticker.")
        else:
            price = round(price_data.get("price"), 5)
            ticker = price_data.get("ticker")

        # Calculate total cost
        if order_type == "MARKET":
            total = round(price * quantity, 5)
        elif order_type == "LIMIT":
            total = round(execute_price * quantity, 5)
        
        # Check if the user has enough money to buy the stock
        if total > balance:
            return await ctx.send(":x: You don't have enough money to place this order.")
        
        # Check for other limit orders and see if the user will have enough cash left over to 
        # execute the other orders
        cursor = self.bot.tasks.find({"user_id": ctx.author.id, "_type": "LIMIT_ORDER", "limit_order_type": "BUY"})
        pending_limit_orders = await cursor.to_list(length=None)
        lo_msg = "```\n"
        for lo in pending_limit_orders:
            if lo["quantity"] * lo["execute_price"] > balance - total:
                lo_msg += f" - BUY {self.bot.commify(lo['quantity'])} shares of {lo['ticker']} @ ${self.bot.commify(lo['execute_price'])}\n"
        if lo_msg != "```\n":
            lo_msg = f"\nIf you make this trade, the following limit orders may not be able to execute:\n{lo_msg}```"
        else:
            lo_msg = ""
        
        # Generate the embed containing the order information
        if order_type == "MARKET":
            em = discord.Embed(
                title=f"BUY Order Summary for `{ticker}`",
                description=f"""
                :bar_chart: Current Price: `${self.bot.commify(price)}`
                :scales: Quantity: `{self.bot.commify(quantity)}`
                :money_with_wings: Total Order Cost: `${self.bot.commify(total)}`
                :moneybag: Current Cash Balance: `${self.bot.commify(balance)}`
                :gem: Ending Cash Balance: `${self.bot.commify(round(balance - total, 3))}`
                {lo_msg}
                :mouse_three_button: Click `Confirm` to proceed or `Cancel` to cancel the order
                """,
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
        elif order_type == "LIMIT":
            em = discord.Embed(
                title=f"Limit BUY Order Summary for `{ticker}`",
                description=f"""
                :bar_chart: Specified Price: `${self.bot.commify(execute_price)}`
                :scales: Quantity: `{self.bot.commify(quantity)}`
                :money_with_wings: Maximum Order Cost: `${self.bot.commify(round(execute_price * quantity, 5))}`
                :moneybag: Current Cash Balance: `${self.bot.commify(balance)}`
                {lo_msg}
                :mouse_three_button: Click `Confirm` to proceed or `Cancel` to cancel the order
                """,
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
        em.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.display_avatar)
        
        # View callbacks

        async def on_timeout():
            # Edit the embed to show the user that they have timed out
            em.title = ""
            em.description = ":alarm_clock: Timed out waiting for a response."
            em.color = discord.Color.red()
            em.timestamp = discord.Embed.Empty
            em.set_footer(text="", icon_url="")
            await m.edit(embeds=[em], view=view)
        
        async def on_confirm(btn: discord.ui.Button, interaction: discord.Interaction):
            if order_type == "LIMIT":
                await self.bot.tasks.insert_one(
                    {
                        "_type": "LIMIT_ORDER",
                        "user_id": ctx.author.id,
                        "limit_order_type": "BUY",
                        "ticker": ticker,
                        "quantity": quantity,
                        "execute_price": execute_price,
                        "timestamp": round(time.time()),
                        "notified": False
                    }
                )
            elif order_type == "MARKET":
                portfolio_data["balance"] = round(balance - total, 3)
                # Update the quantity and the buy price if the user already has the quote in their portfolio
                for quote in portfolio_data["portfolio"]:
                    if quote["ticker"] == ticker:
                        quote["quantity"] += quantity
                        quote["buy_price"] = round((quote["buy_price"] * quote["quantity"] + price * quantity) / (quote["quantity"] + quantity), 3)
                        break
                # Otherwise, add the quote to the portfolio in a new entry
                else:
                    portfolio_data["portfolio"].append(
                        {
                            "ticker": ticker,
                            "quantity": quantity,
                            "buy_price": price
                        }
                    )
                # Update the database
                await self.bot.portfolio.update_one(
                    {"_id": ctx.author.id},
                    {"$set": portfolio_data}
                )
                await self.bot.log_trade(ctx.author.id, "BUY", ticker.upper(), quantity, price) # Log the trade in the database as well
            # Edit the embed to show the user that the order was successful
            em.title = ""
            em.description = ":white_check_mark: Order placed successfully!"
            em.color = discord.Color.green()
            em.timestamp = discord.Embed.Empty
            em.set_footer(text="", icon_url="")
            # Remove all buttons from the view
            view.clear_items()
            # Update the embed and view
            await interaction.response.edit_message(embeds=[em], view=view)
        
        async def on_cancel(btn: discord.ui.Button, interaction: discord.Interaction):
            # Edit the embed to tell the user the order was cancelled
            em.title = ""
            em.description = ":x: Order cancelled"
            em.color = discord.Color.red()
            em.timestamp = discord.Embed.Empty
            em.set_footer(text="", icon_url="")
            # Remove all buttons from the view
            view.clear_items()
            # Update the embed and view
            await interaction.response.edit_message(embeds=[em], view=view)
        
        # Create the view
        view = ConfirmationView(ctx, on_timeout, on_confirm, on_cancel)

        # Send the embed and view
        m = await ctx.reply(embeds=[em], view=view)

    @commands.command(
        name="sell",
        brief="Sell a quote",
        description="Sell a quote from your portfolio. You can sell multiples shares at a time by providing the number of shares you wish to sell for the `quantity` parameter.\n\nIf you wish to place a limit order, provide `limit` for the `order_type` parameter and the specified price at which the order should execute for the `execute_price` parameter. All orders are treated as market orders by default so don't worry if you don't know what a limit order is.",
        extras={
            "usage_examples": ["AMZN", "XLE 15", "TSLA 234 limit 653.45"],
            "links": {
                "What is a limit order?": "https://www.investopedia.com/terms/l/limitorder.asp"
            }
        }
    )
    async def sell(self, ctx: commands.Context, ticker: str, quantity: str = "1", order_type: str = "market", execute_price: str = None):
        await ctx.trigger_typing()

        # Format variables
        ticker = ticker.upper()
        order_type = order_type.upper()
        if order_type == "L": order_type = "LIMIT"
        if order_type == "M": order_type = "MARKET"
        if order_type not in ["MARKET", "LIMIT"]:
            return await ctx.send(f":x: The `order_type` parameter must be either `market` or `limit`.")
        try:
            quantity = int(quantity)
            if quantity < 1:
                return await ctx.send(":x: You have to sell at least one share.")
        except ValueError:
            return await ctx.send(":x: Enter a positive whole number for the `quantity` parameter.")
        if order_type == "LIMIT":
            if execute_price is None: # Make sure the user provides the execute_price
                raise commands.MissingRequiredArgument(param=inspect.Parameter("execute_price", inspect.Parameter.POSITIONAL_ONLY))
            try:
                execute_price = float(execute_price)
            except ValueError:
                return await ctx.send(":x: The `execute_price` parameter must be a valid number.")

        # Retrieve all data
        price_data = await self.bot.fetch_brief(ticker)
        portfolio_data = await self.bot.fetch_portfolio(ctx.author.id)
        balance = round(portfolio_data["balance"], 3)

        # Check if it is a valid ticker
        if price_data.get("error_code") is not None:
            return await ctx.send(":x: Please enter a valid ticker symbol.")
        else:
            price = round(price_data.get("price"), 5)
            ticker = price_data.get("ticker")
        
        # Check if the user owns the quote. If they do, then store their user-specific data about it
        for quote in portfolio_data["portfolio"]:
            if quote["ticker"] == ticker:
                quote_data = quote
                break
        else:
            return await ctx.send(":x: You do not already own this quote.")

        # Calculate the total value of the order
        total = round(price * quantity, 5)
        
        # Check if the user owns enough shares to sell
        if quote_data["quantity"] < quantity:
            return await ctx.send(f":x: You don't have `{quantity}` shares.")
        
        # Check for other limit orders and see if the user will have enough cash left over to 
        # execute the other orders
        cursor = self.bot.tasks.find({"user_id": ctx.author.id, "_type": "LIMIT_ORDER", "limit_order_type": "SELL", "ticker": ticker})
        pending_limit_orders = await cursor.to_list(length=None)
        lo_msg = "```\n"
        for lo in pending_limit_orders:
            if lo["quantity"] > quote_data["quantity"] - quantity:
                lo_msg += f" - SELL {self.bot.commify(lo['quantity'])} shares of {lo['ticker']} @ ${self.bot.commify(lo['execute_price'])}\n"
        if lo_msg != "```\n":
            lo_msg = f"\nIf you make this trade, the following limit orders may not be able to execute:\n{lo_msg}```"
        else:
            lo_msg = ""
        
        # Generate the embed containing the order information
        if order_type == "MARKET":
            em = discord.Embed(
                title=f"SELL Order Summary for `{ticker}`",
                description=f"""
                :bar_chart: Current Price: `${self.bot.commify(price)}`
                :scales: Quantity: `{self.bot.commify(quantity)}`
                :money_with_wings: Total Order Value: `${self.bot.commify(total)}`
                :moneybag: Current Cash Balance: `${self.bot.commify(balance)}`
                :gem: Ending Cash Balance: `${self.bot.commify(round(balance + total, 3))}`
                {lo_msg}
                :mouse_three_button: Click `Confirm` to proceed or `Cancel` to cancel the order
                """,
                color=self.bot.green,
                timestamp=datetime.datetime.now()
            )
        elif order_type == "LIMIT":
            em = discord.Embed(
                title=f"Limit SELL Order Summary for `{ticker}`",
                description=f"""
                :bar_chart: Specified Price: `${self.bot.commify(execute_price)}`
                :scales: Quantity: `{self.bot.commify(quantity)}`
                :money_with_wings: Minimum Order Profit: `${self.bot.commify(round(execute_price * quantity, 5))}`
                :moneybag: Current Cash Balance: `${self.bot.commify(balance)}`
                {lo_msg}
                :mouse_three_button: Click `Confirm` to proceed or `Cancel` to cancel the order
                """,
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
        em.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.display_avatar)
        
        # View callbacks

        async def on_timeout():
            # Edit the embed to show the user that they have timed out
            em.title = ""
            em.description = ":alarm_clock: Timed out waiting for a response."
            em.color = discord.Color.red()
            em.timestamp = discord.Embed.Empty
            em.set_footer(text="", icon_url="")
            await m.edit(embeds=[em], view=view)
        
        async def on_confirm(btn: discord.ui.Button, interaction: discord.Interaction):
            if order_type == "MARKET":
                portfolio_data["balance"] = round(balance + total, 3)
                # Reduce the quantity of the quote by the quantity of the order
                for quote in portfolio_data["portfolio"]:
                    if quote["ticker"] == ticker:
                        quote["quantity"] -= quantity
                        break
                # Remove the quote from the portfolio if the user sold all of their shares
                if quote["quantity"] == 0:
                    portfolio_data["portfolio"].remove(quote)
                # Update the database
                await self.bot.portfolio.update_one(
                    {"_id": ctx.author.id},
                    {"$set": portfolio_data}
                )
                await self.bot.log_trade(ctx.author.id, "SELL", ticker.upper(), quantity, price) # Log the trade in the database as well
            elif order_type == "LIMIT":
                await self.bot.tasks.insert_one({
                    "_type": "LIMIT_ORDER",
                    "user_id": ctx.author.id,
                    "limit_order_type": "SELL",
                    "ticker": ticker,
                    "quantity": quantity,
                    "execute_price": execute_price,
                    "timestamp": round(time.time()),
                    "notified": False
                })
            # Edit the embed to show the user that the order was successful
            em.title = ""
            em.description = ":white_check_mark: Order placed successfully!"
            em.color = discord.Color.green()
            em.timestamp = discord.Embed.Empty
            em.set_footer(text="", icon_url="")
            # Remove all buttons from the view
            view.clear_items()
            # Update the embed and view
            await interaction.response.edit_message(embeds=[em], view=view)
        
        async def on_cancel(btn: discord.ui.Button, interaction: discord.Interaction):
            # Edit the embed to tell the user the order was cancelled
            em.title = ""
            em.description = ":x: Order cancelled"
            em.color = discord.Color.red()
            em.timestamp = discord.Embed.Empty
            em.set_footer(text="", icon_url="")
            # Remove all buttons from the view
            view.clear_items()
            # Update the embed and view
            await interaction.response.edit_message(embeds=[em], view=view)
        
        # Create the view
        view = ConfirmationView(ctx, on_timeout, on_confirm, on_cancel)

        # Send the embed and view
        m = await ctx.reply(embeds=[em], view=view)
    
    @commands.command(
        name="rewardstock",
        brief="Get shares of a random stock",
        description="If you vote for the bot on Top.gg, you will be rewarded with a random number of shares of a random stock. Run this command to see what the potential rewards could be if you claim your free shares. Note that you can only vote for the bot every 12 hours."
    )
    async def rewardstock(self, ctx: commands.Context):
        # Retrieve the data for all the reward stocks
        coroutines = []
        for stock in self.bot.reward_stocks:
            coroutines.append(self.bot.cnbc_data(stock))
        free_stock_data = list(await asyncio.gather(*coroutines))

        # Create the string that will contain the data about the free stocks
        stock_list_str = ""
        for stock in free_stock_data:
            ticker = stock['ticker']
            price = stock['price']
            shares = self.bot.reward_stocks[stock['ticker']]
            total = round(price * shares, 2)
            stock_list_str += f" - Ticker: `{ticker}` --- Current Price: `${self.bot.commify(price)}` x Shares: `{shares}` = Total: `${self.bot.commify(total)}`\n"

        # Generate the embed and view with the link to the vote page
        em = discord.Embed(
            title=":moneybag: Get A Free Stock",
            description=f"""
            If you vote for the bot on Top.gg, you will get a random number of shares of a random stock.

            Here are the stocks that you can get free shares of:
            {stock_list_str}

            Voting for the bot on Top.gg really helps us out, so please consider voting. :heart:
            """,
            color=self.bot.green,
        )
        view = discord.ui.View()
        vote_btn = discord.ui.Button(label="Vote", url=f"https://top.gg/bot/{self.bot.user.id}/vote")
        view.add_item(vote_btn)

        # Send the embed and view
        await ctx.reply(embeds=[em], view=view)
    
    @commands.command(
        name="orders",
        brief="View your pending orders",
        description="See all the pending orders you have placed previously and some details about them. If you no longer want an order to execute, you can use the `deleteorder` command to delete it."
    )
    async def view_pending_orders(self, ctx: commands.Context):
        await ctx.trigger_typing()

        # Retrieve all the user data
        cursor = self.bot.tasks.find({"_type": "LIMIT_ORDER", "user_id": ctx.author.id})
        limit_orders = await cursor.to_list(length=None)
        limit_orders.sort(key=lambda q: q['ticker']) # Sort alphabetically by ticker
        portfolio_data = await self.bot.fetch_portfolio(ctx.author.id)

        # Generate the text for the user
        limit_buy_text = "```"
        limit_sell_text = "```"
        for lo in limit_orders:
            # Handle BUY orders
            if lo['limit_order_type'] == "BUY":
                limit_buy_text += f"- {self.bot.commify(lo['quantity'])} shares of {lo['ticker']} @ ${self.bot.commify(lo['execute_price'])}\n"
            # Handle SELL orders
            elif lo['limit_order_type'] == "SELL":
                limit_sell_text += f"- {self.bot.commify(lo['quantity'])} shares of {lo['ticker']} @ ${self.bot.commify(lo['execute_price'])}\n"
        limit_buy_text += "```"
        limit_sell_text += "```"

        if limit_buy_text == "``````":
            limit_buy_text = "```No Pending Orders```"
        if limit_sell_text == "``````":
            limit_sell_text = "```No Pending Orders```"

        # Create the embed
        em = discord.Embed(
            title=f":hourglass: {ctx.author.name}'s Pending Orders",
            color=self.bot.green,
            timestamp=datetime.datetime.now()
        )
        em.add_field(name=":receipt: Limit BUY Orders", value=limit_buy_text, inline=False)
        em.add_field(name=":dollar: Limit SELL Orders", value=limit_sell_text, inline=False)

        await ctx.reply(embeds=[em])
    
    @commands.command(
        name="deleteorder",
        brief="Delete a pending order",
        description="Delete an order that you had previously placed that has not been filled yet. Provide the ticker for the quote whose order you wish to delete, and if you have multiple orders for that ticker, then click the correct button to delete the order.",
        aliases=["do"],
        extras={
            "usage_examples": ["AAPL", "MSFT", "BTC-USD"]
        }
    )
    async def delete_pending_order(self, ctx: commands.Context, ticker: str):
        # Format args
        ticker = ticker.upper()
        
        # Fetch all of the user's pending orders for the ticker from the database
        cursor = self.bot.tasks.find(
            {
                "_type": "LIMIT_ORDER",
                "user_id": ctx.author.id,
                "ticker": ticker
            }
        )
        pending_orders = await cursor.to_list(length=None)

        # Check if the user has any pending orders for the ticker
        if len(pending_orders) == 0:
            return await ctx.send(f":x: You do not have any pending orders for `{ticker}`.")
        
        # If the user only has one pending order for the ticker, remove it
        if len(pending_orders) == 1:
            await self.bot.tasks.delete_one(
                {
                    "_id": pending_orders[0]["_id"]
                }
            )
            return await ctx.send(f":white_check_mark: Your pending order for `{ticker}` has been removed.")
        
        # Create the embed containing all of the pending orders
        em = discord.Embed(
            title=f"Pending Orders for {ticker}",
            description="```",
            color=self.bot.green,
        )
        em.set_footer(text=f"Select the pending order to remove")
        
        # Generate the embed description
        for i, po in enumerate(pending_orders):
            em.description += f"[{i+1}] Limit {po['limit_order_type']} for {po['quantity']} shares @ ${po['execute_price']}\n"
        em.description += "```"

        # Declare the button callback
        async def btn_callback(interaction: discord.Interaction):
            # Check to make sure the correct user clicked the button
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message(":x: You're not allowed to click that button.", ephemeral=True)

            # Retrieve the selected order
            btn_id = int(interaction.data['custom_id'])
            selected_order = pending_orders[btn_id]

            # Remove the order from the database
            await self.bot.tasks.delete_one({"_id": selected_order["_id"]})
            await interaction.response.send_message(f":white_check_mark: Removed pending order for `{ticker}`.")
            
            # Regenerate the embed and disable all the buttons
            em.description = "```"
            for i, po in enumerate(pending_orders):
                if i == btn_id:
                    em.description += f"[{i+1}] DELETED\n"
                else:
                    em.description += f"[{i+1}] Limit {po['limit_order_type']} for {po['quantity']} shares @ ${po['execute_price']}\n"
            em.description += "```"
            em.set_footer(text="Pending order successfully deleted")
            view.disable_all_items()
            await interaction.followup.edit_message(m.id, embeds=[em], view=view)
        
        # Create the buttons and add them to the view
        btns = {}
        for i, po in enumerate(pending_orders):
            btns[i] = discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                label=f"[{i+1}]",
                custom_id=str(i),
            )
            btns[i].callback = btn_callback
        view = discord.ui.View(*list(btns.values()))

        # Send the embed and wait for the user to select a pending order
        m = await ctx.reply(embeds=[em], view=view)


def setup(bot):
    bot.add_cog(Portfolio(bot))