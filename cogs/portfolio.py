import discord
from discord.ext import commands
from discord.ext import pages

import datetime

from extras import *


class Portfolio(commands.Cog, name="Portfolio Commands"):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot

        # Cog data
        self.emoji = ":dollar:"
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.portfolio.py is online")

    async def cog_before_invoke(self, ctx: commands.Context):
        # Make the user an account in the database if they don't have an account in the portfolio collection
        await self.bot.create_portfolio(ctx.author)
    
    def commify(self, n):
        """Adds commas to a number and returns it as a string.

        Args:
            n (float): The number of commify

        Returns:
            str: A string of the number with commas
        """
        return '{:,}'.format(n)

    @commands.command(
        name="portfolio",
        brief="Displays your portfolio",
        description="Shows a detailed view of your portfolio. This includes your total portfolio value, the amount of cash you have, your net worth, number of holdings, and also data about each individual holding. The data for each holding includes the total value of that holding, your gain/loss, the buy price, and the number of shares you own.",
        aliases=["myportfolio", "mp"]
    )
    async def portfolio(self, ctx: commands.Context):
        # Retrieve the user's portfolio data from the database
        portfolio_data = await self.bot.fetch_portfolio(ctx.author.id)
        balance = portfolio_data["balance"]
        portfolio = portfolio_data["portfolio"]

        # Check to make sure the user has quotes in their portfolio
        if portfolio == []:
            return await ctx.send(":x: You must buy an asset first. Do this by typing `,buy <ticker> <amount>`")

        # Retrive the current prices of the quotes in the user's portfolio
        coroutines = []
        for quote in portfolio:
            coroutines.append(self.bot.cnbc_data(quote["ticker"]))
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
            title=f"{ctx.author.display_name}'s Portfolio",
            description=f"""
            __**Portfolio Summary**__
            :moneybag: Total Portfolio Value: `${self.commify(total_val)}`
            :chart: Dollar Change: `${self.commify(dollar_change)}`
            :chart_with_upwards_trend: Percent Change: `{self.commify(pct_change)}%`

            __**Account Summary**__
            :credit_card: Net Worth: `${self.commify(net_worth)}`
            :dollar: Cash: `${self.commify(balance)}`
            :dividers: Percent Cash: `{self.commify(pct_cash)}%`

            __**Portfolio Statistics**__
            :card_index: Total Number of Holdings: `{self.commify(len(portfolio))}`
            :1234: Total Number of Shares: `{self.commify(total_num_shares)}`

            *Use the select menu below to view your holdings in more detail*
            """,
            timestamp=datetime.datetime.now(),
            color=discord.Color.green() if pct_change >= 0 else discord.Color.red()
        )
        summary_em.set_thumbnail(url=ctx.author.avatar.url)
        summary_em.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url)

        # Create the embeds for each quote in the user's portfolio
        quote_pages = [summary_em]
        for quote_data in price_data:
            em = discord.Embed(
                title=f"{ctx.author.display_name}'s Portfolio: `{quote_data['ticker']}`",
                description=f"""
                __**Holding Summary**__
                :moneybag: Total Value: `${self.commify(quote_data['total_val'])}`
                :chart: Dollar Change: `${self.commify(quote_data['holding_change_dollar'])}`
                :chart_with_upwards_trend: Percent Change: `{self.commify(quote_data['holding_change_pct'])}%`

                __**Other Information**__
                :dollar: Average Buy Price: `${self.commify(quote_data['buy_price'])}`
                :1234: Number of Shares: `{self.commify(quote_data['quantity'])}`
                :money_with_wings: Invested Weight: `{self.commify(quote_data['invested_weight'])}%`
                :bar_chart: Total Portfolio Weight: `{self.commify(quote_data['total_weight'])}%`
                """,
                timestamp=datetime.datetime.now(),
                color=discord.Color.green() if quote_data['holding_change_pct'] >= 0 else discord.Color.red()
            )
            em.set_thumbnail(url=ctx.author.avatar.url)
            em.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url)
            quote_pages.append(em)

        # Create the select menu callback
        async def select_menu_callback(interaction: discord.Interaction):
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
        description="Buy more shares of a quote for your portfolio. If you want to buy multiple shares at a time, supply the number of shares you wish to buy for the `quantity` parameter.",
        extras={
            "usage_examples": ["AAPL", "XLE 5", "MSFT 23"]
        }
    )
    async def buy(self, ctx: commands.Context, ticker: str, quantity: str = "1"):
        # TODO: Limit the number of quotes that people can buy to a maximum of 24
        # Format variables
        ticker = ticker.upper()
        if "-" in ticker: return await ctx.send(":x: Sorry, cryptocurrencies are not yet supprted, but will be soon.") # No crypto support yet :(
        try:
            quantity = int(quantity)
            if quantity < 1:
                return await ctx.send(":x: You have to buy at least one share.") 
        except ValueError:
            return await ctx.send(":x: The `quantity` parameter only accepts positive whole numbers.")

        # Retrieve all data
        price_data = await self.bot.cnbc_data(ticker)
        portfolio_data = await self.bot.fetch_portfolio(ctx.author.id)
        balance = round(portfolio_data["balance"], 3)

        # Check if it is a valid ticker
        if price_data.get("error_code") is not None:
            return await ctx.send(":x: Please enter a valid ticker.")
        else:
            price = round(price_data.get("price"), 3)

        # Calculate total cost
        total = round(price * quantity, 3)
        
        # Check if the user has enough money to buy the stock
        if total > balance:
            return await ctx.send(":x: You don't have enough money to place this order.")
        
        # Generate the embed containing the order information
        em = discord.Embed(
            title=f"BUY Order Summary for `{ticker}`",
            description=f"""
            :bar_chart: Current Price: `${self.commify(price)}`
            :scales: Quantity: `{self.commify(quantity)}`
            :money_with_wings: Total Order Cost: `${self.commify(total)}`
            :moneybag: Current Cash Balance: `${self.commify(balance)}`
            :gem: Ending Cash Balance: `${self.commify(round(balance - total, 3))}`

            :arrow_forward: Would you like to proceed with this order?
            
            :mouse_three_button: Click `Confirm` to proceed or `Cancel` to cancel the order
            """,
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        em.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar.url)
        
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
            # Edit the embed to show the user that the order was successful
            em.title = ""
            em.description = ":white_check_mark: Order successful!"
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
        view = ConfirmationView(on_timeout, on_confirm, on_cancel)

        # Send the embed and view
        m = await ctx.reply(embeds=[em], view=view)

    @commands.command(
        name="sell",
        brief="Sell a quote",
        description="Sell a quote from your portfolio. You can sell multiples shares at a time by providing the number of shares you wish to sell for the `quantity` parameter.",
        extras={
            "usage_examples": ["AMZN", "XLE 15", "TSLA 234"]
        }
    )
    async def sell(self, ctx: commands.Context, ticker: str, quantity: str = "1"):
        # Format variables
        ticker = ticker.upper()
        try:
            quantity = int(quantity)
            if quantity < 1:
                return await ctx.send(":x: You have to sell at least one share.")
        except ValueError:
            return await ctx.send(":x: Enter a positive whole number for the `quantity` parameter.")

        # Retrieve all data
        price_data = await self.bot.cnbc_data(ticker)
        portfolio_data = await self.bot.fetch_portfolio(ctx.author.id)
        balance = round(portfolio_data["balance"], 3)

        # Check if it is a valid ticker
        if price_data.get("error_code") is not None:
            return await ctx.send(":x: Please enter a valid ticker symbol.")
        else:
            price = round(price_data.get("price"), 3)
        
        # Check if the user owns the quote. If they do, then store their user-specific data about it
        for quote in portfolio_data["portfolio"]:
            if quote["ticker"] == ticker:
                quote_data = quote
                break
        else:
            return await ctx.send(":x: You do not already own this quote.")

        # Calculate the total value of the order
        total = round(price * quantity, 3)
        
        # Check if the user owns enough shares to sell
        if quote_data["quantity"] < quantity:
            return await ctx.send(f":x: You don't have `{quantity}` shares.")
        
        # Generate the embed containing the order information
        em = discord.Embed(
            title=f"SELL Order Summary for `{ticker}`",
            description=f"""
            :bar_chart: Current Price: `${self.commify(price)}`
            :scales: Quantity: `{self.commify(quantity)}`
            :money_with_wings: Total Order Value: `${self.commify(total)}`
            :moneybag: Current Cash Balance: `${self.commify(balance)}`
            :gem: Ending Cash Balance: `${self.commify(round(balance + total, 3))}`

            :arrow_forward: Would you like to proceed with this order?
            
            :mouse_three_button: Click `Confirm` to proceed or `Cancel` to cancel the order
            """,
            color=self.bot.green,
            timestamp=datetime.datetime.now()
        )
        em.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar.url)
        
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
            # Edit the embed to show the user that the order was successful
            em.title = ""
            em.description = ":white_check_mark: Order successful!"
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
        view = ConfirmationView(on_timeout, on_confirm, on_cancel)

        # Send the embed and view
        m = await ctx.reply(embeds=[em], view=view)
    
    @commands.command(
        name="freestock",
        brief="Claim free shares of a random stock",
        description="If you vote for the bot on Top.gg, you will be rewarded with a random number of shares of a random stock. Run this command to see what the potential winnings could be if you claim your free shares. Note that you can only vote for the bot every 12 hours."
    )
    async def freestock(self, ctx: commands.Context):
        # Retrieve the data for all the reward stocks
        coroutines = []
        for stock in self.bot.reward_stocks:
            coroutines.append(self.bot.cnbc_data(stock))
        free_stock_data = list(await asyncio.gather(*coroutines))

        # Create the string that will contain the data about the free stocks
        stock_list_str = ""
        for stock in free_stock_data:
            stock_list_str += f" - Ticker: `{stock['ticker']}` --- Current Price: `${self.commify(stock['price'])}`\n"

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
        vote_btn = discord.ui.Button(label="Vote", style=discord.ButtonStyle.green, url=f"https://top.gg/bot/{self.bot.user.id}/vote")
        view.add_item(vote_btn)

        # Send the embed and view
        await ctx.reply(embeds=[em], view=view)


def setup(bot):
    bot.add_cog(Portfolio(bot))