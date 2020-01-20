import datetime
import discord

from Timer import get_timer_for, get_tchan, TimerStage
from cmdClient import cmd


@cmd("timertest")
async def cmd_timertest(ctx):
    stages = [TimerStage("Work", 2), TimerStage("Break", 1)]
    pass


@cmd("sub")
async def cmd_sub(ctx):
    timer = get_timer_for(ctx, ctx.author)
    if timer is not None:
        return await ctx.error_reply(
            "You are already in the group `{}` in {}!".format(timer.name, timer.channel.mention)
        )

    tchan = get_tchan(ctx)
    if tchan is None or not tchan.timers:
        return await ctx.error_reply("There are no timers in this channel!")
    elif len(tchan.timers) == 1:
        sub_to = tchan.timers[0]
    else:
        names = [timer.name for timer in tchan.timers]
        sub_to = tchan.timers[await ctx.selector("Please select a group to join.", names)]

    await sub_to.sub(ctx, ctx.author)

    await ctx.reply("You have joined **{}**!".format(sub_to.name))
    # TODO: Summary of current status.


@cmd("start")
async def cmd_start(ctx):
    timer = get_timer_for(ctx, ctx.author)
    if timer is None:
        tchan = get_tchan(ctx)
        if tchan is None or not tchan.timers:
            await ctx.error_reply("There are no timers in this channel!")
        else:
            await ctx.error_reply("Please join a group first!")
        return

    # Temporary
    stages = [TimerStage("Work", 50), TimerStage("Break", 10)]
    timer.setup(stages)
    await timer.start()


@cmd("stop")
async def cmd_start(ctx):
    timer = get_timer_for(ctx, ctx.author)
    if timer is None:
        tchan = get_tchan(ctx)
        if tchan is None or not tchan.timers:
            await ctx.error_reply("There are no timers in this channel!")
        else:
            await ctx.error_reply("Please join a group first!")
        return

    await timer.start()


