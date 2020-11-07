from cmdClient import Context

from logger import log

from .Timer import TimerState


async def sub_on_vcjoin(client, member, before, after):
    """
    When a member joins a study group voice channel, automatically subscribe them to the study group.
    """
    if before.channel is None and after.channel is not None:
        # Join voice channel event

        # Quit if the member is a bot
        if member.bot:
            return

        # Quit if the member is already subscribed
        if (member.guild.id, member.id) in client.interface.subscribers:
            return

        guild_timers = client.interface.get_guild_timers(member.guild.id)

        # Quit if there are no groups in this guild
        if not guild_timers:
            return

        # Get the collection of clocks in the guild
        guild_clocks = {timer.clock_channel.id: timer for timer in guild_timers if timer.clock_channel is not None}

        # Quit if the voice channel is not a clock channel, otherwise get the related timer
        timer = guild_clocks.get(after.channel.id, None)
        if timer is None:
            return

        # Finally, subscribe the member to the timer
        ctx = Context(client, channel=timer.channel, guild=timer.channel.guild, author=member)
        log("Reaction-subscribing user {} (uid: {}) to timer {} (rid: {})".format(member.name,
                                                                                  member.id,
                                                                                  timer.name,
                                                                                  timer.role.id),
            context="CLOCK_AUTOSUB")
        await client.interface.sub(ctx, member, timer)

        # Send a welcome message
        welcome = "Welcome to **{}**, {}!\n".format(timer.name, member.mention)
        if timer.stages and timer.state == TimerState.RUNNING:
            welcome += "Currently on stage **{}** with **{}** remaining. {}".format(
                timer.stages[timer.current_stage].name,
                timer.pretty_remaining(),
                timer.stages[timer.current_stage].message
            )
        elif timer.stages:
            welcome += "Group timer is set up but not running."

        await ctx.ch.send(welcome)
