import discord
from Context import Context


@Context.util
async def embedreply(ctx, desc, colour=discord.Colour.red(), **kwargs):
    """
    Simple helper to embed replies.
    All arguments are passed to the embed constructor.
    `desc` is passed as the `description` kwarg.
    """
    embed = discord.embed(description=desc, colour=colour, **kwargs)
    return await ctx.reply(embed=embed)
