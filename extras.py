import discord 
from discord.ext.commands import Bot

import aiohttp
import datetime
import csv
import asyncio
import sqlite3
import functools
from bs4 import BeautifulSoup


def insensitive_ticker(func):
    """A decorator that adds -USD to quote_ticker if it is needed for the function.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        output = await func(*args, **kwargs)
        if output == False:
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
        return output
    return wrapper


class ProfitGreenBot(Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    @insensitive_ticker
    async def fetch_quote(self, quote_ticker: str):
        """Fetch a quote from Yahoo Finance. This function accepts both
        Stock tickers and Crypto tickers.

        Args:
            quote_ticker (str): The ticker of the stock or crypto that will be searched.

        Returns:
            bool or dict: False if the request failed or the data about the quote_ticker
        """

        # Convert args to lowercase
        quote_ticker = quote_ticker.lower()
        
        # Replace the url with the correct quote url
        url = "https://finance.yahoo.com/quote/<quote>"
        url = url.replace("<quote>", quote_ticker)

        # Make the request to the url
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as req:

                # Return false if the site redirected to the lookup page meaning that 
                # the quote could not be found
                if "lookup" in str(req.url):
                    return False
                
                # Create the soup
                soup = BeautifulSoup(await req.text(), "html.parser")
                
                # Return false if the quote is an ETF
                if soup.find("li", {"data-test": "HOLDINGS"}) is not None:
                    return False

                # Store the quote data in a dict which will be returned later
                quote_data = {}
                quote_data["quote_ticker"] = quote_ticker
                
                # Fetch different quote information if the quote is a crypto
                if url.endswith("-usd"):
                    quote_data["type"] = "crypto"
                    # Get the full crypto name
                    quote_data["name"] = soup.find(
                        "h1",
                        {
                            "class": "D(ib) Fz(18px)"
                        }
                    ).text
                    # Get the crypto price
                    quote_data["price"] = soup.find(
                        "fin-streamer", 
                        {
                            "data-symbol": quote_ticker.upper(), 
                            "data-field": "regularMarketPrice"
                        }
                    ).text
                    # Get the crypto's dollar change
                    quote_data["dollar_change"] = soup.find(
                        "fin-streamer",
                        {
                            "data-symbol": quote_ticker.upper(),
                            "data-field": "regularMarketChange"
                        }
                    ).findChild(
                        "span"
                    ).text
                    # Get the crypto's percentage change
                    quote_data["percent_change"] = soup.find(
                        "fin-streamer",
                        {
                            "data-symbol": quote_ticker.upper(),
                            "data-field": "regularMarketChangePercent"
                        }
                    ).findChild(
                        "span"
                    ).text
                    # Get the open price
                    quote_data["open_price"] = soup.find(
                        "td",
                        {
                            "data-test": "OPEN-value"
                        }
                    ).text
                    # Get the day's range
                    quote_data["days_range"] = soup.find(
                        "td",
                        {
                            "data-test": "DAYS_RANGE-value"
                        }
                    ).text
                    # Get the 52 week range
                    quote_data["52_week_range"] = soup.find(
                        "td",
                        {
                            "data-test": "FIFTY_TWO_WK_RANGE-value"
                        }
                    ).text
                    # Get the crypto's market cap
                    quote_data["market_cap"] = soup.find(
                        "td",
                        {
                            "data-test": "MARKET_CAP-value"
                        }
                    ).text
                    # Get the crypto's volume
                    quote_data["volume"] = soup.find(
                        "fin-streamer",
                        {
                            "data-symbol": quote_ticker.upper(),
                            "data-field": "regularMarketVolume"
                        }
                    ).text

                # Fetch certain quote information if the quote is a stock
                else:
                    quote_data["type"] = "stock"
                    # Get the full crypto name
                    quote_data["name"] = soup.find(
                        "h1",
                        {
                            "class": "D(ib) Fz(18px)"
                        }
                    ).text
                    # Get the stock price
                    quote_data["price"] = soup.find(
                        "fin-streamer", 
                        {
                            "data-symbol": quote_ticker.upper(), 
                            "data-field": "regularMarketPrice"
                        }
                    ).text
                    # Get the stock's dollar change
                    quote_data["dollar_change"] = soup.find(
                        "fin-streamer",
                        {
                            "data-symbol": quote_ticker.upper(),
                            "data-field": "regularMarketChange"
                        }
                    ).findChild(
                        "span"
                    ).text
                    # Get the stock's percentage change
                    quote_data["percent_change"] = soup.find(
                        "fin-streamer",
                        {
                            "data-symbol": quote_ticker.upper(),
                            "data-field": "regularMarketChangePercent"
                        }
                    ).findChild(
                        "span"
                    ).text
                    # Get the previous close price
                    quote_data["previous_close_price"] = soup.find(
                        "td",
                        {
                            "data-test": "PREV_CLOSE-value"
                        }
                    ).text
                    # Get the bid
                    quote_data["bid"] = soup.find(
                        "td",
                        {
                            "data-test": "BID-value"
                        }
                    ).text
                    # Get the ask
                    quote_data["ask"] = soup.find(
                        "td",
                        {
                            "data-test": "ASK-value"
                        }
                    ).text
                    # Get the volume
                    quote_data["volume"] = soup.find(
                        "fin-streamer",
                        {
                            "data-symbol": quote_ticker.upper(),
                            "data-field": "regularMarketVolume"
                        }
                    ).text
                    # Get the market cap
                    quote_data["market_cap"] = soup.find(
                        "td",
                        {
                            "data-test": "MARKET_CAP-value"
                        }
                    ).text
                    # Get the beta
                    quote_data["beta"] = soup.find(
                        "td",
                        {
                            "data-test": "BETA_5Y-value"
                        }
                    ).text
                    # Get the PE Ratio
                    quote_data["pe_ratio"] = soup.find(
                        "td",
                        {
                            "data-test": "PE_RATIO-value"
                        }
                    ).text
                    # Get the EPS
                    quote_data["eps"] = soup.find(
                        "td",
                        {
                            "data-test": "EPS_RATIO-value"
                        }
                    ).text

        # Return the data collected
        return quote_data
    
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
        if quote_data["dollar_change"].startswith("+"):
            em.color = discord.Color.green()
        elif quote_data["dollar_change"].startswith("-"):
            em.color = discord.Color.red()

        if quote_data["type"] == "crypto":
            em.description = f"""
            :dollar: **Price: ${quote_data["price"]}**
            :small_red_triangle: **Dollar Change: {quote_data["dollar_change"]}**
            :part_alternation_mark: **Percentage Change: {quote_data["percent_change"]}**
            :moneybag: Market Open Price: {quote_data["open_price"]}

            __**Metrics:**__
            :chart: Day's Range: {quote_data["days_range"]}
            :calendar: 52 Week Range: {quote_data["52_week_range"]}
            :bar_chart: Volume: {quote_data["volume"]}
            :coin: Market Cap: ${quote_data["market_cap"]}
            """

        elif quote_data["type"] == "stock":
            em.description = f"""
            :dollar: **Price: ${quote_data["price"]}**
            :small_red_triangle: **Dollar Change: {quote_data["dollar_change"]}**
            :part_alternation_mark: **Percentage Change: {quote_data["percent_change"]}**
            :moneybag: Previous Close Price: {quote_data["previous_close_price"]}

            __**Metrics:**__
            :hammer: Bid: {quote_data["bid"]}
            :speaking_head: Ask: {quote_data["ask"]}
            :bar_chart: Volume: {quote_data["volume"]}
            :coin: Market Cap: ${quote_data["market_cap"]}

            __**Valuation:**__
            :star: Beta: {quote_data["beta"]}
            :diamond_shape_with_a_dot_inside: P/E Ratio: {quote_data["pe_ratio"]}
            :money_with_wings: EPS: {quote_data["eps"]}
            """

        """Sample crypto data: 
        {
            'quote_ticker': 'doge-usd', 
            'type': 'crypto', 
            'name': 'Dogecoin USD (DOGE-USD)', 
            'price': '0.143747', 
            'dollar_change': '+0.008455', 
            'percent_change': '(+6.25%)', 
            'open_price': '0.135926', 
            'days_range': '0.135733 - 0.143970', 
            '52_week_range': '0.052269 - 0.737567', 
            'market_cap': '19.071B', 
            'volume': '1,362,078,720'
        }
        """

        """Sample stock data:
        {
            'quote_ticker': 'sklz', 
            'type': 'stock', 
            'name': 'Skillz Inc. (SKLZ)', 
            'price': '3.0700', 
            'dollar_change': '-0.2700', 
            'percent_change': '(-8.08%)', 
            'previous_close_price': '3.3400', 
            'bid': '3.0500 x 36900', 
            'ask': '3.4900 x 317700', 
            'volume': '9,617,138', 
            'market_cap': '1.258B', 
            'beta': 'N/A', 
            'pe_ratio': 'N/A', 
            'eps': '-0.6930'
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
