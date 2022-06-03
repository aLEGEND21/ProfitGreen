# cogs/errors.py - An error handler for ProfitGreen
import discord
from discord.ext import commands

import traceback
import sys

from extras import *


class ErrorHandler(commands.Cog):
    
    def __init__(self, bot):
        self.bot: ProfitGreenBot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("cogs.errors is online")

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error):
        """The event triggered when an error is raised while invoking an application command.
        Parameters
        ------------
        ctx: discord.ApplicationContext
            The context used for command invocation.
        error: commands.CommandError
            The Exception raised.
        """
        await self.handle_error(ctx, error, "application")
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        """The event triggered when an error is raised while invoking a command.
        Parameters
        ------------
        ctx: commands.Context
            The context used for command invocation.
        error: commands.CommandError
            The Exception raised.
        """
        await self.handle_error(ctx, error, "prefixed")
        
    async def handle_error(self, ctx, error, command_type):
        # Change the response type if it is an application command
        if command_type == "application":
            ctx.prefix = ""
            ctx.reply = ctx.respond

        # This prevents any commands with local handlers being handled here in on_command_error.
        if hasattr(ctx.command, 'on_error'):
            return

        # This prevents any cogs with an overwritten cog_command_error being handled here.
        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return

        ignored = (commands.CommandNotFound, commands.NotOwner, )

        # Allows us to check for original exceptions raised and sent to CommandInvokeError.
        # If nothing is found. We keep the exception passed to on_command_error.
        error = getattr(error, 'original', error)

        # Anything in ignored will return and prevent anything happening.
        if isinstance(error, ignored):
            return

        # Handle all the errors caused by prefixed commands
        elif isinstance(error, commands.MissingRequiredArgument):
            # Show a detailed error message if the command has a usage_examples attribute
            if getattr(ctx.command, "usage_examples", None) is not None:
                em = discord.Embed(
                    title=f":package: Missing Required Argument: `{error.param.name}`",
                    description=f":notepad_spiral: __**Command Description:**__\n{ctx.command.description}\n\n:microphone2: __**Example Usage:**__\n",
                    color=discord.Color.red(),
                )
                for ex in ctx.command.usage_examples:
                    em.description += f"`{ctx.prefix}{ctx.command.name} {ex}`\n"
                await ctx.reply(embeds=[em])
            else:
                await ctx.reply(f'You must provide the `{error.param.name}` argument.')
        elif isinstance(error, commands.DisabledCommand):
            await ctx.reply(f'Command `{ctx.command.name}` is currently disabled.')
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f'You have to wait `{round(error.retry_after)}` seconds before you can run `{ctx.command.name}` again.')
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply(f'I couldn\'t find any member named `{error.argument}`.')
        elif isinstance(error, commands.RoleNotFound):
            await ctx.reply(f'I couldn\'t find any role named `{error.argument}`.')
        elif isinstance(error, commands.MissingPermissions):
            # Convert the list of missing perms into a str
            missing_perms = ""
            for perm in error.missing_permissions:
                missing_perms = f'{missing_perms}{perm}, '
            missing_perms = missing_perms[:-2]
            await ctx.reply(f'You are missing the required permissions to run `{ctx.command.name}`: `{missing_perms}`.')
        elif isinstance(error, commands.BotMissingPermissions):
            # Convert the list of missing perms into a str
            missing_perms = ""
            for perm in error.missing_permissions:
                missing_perms = f'{missing_perms}{perm}, '
            missing_perms = missing_perms[:-2]
            await ctx.reply(f'I need the following permissions to run `{ctx.command.name}`: `{missing_perms}`.')

        # Handle any other possible error here
        else:
            # All other Errors not returned come here. And we can just print the default TraceBack.
            print('Ignoring exception in command {}:'.format(ctx.command.name), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            # Notify the user an error occured
            await ctx.reply(f"An unexpected error occured in command `{ctx.command.name}`.")

def setup(bot):
    bot.add_cog(ErrorHandler(bot))