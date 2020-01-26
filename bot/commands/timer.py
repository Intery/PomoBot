# import datetime
# import discord
from cmdClient import cmd

from Timer import TimerState

from utils import timer


@cmd("join",
     group="Timer",
     desc="Join a group bound to the current channel.",
     aliases=['sub'])
async def cmd_join(ctx):
    """
    Usage``:
        join
        join <group>
    Description:
        Join a group in the current channel.
        If there are multiple matching groups, or no group is provided,
        will show the group selector.
    Examples``:
        join espresso
    """
    # Quit if the author is already in a timer
    timer = ctx.client.interface.get_timer_for(ctx.author.id)
    if timer is not None:
        return await ctx.error_reply(
            "You are already in the group `{}` in {}!".format(timer.name, timer.channel.mention)
        )

    # Get the timer they want to join
    timer = await ctx.get_timers_matching(ctx.arg_str)

    if timer is None:
        return await ctx.error_reply(
            ("No matching groups in this channel.\n"
             "Use the `groups` command to see the groups in this guild!")
        )

    await ctx.client.interface.sub(ctx, ctx.author, timer)

    message = "You have joined the group **{}**!".format(timer.name)
    if timer.state == TimerState.RUNNING:
        message += "\nCurrently on stage **{}** with **{}** remaining.".format(
            timer.stages[timer.current_stage].name,
            timer.pretty_remaining()
        )
    elif timer.stages:
        message += "\nGroup timer is set up but not running. Use `start` to start the timer!"
    else:
        message += "\nSet up the timer with `set`!"

    await ctx.reply(message)


@cmd("leave",
     group="Timer",
     desc="Leave your current group.",
     aliases=['unsub'])
async def cmd_unsub(ctx):
    timer = ctx.client.interface.get_timer_for(ctx.author.id)
    if timer is None:
        return await ctx.error_reply(
            "You need to join a group before you can leave one!"
        )

    session = await ctx.client.interface.unsub(ctx.author.id)
    clocked = session[-1]

    await ctx.reply("You have been unsubscribed from **{}**! You were subscribed for **{}** seconds.".format(
        timer.name,
        clocked
    ))


@cmd("set")
async def cmd_set(ctx):
    timer = ctx.client.interface.get_timer_for(ctx.author.id)
    if timer is None:
        tchan = ctx.client.interface.channels.get(ctx.ch.id, None)
        if tchan is None or not tchan.timers:
            await ctx.error_reply("There are no timers in this channel!")
        else:
            await ctx.error_reply("Please join a group first!")
        return

    setupstr = ctx.arg_str or "Study, 25; Break, 5; Study, 25; Break, 5; Study, 25; Break, 10"
    stages = ctx.client.interface.parse_setupstr(setupstr)

    if stages is None:
        return await ctx.error_reply("Didn't understand setup string!")

    timer.setup(stages)
    await ctx.reply("Timer pattern set up! Start when ready.")


@cmd("start")
async def cmd_start(ctx):
    timer = ctx.client.interface.get_timer_for(ctx.author.id)
    if timer is None:
        tchan = ctx.client.interface.channels.get(ctx.ch.id, None)
        if tchan is None or not tchan.timers:
            await ctx.error_reply("There are no timers in this channel!")
        else:
            await ctx.error_reply("Please join a group first!")
        return

    if not timer.stages:
        return await ctx.error_reply("Please set up the timer first!")

    await timer.start()


@cmd("groups",
     group="Timer",
     desc="View or manage the guild's groups.")
async def cmd_groups(ctx):
    pass


@cmd("group",
     group="Timer",
     desc="View detailed information about a group.")
async def cmd_group(ctx):
    pass
