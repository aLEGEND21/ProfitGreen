import discord 
from discord.ext import commands

import aiohttp
import asyncio
import datetime
import csv
import asyncio
import sqlite3
import functools
import ssl
import random
import cnbcfinance
import motor.motor_asyncio
from bs4 import BeautifulSoup
from decimal import Decimal

from config import Config


def insensitive_ticker(func):
    """A decorator that adds -USD to quote_ticker if it is needed for the function.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        output = await func(*args, **kwargs)
        if output.get("error") is not None:
            # Store the original list of similar tickers if the error is a 404 error
            if output.get("error_code") == 404:
                similar_tickers = output.get("similar_tickers")
            # Handle the ticker being an arg
            if kwargs.get("quote_ticker") is None:
                args = list(args)
                if "-" in args[1]:
                    args[1] = args[1].split("-")[0]
                else:
                    args[1] = args[1] + "-USD"
                args = tuple(args)
            # Handle the ticker being a kwarg
            else:
                if "-" in kwargs["quote_ticker"]:
                    kwargs["quote_ticker"] = kwargs["quote_ticker"].split("-")[0]
                else:
                    kwargs["quote_ticker"] = kwargs["quote_ticker"] + "-USD"
            output = await func(*args, **kwargs)
            # Update the output with the original list of similar tickers
            if output.get("error_code") == 404 and similar_tickers != []:
                output["similar_tickers"] = similar_tickers
        return output
    return wrapper


class ProfitGreenBot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Connect to the database
        self.db_client = motor.motor_asyncio.AsyncIOMotorClient(Config.DB_CONNECTION_STRING)
        self.db: motor.motor_asyncio.AsyncIOMotorDatabase = self.db_client["ProfitGreen"]
        self.portfolio: motor.motor_asyncio.AsyncIOMotorCollection = self.db["Portfolio"]
        self.tasks: motor.motor_asyncio.AsyncIOMotorCollection = self.db["Tasks"]

        # Bot settings
        self._emojis = {
            "profitgreen": "<:profitgreen:982696451924709436>"
        }
        self.green = discord.Color.from_rgb(38, 186, 156)
        self.portfolio_starting_value = 100000
        # Set the rewards
        rewards = ["META", "AMZN", "AAPL", "NFLX", "MSFT"]
        self.reward_stocks = {}
        for stock in rewards:
            self.reward_stocks[stock] = random.randint(15, 25)
    
    async def create_portfolio(self, user: discord.User):
        if await self.fetch_portfolio(user.id) is None:
            user = await self.fetch_user(user.id)
            await self.portfolio.insert_one(
                {
                    "_id": user.id,
                    "username": f"{user.name}#{user.discriminator}",
                    "balance": self.portfolio_starting_value,
                    "portfolio": []
                },
            )
    
    async def fetch_portfolio(self, user_id: int):
        # Get the user's portfolio
        cursor = self.portfolio.find({"_id": user_id})
        for doc in await cursor.to_list(100):
            if doc.get("_id") == user_id:
                return doc
        return None
    
    @insensitive_ticker
    async def cnbc_data(self, ticker: str):
        """Fetches the price of a stock or cryptocurrency from CNBC Finance's API. This should
        be used as a fast alternative to fetch_quote in order to get ONLY the price of a ticker.

        Args:
            ticker (str): The ticker of the stock or cryptocurrency to fetch the price of.

        Returns:
            dict: A dict containing the price or an error code.
        """
        # The function that will preform the synchronous request to the API
        def sync_request(ticker: str):
            quote_object = cnbcfinance.Cnbc(ticker)
            result = quote_object.get_quote()
            if result.get("last") is None:
                result = {
                    "error": "Could not find the ticker.",
                    "error_code": 404
                }
            else:
                result = {
                    "_type": result["assetType"].lower(),
                    "change": result["change"],
                    "change_pct": result["change_pct"],
                    "name": result["name"],
                    "open": float(result["open"]),
                    "price": float(result.get("last")),
                    "ticker": ticker
                }
            return result
        # We need to run the event loop in the executor in order to make this a non-blocking sync function
        # This way, other commands can still run while the data is being fetched, however the original
        # command will wait for this to finish
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, sync_request, ticker)
        return output
    
    @insensitive_ticker
    async def fetch_brief(self, quote_ticker: str):
        if quote_ticker.upper().endswith("-USD"):
            _output = await self.fetch_quote(quote_ticker)
            # Check that its a valid ticker
            if _output.get("error") is None:
                output = {
                    "_type": _output["_type"],
                    "change": _output["change-dollar"],
                    "change_pct": _output["change-percent"],
                    "name": _output["name"][:-len(f" ({quote_ticker}-USD)")], # Remove the ticker from the name
                    "open": float(_output["open"]),
                    "price": float(_output["price"]),
                    "ticker": _output["ticker"]
                }
            else:
                output = _output
            print(output)
        else:
            output = await self.cnbc_data(quote_ticker)
            print(output)
        return output
    
    @insensitive_ticker
    async def fetch_quote(self, quote_ticker: str):
        """Fetch a quote from the ProfitGreenAPI. This function accepts both Stock tickers 
        and Crypto tickers.

        Args:
            quote_ticker (str): The ticker of the stock or crypto that will be searched.

        Returns:
            bool or dict: False if the request failed or the data about the quote_ticker
        """
        # Generate the correct url
        url = "https://ProfitGreenAPI.alegend.repl.co/summary/<quote>"
        url = url.replace("<quote>", quote_ticker)

        # Make the request to the api
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
            async with session.get(url) as req:
                output = await req.json()
        
        # Return the data about the quote
        return output
    
    async def prepare_card(self, quote_data: dict):
        """Creates an embed containing information about a stock or crypto. Pass in the
        output from fetch_quote as quote_data so that this function can properly create
        the emebd.

        Args:
            quote_data (dict): The dict containing all the information about the quote.

        Returns:
            discord.Embed: The embed containing all information about the quote.
        """
        # Create the basic embed data
        em = discord.Embed(
                title=quote_data["name"]
            )
        em.set_footer(text="Sourced From Yahoo Finance", icon_url="https://cdn.discordapp.com/attachments/812338726557450240/957714639637069874/favicon.png")
        em.timestamp = datetime.datetime.now()
        # Change the color of the embed depending on if the asset when up or down
        if quote_data["change-dollar"] > 0:
            em.color = discord.Color.green()
        elif quote_data["change-dollar"] < 0:
            em.color = discord.Color.red()
        
        # Reformat all the integer or float values of the data into strings with commas
        for key in quote_data:
            if type(quote_data[key]) == int or type(quote_data[key]) == float:
                quote_data[key] = format(quote_data[key], ",f") # , = format with commas, f = convert scientific notation to decmial
                quote_data[key] = quote_data[key].rstrip("0").rstrip(".") # Remove the trailing zeros and decimal point

        if quote_data["_type"] == "crypto":
            em.description = f"""
            :dollar: **Price: ${quote_data["price"]}**
            :small_red_triangle: **Dollar Change: {quote_data["change-dollar"]}**
            :part_alternation_mark: **Percentage Change: {quote_data["change-percent"]}**
            :moneybag: Market Open Price: {quote_data["open"]}

            __**Metrics:**__
            :chart: Day's Range: {quote_data["days-range"]}
            :calendar: 52 Week Range: {quote_data["52-week-range"]}
            :bar_chart: Volume: {quote_data["volume"]}
            :coin: Market Cap: ${quote_data["market-cap"]}
            """

        elif quote_data["_type"] == "stock":
            em.description = f"""
            :dollar: **Price: ${quote_data["price"]}**
            :small_red_triangle: **Dollar Change: {quote_data["change-dollar"]}**
            :part_alternation_mark: **Percentage Change: {quote_data["change-percent"]}**
            :moneybag: Previous Close Price: {quote_data["previous-close"]}

            __**Metrics:**__
            :hammer: Bid: {quote_data["bid"]}
            :speaking_head: Ask: {quote_data["ask"]}
            :bar_chart: Volume: {quote_data["volume"]}
            :coin: Market Cap: ${quote_data["market-cap"]}

            __**Valuation:**__
            :star: Beta: {quote_data["beta"]}
            :diamond_shape_with_a_dot_inside: P/E Ratio: {quote_data["pe-ratio"]}
            :money_with_wings: EPS: {quote_data["eps"]}
            """
        
        elif quote_data["_type"] == "etf":
            em.description = f"""
            :dollar: **Price: ${quote_data["price"]}**
            :small_red_triangle: **Dollar Change: {quote_data["change-dollar"]}**
            :part_alternation_mark: **Percentage Change: {quote_data["change-percent"]}**
            :moneybag: Previous Close Price: {quote_data["previous-close"]}

            __**Metrics:**__
            :hammer: Bid: {quote_data["bid"]}
            :speaking_head: Ask: {quote_data["ask"]}
            :bar_chart: Volume: {quote_data["volume"]}
            :chart_with_upwards_trend: YTD Return: {quote_data["ytd-daily-total-return"]}

            __**Valuation:**__
            :star: Beta: {quote_data["beta"]}
            :diamond_shape_with_a_dot_inside: P/E Ratio: {quote_data["pe-ratio"]}
            :money_with_wings: Net Assets: ${quote_data["net-assets"]}
            :dollar: Net Assets Per Share: ${quote_data["nav"]}
            """

        """Sample crypto data: 
        {
            "52-week-range": "0.070037 - 0.444590", 
            "_type": "crypto", 
            "algorithm": "N/A", 
            "change-dollar": -0.004178, 
            "change-percent": "(-4.85%)", 
            "circulating-supply": "132.67B", 
            "days-range": "0.081641 - 0.088513", 
            "market-cap": "10.864B", 
            "max-supply": "N/A", 
            "name": "Dogecoin USD (DOGE-USD)", 
            "open": 0.085979, 
            "previous-close": 0.085979, 
            "price": 0.081886, 
            "start-date": "2013-12-15", 
            "ticker": "DOGE-USD", 
            "volume": 780823104.0, 
            "volume-24-hour": "780.82M", 
            "volume-24-hour-all-currencies": "780.82M"
        }
        """

        """Sample stock data:
        {
            "1-year-target-est": 69.84, 
            "52-week-range": "52.28 - 67.20", 
            "_type": "stock", 
            "ask": "63.06 x 1800", 
            "avg-volume": 18895850.0, 
            "beta": 0.58, 
            "bid": "63.05 x 1400", 
            "change-dollar": -0.12, 
            "change-percent": "(-0.18%)", 
            "days-range": "62.13 - 63.80", 
            "earnings-date": "Jul 19, 2022 - Jul 25, 2022", 
            "eps": 2.37, 
            "ex-dividend-date": "Jun 14, 2022", 
            "forward-dividend-and-yield": "1.76 (2.72%)", 
            "market-cap": "274.256B", 
            "name": "The Coca-Cola Company (KO)", 
            "open": 63.42, 
            "pe-ratio": 26.69, 
            "previous-close": 63.38, 
            "price": 63.26, 
            "ticker": "KO", 
            "volume": 11517617.0
        }"""

        """Sample ETF data:
        {
            "52-week-range": "269.28 - 408.71", 
            "_type": "etf", 
            "ask": "273.18 x 800", 
            "avg-volume": 77890915.0, 
            "beta": 1.07, 
            "bid": "273.18 x 1000", 
            "change-dollar": 0.9, 
            "change-percent": "(+0.33%)", 
            "days-range": "272.02 - 276.06", 
            "expense-ratio": "0.20%", 
            "inception-date": "1999-03-10", 
            "name": "Invesco QQQ Trust (QQQ)", 
            "nav": 275.38, 
            "net-assets": "166.33B", 
            "open": 272.18, 
            "pe-ratio": 3.61, 
            "previous-close": 271.39, 
            "price": 272.29, 
            "ticker": "QQQ", 
            "volume": 21471925.0, 
            "yield": "0.67%", 
            "ytd-daily-total-return": "-27.28%"
        }"""
        
        return em


class ConfirmationView(discord.ui.View):

    def __init__(self, ctx, _on_timeout, on_confirm, on_cancel, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self._on_timeout = _on_timeout
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
    
    @property
    def user(self):
        if isinstance(self.ctx, discord.ApplicationContext):
            return self.ctx.interaction.user
        else:
            return self.ctx.author

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, btn: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user != self.user:
            return await self.incorrect_user(interaction)
        self.stop()
        await self.on_confirm(btn, interaction)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel(self, btn: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user != self.user:
            return await self.incorrect_user(interaction)
        self.stop()
        await self.on_cancel(btn, interaction)
    
    async def on_timeout(self):
        self.clear_items()
        await self._on_timeout()
    
    async def incorrect_user(self, interaction: discord.Interaction):
        responses = [
            ":x: You can't click that button.",
            ":x: You're not the person who requested that action."
        ]
        await interaction.response.send_message(random.choice(responses), ephemeral=True)


class InvalidTicker(Exception):
    def __init__(self, ctx: commands.Context, ticker: str):
        self.ctx = ctx
        self.ticker = ticker