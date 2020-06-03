import asyncio
import discord
from cmdClient import Context


@Context.util
async def embedreply(ctx, desc, colour=discord.Colour(0x9b59b6), **kwargs):
    """
    Simple helper to embed replies.
    All arguments are passed to the embed constructor.
    `desc` is passed as the `description` kwarg.
    """
    embed = discord.Embed(description=desc, colour=colour, **kwargs)
    return await ctx.reply(embed=embed)


@Context.util
async def live_reply(ctx, reply_func, update_interval=5, max_messages=20):
    """
    Acts as `ctx.reply`, but asynchronously updates the reply every `update_interval` seconds
    with the value of `reply_func`, until the value is `None`.

    Parameters
    ----------
    reply_func: coroutine
        An async coroutine with no arguments.
        Expected to return a dictionary of arguments suitable for `ctx.reply()` and `Message.edit()`.
    update_interval: int
        An integer number of seconds.
    max_messages: int
        Maximum number of messages in channel to keep the reply live for.

    Returns
    -------
    The output message after the first reply.
    """
    # Send the initial message
    message = await ctx.reply(**(await reply_func()))

    # Start the counter
    future = asyncio.ensure_future(_message_counter(ctx.client, ctx.ch, max_messages))

    # Build the loop function
    async def _reply_loop():
        while not future.done():
            await asyncio.sleep(update_interval)
            args = await reply_func()
            if args is not None:
                await message.edit(**args)
            else:
                break

    # Start the loop
    asyncio.ensure_future(_reply_loop())

    # Return the original message
    return message


async def _message_counter(client, channel, max_count):
    """
    Helper for live_reply
    """
    # Build check function
    def _check(message):
        return message.channel == channel

    # Loop until the message counter reaches maximum
    count = 0
    while count < max_count:
        await client.wait_for('message', check=_check)
        count += 1
    return
