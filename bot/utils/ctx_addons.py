import discord
from cmdClient import Context

from data import tables

from settings import GuildSettings, UserSettings


@Context.util
async def embed_reply(ctx, desc, colour=discord.Colour(0x9b59b6), **kwargs):
    """
    Simple helper to embed replies.
    All arguments are passed to the embed constructor.
    `desc` is passed as the `description` kwarg.
    """
    embed = discord.Embed(description=desc, colour=colour, **kwargs)
    return await ctx.reply(embed=embed)


@Context.util
async def error_reply(ctx, error_str, **kwargs):
    """
    Notify the user of a user level error.
    Typically, this will occur in a red embed, posted in the command channel.
    """
    embed = discord.Embed(
        colour=discord.Colour.red(),
        description=error_str
    )
    try:
        message = await ctx.ch.send(embed=embed, reference=ctx.msg, **kwargs)
        ctx.sent_messages.append(message)
        return message
    except discord.Forbidden:
        message = await ctx.reply(error_str)
        ctx.sent_messages.append(message)
        return message


def context_property(func):
    setattr(Context, func.__name__, property(func))
    return func


@context_property
def best_prefix(ctx):
    guild_prefix = tables.guilds.fetch_or_create(ctx.guild.id).prefix if ctx.guild else ''
    return guild_prefix or ctx.client.prefix


@context_property
def example_group_name(ctx):
    name = "AwesomeStudyGroup"
    if ctx.guild:
        groups = ctx.timers.get_timers_in(ctx.guild.id)
        if groups:
            name = groups[0].name
    return name


@context_property
def guild_settings(ctx):
    return GuildSettings(ctx.guild.id if ctx.guild else 0)


@context_property
def author_settings(ctx):
    return UserSettings(ctx.author.id)
