# cogs/utils.py - A cog to store all utility functions for ProfitGreen
import discord
from discord.ext import commands
from discord.ext import tasks

import topgg

from extras import *


class Utils(commands.Cog, name="Utility Commands"):

    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot
        self.bot.topggpy = topgg.DBLClient(bot, bot.topgg_token)

        self.update_stats.start()

        # Cog data
        self.emoji = ":gear:"
    
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
                    if quote_data.get("error") is None:
                        await message.reply(embeds=[await self.bot.prepare_card(quote_data)], mention_author=False)
        # Check if the user mentioned the bot and reply with the prefix
        if self.bot.user in message.mentions:
            prefix = (await self.bot.get_prefix(message))[-1]
            await message.channel.send(f"My prefix is `{prefix} (Comma)`. Get started by typing `{prefix}help`")

    @commands.command(
        brief="Gets the latency of the bot"
    )
    async def ping(self, ctx: commands.Context):
        await ctx.send(f"Pong! ({round(self.bot.latency * 1000)} ms)")
    
    @commands.command(
        name="feedback",
        brief="Send feedback to the bot owner",
        description="Displays a form in which you can provide detailed feedback on what you didn't like, what you think needs improvement, what you liked etc. Any feedback is greatly appreciated!"
    )
    async def feedback(self, ctx: commands.Context):
        # Create and configure the modal
        async def modal_callback(interaction: discord.Interaction):
            em.description = ":heart: Thank you for your feedback!"
            em.color = self.bot.green
            await interaction.response.send_message(embeds=[em])
            log_em = discord.Embed(
                title=f":speaking_head: Feedback From `{interaction.user}`",
                description=f"{modal.children[0].value}",
                color=self.bot.green,
                timestamp=datetime.datetime.now()
            )
            log_em.set_footer(text="Sent by {}".format(ctx.author), icon_url=ctx.author.avatar.url)
            log_channel = self.bot.get_channel(self.bot.log_channels[0])
            await log_channel.send(embeds=[log_em])
        modal = discord.ui.Modal("ProfitGreen Feedback")
        modal.add_item(
            discord.ui.InputText(
                style=discord.InputTextStyle.long,
                label="What feedback do you have?",
                required=True
            )
        )
        modal.callback = modal_callback
        
        # Create the view and add the button which will trigger the modal
        view = discord.ui.View()
        btn = discord.ui.Button(style=discord.ButtonStyle.primary, label="Show Form")
        async def btn_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(modal)
        btn.callback = btn_callback
        view.add_item(btn)

        # Create and send the embed with the view
        em = discord.Embed(description=":mouse_three_button: Click the button below to display the feedback form.", color=discord.Color.blurple())
        await ctx.reply(embeds=[em], view=view)

def setup(bot):
    bot.add_cog(Utils(bot))