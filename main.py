# Imports
import discord
from discord.ext import commands

import os

from config import Config
from extras import *
from server import run_server_thread


# Set the intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Choose API V9 in order to bypass message content intent requirement
#discord.http.API_VERSION = 9

# Set the debug_guilds
if Config.PRODUCTION:
    debug_guilds = None
else:
    debug_guilds=[
        818859166772363314 # bot test server
    ]

# Create the bot
bot = ProfitGreenBot (
                command_prefix=commands.when_mentioned_or(Config.PREFIX),
                case_insensitive=True,
                strip_after_prefix=True,
                intents=intents,
                debug_guilds=debug_guilds
                )

# Set the developer's id
bot.owner_id = 416730155332009984
# Set the test server id
bot.test_server_id = 818859166772363314
# Set the Top.gg token
bot.topgg_token = Config.TOPGG_TOKEN
# Set the log channel(s)
bot.log_channels = [941105200586952735, # #logging
                    896527153422794792  # #bubble-announcements
]


# When the bot is online
@bot.event
async def on_ready():
    print("Logged in as {}.".format(bot.user))
    
    # Display the server count
    print()
    print(f"Server Data ({len(bot.guilds)}):")
    for guild in bot.guilds:
        mem_ct = 0
        for m in guild.members:
            if m.bot == True:
                continue
            else:
                mem_ct += 1
        print(f"Guild Name: {guild}, Member Count: {guild.member_count}, Human Count: {mem_ct}, Bot Count: {guild.member_count - mem_ct}")
    print()

    # Update the bot's status
    activity = discord.Activity(name=",help | The Stock Market", type=discord.ActivityType.watching)
    await bot.change_presence(status=discord.Status.online, activity=activity)


# Load all cogs on bot startup
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'cogs.{filename[:-3]}')


# Load cogs manually
@bot.command(
    hidden=True
)
async def load(ctx, extension):
    if ctx.author.id != bot.owner_id:
        return
    try:
        bot.load_extension(f'cogs.{extension}')
    except:
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                if filename[:-3] == extension:
                    bot.load_extension(f'cogs.{filename[:-3]}')
    await ctx.send(f"Loaded **{extension}**")


# Unload cogs manually
@bot.command(
    hidden=True
)
async def unload(ctx, extension):
    if ctx.author.id != bot.owner_id:
        return
    bot.unload_extension(f'cogs.{extension}')
    await ctx.send(f"Unloaded **{extension}**")


# Reload cogs manually
@bot.command(
    hidden=True
)
async def reload(ctx, extension):
    if ctx.author.id != bot.owner_id:
        return
    bot.reload_extension(f'cogs.{extension}')
    await ctx.send(f"Reloaded **{extension}**")


# Run the server
run_server_thread()


# Run the bot
try:
    bot.run(Config.TOKEN)
except:
    os.system("kill 1") # Switch to a different container to prevent ratelimits
    bot.run(Config.TOKEN)