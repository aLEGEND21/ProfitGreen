import discord
from discord.ui import View
from discord.ui import Button
from discord.ext import commands

import aiohttp
import datetime
import pandas as pd
import pandas_datareader.data as web
import plotly.express as px
import os
from bs4 import BeautifulSoup
#from matplotlib import pyplot as plt # No longer used
#from matplotlib import dates as mdates # No longer used

from extras import *
from config import Config


class Commands(commands.Cog, name="General Commands"):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot

        # Cog data
        self.emoji = ":hash:"

    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.commands is online")
    
    # TODO: Figure out why the context menu disappears after message commands are run
    '''
    @commands.message_command(
        name="Show Quote Data"
    )
    async def show_quote_data_from_message(self, ctx: discord.ApplicationContext, message: discord.Message):
        found = False # Track if any results were found
        if "$" in message.content:
            await ctx.defer()
            words = message.content.split(" ")
            for word in words:
                if "$" in word:
                    quote_data = await self.bot.fetch_quote(word.strip("$"))
                    if quote_data.get("error") is None:
                        found = True
                        await ctx.respond(embeds=[await self.bot.prepare_card(quote_data)])
        if not found:
            await ctx.respond(":x: No quotes found in the message", ephemeral=True)
    '''

    @commands.command(
        name="quote",
        brief="Shows current data about a ticker",
        description="Get a detailed message containing information about a stock or crypto.",
        extras={
            "usage_examples": ["AAPL", "ETH-USD", "DOGE"]
        }
    )
    async def quote(self, ctx: commands.Context, quote_ticker: str):
        # Simulate the bot typing in case the request takes long
        await ctx.trigger_typing()

        # Convert the arg to uppercase and remove any unnecessary symbols
        quote_ticker = quote_ticker.upper()
        quote_ticker = quote_ticker.strip("<>()[]{}")

        # Fetch quote data
        quote_data = await self.bot.fetch_quote(quote_ticker)
        
        # If the request is invalid, tell the user the quote could not be found
        if quote_data.get("error") is not None:
            if quote_data.get("similar_tickers") == []:
                return await ctx.reply(f"I could not find a quote with ticker `{quote_ticker}`.")
            else:
                em = discord.Embed(
                    title=":question: Quote Not Found",
                    color=discord.Color.brand_red(),
                    timestamp=datetime.datetime.now()
                )
                desc = f"Could Not Find `{quote_ticker}`\n\n__**Similar Tickers:**__"
                for count, sim_quote in enumerate(quote_data.get("similar_tickers")):
                    # If there are more than 5 similar tickers, stop adding them
                    if count >= 5:
                        break
                    desc += f"\n - **Name**: `{sim_quote['name']}`, **Ticker**: `({sim_quote['symbol']})`"
                em.description = desc
                return await ctx.send(embeds=[em])
        
        # Prepare and send the emebed card
        em = await self.bot.prepare_card(quote_data)
        await ctx.reply(embeds=[em], mention_author=False)
    
    # Commands that have not been completed yet
    @commands.command(
        name="chart",
        brief="Displays a price chart for a ticker",
        description="Displays a price chart of the specified stock or crypto. You can provide the `time_period` argument to specify how long ago the chart shows prices from, or you can leave it out so that you can use buttons below the chart to select the time period.",
        extras={
            "usage_examples": ["AAPL 9m", "BTC-USD 2y", "DOGE 24d"]
        }
    )
    async def chart(self, ctx: commands.Context, quote_ticker: str, time_period: str="6m"):
        await ctx.trigger_typing()

        # Format arguments
        quote_ticker = quote_ticker.upper()
        quote_ticker = quote_ticker.strip("<>()[]{}")
        time_period = time_period.lower()

        # Parse time_period input. Set formatting_error to True if there is an
        # issue with the way the user formatted their input. Otherwise, construct 
        # the timedeltas.
        formatting_error = False
        if time_period[-1] == "d":
            if time_period[:-1].isnumeric():
                time_period = datetime.timedelta(days=int(time_period[:-1]))
            else:
                formatting_error = True
        elif time_period[-1] == "m":
            if time_period[:-1].isnumeric():
                time_period = datetime.timedelta(days=int(time_period[:-1])*30)
            else:
                formatting_error = True
        elif time_period[-1] == "y":
            if time_period[:-1].isnumeric():
                time_period = datetime.timedelta(days=int(time_period[:-1])*365)
            else:
                formatting_error = True
        else:
            formatting_error = True
        
        # Send a message and return if there was a formatting error
        if formatting_error:
            indent = "\u200b " * 4
            
            # Generate the valid command usage. If the bot has just been started, ctx.command will
            # not have the usage_examles attribute which is why we check for it with hasattr().
            usage_examples_text = ""
            if hasattr(ctx.command, "usage_examples"):
                usage_examples_text = "\nHere are some examples of valid command usage:\n"
                for ex in ctx.command.usage_examples:
                    usage_examples_text += f"{indent}- `{ctx.prefix}{ctx.command.name} {ex}`\n"
            
            # Create the embed
            em = discord.Embed(
                title=":x: Invalid Time Period",
                description=f"""
                Please provide valid formatting for the time period argument.

                The time period must be formatted as follows: `<number><time_period_type>`.
                The number must be a valid number. The time period type must be one of the following:
                {indent}- `d` for days
                {indent}- `m` for months
                {indent}- `y` for years
                {usage_examples_text}

                Alternatively, if you leave out the time period, you will be able to select from various time periods using buttons below the chart.
                
                Type `{ctx.prefix}help chart` for more information.
                """,
                color=discord.Color.red()
            )
            return await ctx.reply(embeds=[em])
        
        # Prevent the user from supplying less than 7 days to prevent the chart from having too
        # few data points. Also prevent the user from supplying a date farther back than Jan 1, 1970
        if time_period < datetime.timedelta(days=7):
            return await ctx.send(f"Please provide a value for `time period` that is greater than `7 days`.")
        elif datetime.datetime.today() - time_period < datetime.datetime(1970, 1, 1):
            return await ctx.send(f"The value you provided for `time_period` is too long ago.")        

        async def generate_chart_embed(quote_ticker: str, period1: datetime.datetime, period2: datetime.datetime):
            # Retrieve all the data
            @insensitive_ticker
            async def get_data(self, quote_ticker: str, period1: datetime.datetime, period2: datetime.datetime): # self is required so that the command can be used with the insensitive_ticker decorator
                loop = asyncio.get_event_loop()
                try:
                    output = await loop.run_in_executor(None, lambda: web.DataReader(quote_ticker, 'yahoo', period1, period2))
                except:
                    return {
                        "error": "Could not retrieve data from Yahoo Finance.",
                        "error_code": 404
                    } # Ticker is invalid
                output = output['Close']
                df = pd.DataFrame(output)
                return df
            df = await get_data(self, quote_ticker, period1, period2)
            if type(df) == dict: # 404 not found
                return False
            
            # Record the line and embed colors
            if df.iloc[-1]['Close'] > df.iloc[0]['Close']:
                color = ("Green", discord.Color.green())
            elif df.iloc[-1]['Close'] < df.iloc[0]['Close']:
                color = ("Red", discord.Color.red())
            else:
                color = ("Gray", discord.Color.light_gray())
            
            # Generate and format the chart
            chart = px.line(df, title=f"{quote_ticker.upper()} Historical Price Chart ({period1.strftime('%b %d, %Y')} - {period2.strftime('%b %d, %Y')})", render_mode="") # For some reason, if render_mode="" is not specified, the line color is black for long time periods
            chart.update_traces({"line_color": color[0]}) # Set line color
            chart.update_layout({"plot_bgcolor": "#FFFFFF"}, title_x=0.5) # Change the bg line color and center the title
            chart.update_xaxes(title_text="") # Remove text from x-axis
            chart.update_yaxes(title_text=f"", gridcolor="#EEEEEE", linewidth=1) # Remove text from y-axis and add gridlines in the background
            chart.update_layout(showlegend=False)
            chart.write_image(f"{quote_ticker.upper()}_delete.png")

            # Send the saved image on Discord.
            #
            # Send the image file to a muted logging channel, extract the url, 
            # and delete it.
            img_file = discord.File(f"{quote_ticker.upper()}_delete.png")
            log_channel = await self.bot.fetch_channel(self.bot.log_channels[0])
            msg = await log_channel.send(files=[img_file])
            img_url = msg.attachments[0].url
            await msg.delete()
            os.remove(f"{quote_ticker.upper()}_delete.png") # Delete the saved image

            em = discord.Embed(
                title=f"{quote_ticker.upper()} Price Chart",
                color=color[1]
            )
            em.set_image(url=img_url)
            em.set_footer(text="Sourced From Yahoo Finance", icon_url="https://cdn.discordapp.com/attachments/812338726557450240/957714639637069874/favicon.png")
            em.timestamp = datetime.datetime.now()
            
            return em
        
        # Declare the callback for whenever the user clicks on one of the time period buttons
        async def timespan_selected(interaction: discord.Interaction):
            btn_id = interaction.data['custom_id']
            # Enable all of the buttons and disable the selected button since it has been selected
            for b in buttons:
                buttons[b].disabled = False
                buttons[b].style = blurple
            buttons[btn_id].disabled = True
            buttons[btn_id].style = green
            view.children = list(buttons.values())
            # Get the time periods
            time_period = {
                "7d": datetime.timedelta(days=7),
                "1m": datetime.timedelta(days=30),
                "6m": datetime.timedelta(days=180),
                "1y": datetime.timedelta(days=365),
                "5y": datetime.timedelta(days=1825)
            }
            time_period = time_period[btn_id]
            period2 = datetime.datetime.now()
            period1 = period2 - time_period
            # Generate the embed and update everything
            em = await generate_chart_embed(quote_ticker, period1, period2)
            await interaction.response.edit_message(embeds=[em], view=view)

        # Generate the buttons and add them to the view
        blurple = discord.ButtonStyle.blurple
        green = discord.ButtonStyle.green
        buttons = {
            '7d': Button(label="7d", custom_id="7d", style=blurple),
            '1m': Button(label="1m", custom_id="1m", style=blurple),
            '6m': Button(label="6m", custom_id="6m", style=green, disabled=True),
            '1y': Button(label="1y", custom_id="1y", style=blurple),
            '5y': Button(label="5y", custom_id="5y", style=blurple)
        }
        for b in buttons: buttons[b].callback = timespan_selected
        view = View(*list(buttons.values()))
        
        # Construct the time periods
        period2 = datetime.datetime.today()
        period1 = period2 - time_period

        # Generate the embed with chart and check if the ticker couldn't be found
        em = await generate_chart_embed(quote_ticker, period1, period2)
        if em is False:
            return await ctx.send(f":x: I couldn't find a quote with ticker `{quote_ticker}`")
        
        # Send the embed with view if the user didn't supply the time period. Otherwise, send only
        # the embed containing the price chart
        if time_period == datetime.timedelta(days=180):
            await ctx.reply(embeds=[em], view=view)
        else:
            await ctx.reply(embeds=[em])
    
    @commands.command(
        name="techchart",
        brief="Displays a technical analysis chart",
        description="Displays a technical analysis chart for the specified ticker symbol.",
        extras={
            "usage_examples": ["AAPL", "MSFT", "TSLA"]
        }
    )
    async def techchart(self, ctx: commands.Context, ticker: str):
        # Convert the arg to uppercase and remove any unnecessary symbols
        ticker = ticker.upper()
        ticker = ticker.strip("<>()[]{}")

        # Tell the user that crypto is not supported if they specify a crypto
        if "-" in ticker:
            return await ctx.reply("Sorry, crypto is not yet supported for this command.")

        # Generate the embed and send it to the user
        chart_url = f"https://stockcharts.com/c-sc/sc?s={ticker}&p=D&b=5&g=0&i=0&r=1653691828431"
        em = discord.Embed(
            title=f"Technical Analysis Chart for {ticker.upper()}",
            timestamp=datetime.datetime.now(),
            color=discord.Color.blurple()
        )
        em.set_image(url=chart_url)
        em.set_footer(text="Sourced From StockCharts.com", icon_url="https://stockcharts.com/favicon.ico")
        await ctx.reply(embeds=[em], mention_author=False)
    
    @commands.command(
        name="sentiment",
        brief="Displays the sentiment of a stock",
        description="Shows the sentiment of the specified ticker symbol based on news articles retrieved and analyzed from the web. This includes the links to the articles as well so that you can read them yourself if you would like to. This command can only show the sentiment of stocks and no other asset types.",
        extras={
            "usage_examples": ["AAPL", "MSFT", "TSLA"]
        }
    )
    @commands.cooldown(3, 60, commands.BucketType.user)
    async def sentiment(self, ctx: commands.Context, ticker: str):
        """
        Example Response:
        {
            "items": "50",
            "sentiment_score_definition": "x <= -0.35: Bearish; -0.35 < x <= -0.15: Somewhat-Bearish; -0.15 < x < 0.15: Neutral; 0.15 <= x < 0.35: Somewhat_Bullish; x >= 0.35: Bullish",
            "relevance_score_definition": "0 < x <= 1, with a higher score indicating higher relevance.",
            "feed": [
                {
                    "title": "Top Wall Street analysts say these are the best stocks to beat the volatile market",
                    "url": "https://www.cnbc.com/2022/06/19/top-wall-street-analysts-say-to-buy-apple-bank-of-america.html",
                    "time_published": "20220619T124703",
                    "authors": [
                        "Tipranks.com Staff"
                    ],
                    "summary": "TipRanks analyst ranking service pinpoints Wall Street's best-performing stocks, including Apple and Bank of America.",
                    "banner_image": "https://image.cnbcfm.com/api/v1/image/107071810-16545476872022-06-06t174903z_694088903_rc2gmu93g5hb_rtrmadp_0_apple-developer.jpeg?v=1654547799&w=1920&h=1080",
                    "source": "CNBC",
                    "category_within_source": "Investing",
                    "source_domain": "www.cnbc.com",
                    "topics": [
                        {
                            "topic": "Technology",
                            "relevance_score": "0.5"
                        },
                        {
                            "topic": "Finance",
                            "relevance_score": "0.5"
                        }
                    ],
                    "overall_sentiment_score": -0.001195,
                    "overall_sentiment_label": "Neutral",
                    "ticker_sentiment": [
                        {
                            "ticker": "AAPL",
                            "relevance_score": "0.164431",
                            "ticker_sentiment_score": "0.040582",
                            "ticker_sentiment_label": "Neutral"
                        },
                        {
                            "ticker": "CBSU",
                            "relevance_score": "0.027597",
                            "ticker_sentiment_score": "-0.626318",
                            "ticker_sentiment_label": "Bearish"
                        }
                    ]
                }
            ]
        }
        """

        ticker = ticker.upper()

        # Make the request to get the data
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&apikey={Config.ALPHA_VANTAGE_API_KEY}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        
        # Handle the ticker not being found
        if "Information" in list(data.keys()):
            return await ctx.send(f":x: I couldn't get any sentiment data for `{ticker}`. Make sure that `{ticker}` is a stock.")
        else:
            feed = data["feed"] # Retrieve all the data
        
        # Get the overall sentiment and average it
        overall_sentiment = 0
        for item in feed:
            overall_sentiment += item["overall_sentiment_score"]
        overall_sentiment = round(overall_sentiment / len(feed), 2)

        # Convert the overall sentiment into words
        if overall_sentiment < -0.35:
            overall_sentiment_label = "Bearish"
        elif overall_sentiment < -0.15:
            overall_sentiment_label = "Somewhat-Bearish"
        elif overall_sentiment < 0.15:
            overall_sentiment_label = "Neutral"
        elif overall_sentiment < 0.35:
            overall_sentiment_label = "Somewhat-Bullish"
        else:
            overall_sentiment_label = "Bullish"

        em = discord.Embed(
            title=f":pushpin: Sentiment for `{ticker}`",
            timestamp=datetime.datetime.now(),
            color=self.bot.green
        )
        em.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar)

        # Get some of the relevant articles
        articles = []
        for i, item in enumerate(feed):
            if len(articles) == 3: # Only retrieve three articles
                break
            # Get the relevance score
            for t in item["ticker_sentiment"]:
                if t["ticker"] == ticker:
                    relavence_score = float(t["relevance_score"])
            if relavence_score > 0.5: # Only display articles with a high relevance score
                articles.append(item)
        else:
            articles = articles[:3] # Retrieve the first three articles if there weren't enough relevent articles


        # Construct the fields of the embed using the article data
        for i, item in enumerate(articles):
            # Get the sentiment
            for t in item["ticker_sentiment"]:
                if t["ticker"] == ticker:
                    sentiment = t
            em.add_field(
                name=f"\u200b",
                value=f"""
                **__[{item['title']}]({item['url']})__**
                {item['summary']}
                ***Sentiment: {sentiment['ticker_sentiment_label']} ({sentiment['ticker_sentiment_score']})***
                """,
                inline=False
            )
        
        # Display the overall sentiment
        em.description = f"**Overall Sentiment:** {overall_sentiment_label} ({overall_sentiment})"
        
        await ctx.send(embeds=[em])
    
    @commands.command(
        name="lookup",
        brief="Look up the ticker of a stock or crypto",
        description="Find the ticker symbol of a stock or crypto by typing the name of the company in for the `<name>` parameter. This will then display some potential matches for the name and the tickers associated with them.",
        extras={
            "usage_examples": ["Apple", "Bitcoin", "Microsoft"]
        }
    )
    async def lookup(self, ctx: commands.Context, *, name: str):
        await ctx.trigger_typing()

        # Generate the url
        url = f"https://finance.yahoo.com/lookup?s={name}"
        
        # Make the request to the site
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                html = await resp.text()
        
        # Parse the html to get the potential matches
        soup = BeautifulSoup(html, "html.parser")
        similar_tickers = []
        lookup_table = soup.find('table', {'class': 'lookup-table W(100%) Pos(r) BdB Bdc($seperatorColor) smartphone_Mx(20px)'})
        if lookup_table is not None:
            for row in lookup_table.tbody.find_all('tr'):
                items = row.findChildren('td')
                similar_tickers.append(
                    {
                        'symbol': items[0].text,
                        'name': items[1].text
                    }
                )
        
        # Format the similar tickers into a string
        desc = ""
        for count, sim_quote in enumerate(similar_tickers):
            # If there are more than 5 similar tickers, stop adding them
            if count >= 5:
                break
            desc += f"\n **Name**: `{sim_quote['name']}`, **Ticker**: `({sim_quote['symbol']})`"
        
        # Check to make sure at least one ticker was found
        if len(similar_tickers) == 0:
            desc = f"No results were found :slight_frown:"

        # Create the embed
        em = discord.Embed(
            title=f":pushpin: Ticker Lookup for `{name}`",
            description=desc,
            timestamp=datetime.datetime.now(),
            color=self.bot.green
        )
        em.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar)

        await ctx.send(embeds=[em])

    @commands.command(
        name="news",
        description="Displays current news about a stock or crypto.",
        hidden=True
    )
    async def news(self, ctx: commands.Context):
        await ctx.send("Sorry, this feature is still in development but will be completed soon.")


def setup(bot):
    bot.add_cog(Commands(bot))