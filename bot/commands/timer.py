# import datetime
# import discord

from Timer import TimerStage
from cmdClient import cmd


@cmd("sub")
async def cmd_sub(ctx):
    timer = ctx.client.interface.get_timer_for(ctx.author.id)
    if timer is not None:
        return await ctx.error_reply(
            "You are already in the group `{}` in {}!".format(timer.name, timer.channel.mention)
        )

    tchan = ctx.client.interface.channels.get(ctx.ch.id, None)
    if tchan is None or not tchan.timers:
        return await ctx.error_reply("There are no timers in this channel!")
    elif len(tchan.timers) == 1:
        sub_to = tchan.timers[0]
    else:
        names = [timer.name for timer in tchan.timers]
        sub_to = tchan.timers[await ctx.selector("Please select a group to join.", names)]

    await ctx.client.interface.sub(ctx, ctx.author, sub_to)

    await ctx.reply("You have joined **{}**!".format(sub_to.name))
    # TODO: Summary of current status.


@cmd("unsub")
async def cmd_unsub(ctx):
    timer = ctx.client.interface.get_timer_for(ctx.author.id)
    if timer is None:
        return await ctx.error_reply(
            "You need to join a group before you can leave one!"
        )

    session = ctx.client.interface.unsub(ctx.author.id)
    clocked = session[-1]

    await ctx.reply("You have been unsubscribed from **{}**! You were subscribed for **{}** seconds.".format(
        timer.name,
        clocked
    ))


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

    # Temporary
    stages = [TimerStage("Work", 50), TimerStage("Break", 10)]
    timer.setup(stages)
    await timer.start()
