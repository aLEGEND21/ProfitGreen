import discord
from discord.ext import commands

import datetime
import os
from matplotlib import pyplot as plt
from matplotlib import dates as mdates

from extras import *


class Commands(commands.Cog):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.commands is online")

        # Add usage examples
        self.bot.get_command("quote").usage_examples = ["AAPL", "ETH-USD", "DOGE"]
        self.bot.get_command("chart").usage_examples = ["AAPL 9m", "BTC-USD 2y", "DOGE 24d"]
        self.bot.get_command("techchart").usage_examples = ["AAPL", "MSFT", "TSLA"]

    @commands.command(
        name="quote",
        description="Get a detailed message containing information about a stock or crypto.",
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
        description="Displays a price chart of the specified stock or crypto.",
    )
    async def chart(self, ctx: commands.Context, quote_ticker: str, time_period: str="6m"):
        async with ctx.typing(): # Some computations take a long time so make the user believe the bot is typing them out
            
            # Format arguments
            quote_ticker = quote_ticker.lower()
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
                return await ctx.send(f"Please use valid formatting. Ex: ,chart GME 15d OR ,chart amc 4m")
            
            # Prevent the user from supplying less than 7 days to prevent the chart from having too
            # few data points. Also prevent the user from supplying a date farther back than Jan 1, 1970
            if time_period < datetime.timedelta(days=7):
                return await ctx.send(f"Please provide a value for `time period` that is greater than `7 days`.")
            elif datetime.datetime.today() - time_period < datetime.datetime(1970, 1, 1):
                return await ctx.send(f"The value you provided for `time_period` is too long ago.")

            # Fetch the historical prices and notify the user if the ticker was not found
            historical_prices, skip_interval = await self.bot.fetch_historical_prices(quote_ticker, time_period)
            historical_prices: dict
            skip_interval: int
            if historical_prices == False:
                return await ctx.send(f"I could not find a stock or crypto of the ticker `{quote_ticker.upper()}`")
            
            # Format the x and y axis values
            x_axis_values = list(historical_prices.keys())
            for date in x_axis_values:
                x_axis_values[x_axis_values.index(date)] = mdates.date2num(datetime.datetime.strptime(date, "%Y-%m-%d"))
            y_axis_values = list(historical_prices.values())

            # Change plot settings and the plot the data using matplotlib. Reuse the color
            # var when sending the embed with the chart image on Discord
            if y_axis_values[0] < y_axis_values[-1]:
                color = ("green", discord.Color.green())
            elif y_axis_values[0] > y_axis_values[-1]:
                color = ("red", discord.Color.red())
            else:
                color = ("black", discord.Color.blurple())
            start_day = datetime.datetime.strptime(list(historical_prices.keys())[0], "%Y-%m-%d").strftime('%b %d, %Y')
            plt.title(f"{quote_ticker.upper()} Price Chart {start_day} - Today")
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %d, %Y'))
            interval = round(len(x_axis_values) / 3 * skip_interval) # Set the interval between the dates
            plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=interval))
            plt.plot(x_axis_values, y_axis_values, color=color[0])

            # Convert the graph into an image and save it
            plt.savefig(f"{quote_ticker.upper()}_delete.png")
            plt.clf()

            # Send the saved image on Discord.
            #
            # Send the image file to a muted logging channel, extract the url, 
            # and delete it.
            img_file = discord.File(f"{quote_ticker.upper()}_delete.png")
            log_channel = await self.bot.fetch_channel(self.bot.log_channels[0])
            msg = await log_channel.send(files=[img_file])
            img_url = msg.attachments[0].url
            await msg.delete()
            # Use the image url for the url of the image field on the embed and send.
            em = discord.Embed(title=f"{quote_ticker.upper()} Price Chart", color=color[1])
            em.set_image(url=img_url)
            em.set_footer(text="Sourced From Yahoo Finance", icon_url="https://cdn.discordapp.com/attachments/812338726557450240/957714639637069874/favicon.png")
            em.timestamp = datetime.datetime.now()
            await ctx.reply(embeds=[em], mention_author=False)

            # Delete the saved image
            os.remove(f"{quote_ticker.upper()}_delete.png")
    
    @commands.command(
        name="techchart",
        description="Displays a technical analysis chart for the specified ticker symbol.",
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
        name="news",
        description="Displays current news about a stock or crypto.",
        hidden=True
    )
    async def news(self, ctx: commands.Context):
        await ctx.send("Sorry, this feature is still in development but will be completed soon.")


def setup(bot):
    bot.add_cog(Commands(bot))