# cogs/utils.py - A cog to store all utility functions for ProfitGreen
import discord
from discord.ext import commands
from discord.ext import tasks

import topgg

from extras import *


class Utils(commands.Cog):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot
        self.bot.topggpy = topgg.DBLClient(bot, bot.topgg_token)

        self.update_stats.start()
    
    @tasks.loop(minutes=30)
    async def update_stats(self):
        """This function runs every 30 minutes to automatically update your server count."""
        try:
            await self.bot.topggpy.http.post_guild_count(10243, self.bot.shard_count, self.bot.shard_id) # Post a fake server count to Top.gg
            print(f"Posted server count to Top.gg")
        except Exception as e:
            print(f"Failed to post server count\n{e.__class__.__name__}: {e}")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Respond with the embed card of the quote if a quote is included in the message
        if "$" in message.content:
            await message.channel.trigger_typing()
            words = message.content.split(" ")
            for word in words:
                if "$" in word:
                    quote_data = await self.bot.fetch_quote(word.strip("$"))
                    if quote_data != False:
                        await message.reply(embeds=[await self.bot.prepare_card(quote_data)], mention_author=False)
        # Check if the user mentioned the bot and reply with the prefix
        if self.bot.user in message.mentions:
            prefix = (await self.bot.get_prefix(message))[-1]
            await message.channel.send(f"My prefix is `{prefix}`. Get started by typing `{prefix}help`")

    @commands.command()
    async def ping(self, ctx: commands.Context):
        await ctx.send(f"Pong! ({round(self.bot.latency * 1000)} ms)")

def setup(bot):
    bot.add_cog(Utils(bot))