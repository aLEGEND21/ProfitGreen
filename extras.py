import discord 
from discord.ext.commands import Bot

import aiohttp
import asyncio
import datetime
import csv
import asyncio
import sqlite3
import functools
import ssl
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


class ProfitGreenBot(Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Connect to the database
        self.db_client = motor.motor_asyncio.AsyncIOMotorClient(Config.DB_CONNECTION_STRING)
        self.db: motor.motor_asyncio.AsyncIOMotorDatabase = self.db_client["ProfitGreen"]
        self.portfolio: motor.motor_asyncio.AsyncIOMotorCollection = self.db["Portfolio"]

        # Bot settings
        self._emojis = {
            "profitgreen": "<:profitgreen:982696451924709436>"
        }
        self.green = discord.Color.from_rgb(38, 186, 156)
    
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
                result = {"error_code": 404}
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
        # TODO: Make this run fetch_quote if the ticker is a crypto
    
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
        
        return em
    
    async def fetch_historical_prices(self, quote_ticker: str, time_period: datetime.timedelta):
        """Fetch the historical prices of a stock or crypto from Yahoo Finance. Provide the 
        quote's ticker and the time period over which you would like to fetch the prices.

        Args:
            quote_ticker (str): The ticker of the quote to fetch.
            time_period (datetime.timedelta): A timedelta of the time period over which you would like
                to fetch the data from.

        Returns:
            bool or dict, int: False if the quote couldn't be found or the dict containing {date: price}. Date
                is formatted as YYYY-MM-DD or as datetime.datetime.strftime "%Y-%m-%d". If the function doesn't
                return False, it will return the interval at which it skipped the data in order to improve 
                processing speed in addition to the dict.
        """
        
        # Convert args to lowercase
        quote_ticker = quote_ticker.lower()
        
        # Construct the time periods
        period2 = datetime.datetime.today()
        period1 = period2 - time_period
        period2 = str(round(period2.timestamp()))
        period1 = str(round(period1.timestamp()))

        # Replace the url with the correct quote url
        #url = "https://finance.yahoo.com/quote/<quote>/history?period1=<period1>&period2=<period2>"
        url = "https://query1.finance.yahoo.com/v7/finance/download/<quote>?period1=<period1>&period2=<period2>"
        url = url.replace("<quote>", quote_ticker)
        url = url.replace("<period1>", period1)
        url = url.replace("<period2>", period2)

        # Make the request to the url
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as req:
                
                csv_output = await req.text()

                # Return false if the quote could not be found
                if "404 Not Found" in csv_output:
                    return False, 0
                
                # The data will have been returned as a CSV string, which needs to be converted into a 
                # list containing all the data
                lines = csv_output.splitlines()
                reader_output = csv.reader(lines)
                all_price_data = list(reader_output)
                
                # Set the interval at which the data should be processed to improve processing speed
                if len(all_price_data) > 365:
                    interval = round(len(all_price_data) / 150)
                else:
                    interval = 1

                # Extract the closing prices and dates from the data
                closing_prices = {}
                for day_num in range(1, len(all_price_data)-1, interval): # Skip first row as it contains the table header
                    day_data = all_price_data[day_num]
                    # Ignore dividends
                    if len(day_data) == 2:
                        continue
                    date = day_data[0] # Date is the first data point
                    close_price = float(day_data[4]) # Price is the 5th data point
                    closing_prices[date] = close_price
                    await asyncio.sleep(0.001) # Allow other processes running on the same thread to be processed
        
        return closing_prices, interval


class TasksDataBase:

    def __init__(self, db_path="./tasks.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._create_price_target_table()
    
    '''def _connect(self):
        """Makes a connection to the database and establishes the cursor. This should be used in
        order to provide auto connect and disconnect support for the database. The _disconnect
        function should be run once the database function has finished running.
        """
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
    
    def _disconnect(self):
        """Safely closes the connection to the database.
        """
        self.conn.close()'''
    
    def _create_price_target_table(self):
        """Creates the price targets table if it doesn't already exist.
        """
        query = """
            CREATE TABLE IF NOT EXISTS PRICE_TARGETS (
            author_id INTEGER,
            quote_ticker STRING,
            target_price REAL
            )
        """
        self.cursor.execute(query)
    
    def disconnect(self):
        """Safely closes the connection to the database.
        """
        self.conn.close()
    
    def add_price_target(self, author_id: int, quote_ticker: str, target_price: float):
        """Adds a new price target to the database.

        Args:
            author_id (int): The id of the user who requested the price target
            quote_ticker (str): The ticker of the quote
            target_price (float): The target price at which the user should be notified at
        """
        query = """INSERT INTO PRICE_TARGETS values (?, ?, ?)"""
        self.cursor.execute(query, (author_id, quote_ticker, target_price))
        self.conn.commit()
    
    def remove_price_target(self, author_id: int, quote_ticker: str):
        """Removes a previously created price target from the database.

        Args:
            author_id (int): The Discord id of the author of the price target
            quote_ticker (str): The ticker of the quote that had been the target of the price target
        
        Returns:
            bool: True or False depending on if the price target was successfully deleted
        """
        # Make the query to the database. Also, record the number of price targets present
        # in the database before the operation and after.
        query = """
            DELETE FROM PRICE_TARGETS WHERE
            author_id = ? AND
            quote_ticker = ?
        """
        num_targets_before = len(self.get_user_price_targets(author_id))
        self.cursor.execute(query, (author_id, quote_ticker))
        self.conn.commit()
        num_targets_after = len(self.get_user_price_targets(author_id))

        # Detect if the number of price targets decreased. If they did, then the price target
        # was successfully deleted. Otherwise, the operation failed
        if num_targets_before == num_targets_after:
            return False
        else:
            return True
    
    def get_all_price_targets(self):
        """Gets all price targets from the task database. This is useful if the price targets
        need to be checked to see if they have been met.

        Returns:
            list: A list of tuples of all price targets, organized as [(author_id, quote_ticker, target_price), ...]
        """
        query = """SELECT * FROM PRICE_TARGETS"""
        price_targets = self.cursor.execute(query).fetchall()

        return price_targets
    
    def get_user_price_targets(self, user_id: int):
        """Get all price targets for a specific user.

        Args:
            user_id (int): The Discord id of the user
        
        Returns:
            list: A list of tuples containing the price targets the user has set.
        """
        # Make the query to the database to get all price targets
        query = """SELECT * FROM PRICE_TARGETS"""
        price_targets = self.cursor.execute(query)
        
        # Add the price targets belonging to the user to user_price_targets
        user_price_targets = []
        for pt in price_targets:
            if pt[0] == user_id:
                user_price_targets.append(pt)

        return user_price_targets


class ConfirmationView(discord.ui.View):

    def __init__(self, _on_timeout, on_confirm, on_cancel, timeout: int = 180):
        super().__init__(timeout=timeout)
        self._on_timeout = _on_timeout
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, btn: discord.ui.Button, interaction: discord.Interaction):
        await self.on_confirm(btn, interaction)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel(self, btn: discord.ui.Button, interaction: discord.Interaction):
        await self.on_cancel(btn, interaction)
    
    async def on_timeout(self):
        self.clear_items()
        await self._on_timeout()