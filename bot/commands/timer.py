import datetime
import asyncio

import discord

from meta import client
from data import tables

from Timer import TimerState, Pattern, module

from utils import timer_utils, interactive, ctx_addons  # noqa
from utils.live_messages import live_edit
from utils.timer_utils import is_timer_admin
from wards import has_timers


@module.cmd("join",
            group="Timer Usage",
            short_help="Join a study group.",
            aliases=['sub'])
@has_timers()
async def cmd_join(ctx):
    """
    Usage``:
        {prefix}join
        {prefix}join <group>
    Description:
        Join a study group, and subscribe to the group timer notifications.
        When used with no arguments, displays a selection prompt with the available groups.

        The `group` may be given as a group name or partial name. \
        See `{prefix}groups` for the list of groups in this server.
    Related:
        leave, status, groups, globalgroups
    Examples``:
        {prefix}join {ctx.example_group_name}
    """
    # Get the timer they want to join
    globalgroups = ctx.guild_settings.globalgroups.value
    timer = await ctx.get_timers_matching(ctx.args, channel_only=(not globalgroups), info=True)

    if timer is None:
        if not ctx.timers.get_timers_in(ctx.guild.id):
            await ctx.error_reply(
                "There are no study groups to join!\n"
                "Create a new study group with `{prefix}newgroup <groupname>` "
                "(e.g. `{prefix}newgroup Pomodoro`).".format(prefix=ctx.best_prefix)
            )
        elif not globalgroups and not ctx.timers.get_timers_in(ctx.guild.id, ctx.ch.id):
            await ctx.error_reply(
                "No study groups in this channel!\n"
                "Use `{prefix}groups` to see all server groups.".format(prefix=ctx.best_prefix)
            )
        else:
            await ctx.error_reply(
                ("No matching groups in this {}.\n"
                 "Use `{}groups` to see the server study groups!").format(
                    'server' if globalgroups else 'channel',
                    ctx.best_prefix
                )
            )
        return

    # Query if the author is already in a group
    sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
    if sub is not None:
        if sub.timer == timer:
            return await ctx.error_reply(
                "You are already in this study group!\n"
                "Use `{prefix}status` to see the current timer status.".format(prefix=ctx.best_prefix)
            )
        else:
            result = await ctx.ask(
                "You are already in the group **{}**{}. "
                "Are you sure you want to switch groups?".format(
                    sub.timer.name,
                    " in {}".format(sub.timer.channel.mention) if ctx.ch != sub.timer.channel else ""
                )
            )
            if not result:
                return
            # TODO: Vulnerable to interactive race-states
            await sub.timer.unsubscribe(ctx.author.id)

    # Subscribe the member
    new_sub = await timer.subscribe(ctx.author)
    if sub:
        new_sub.clocked_time = sub.clocked_time

    # Check if member is joining from a different channel
    this_channel = (timer.channel == ctx.ch)

    # Build and send the join message
    message = "You have {} **{}**{}!".format(
        'switched to' if sub is not None else 'joined',
        timer.name,
        " in {}".format(timer.channel.mention) if not this_channel else ""
    )
    if ctx.author.bot:
        message += " Good luck, colleague!"
    if timer.state == TimerState.RUNNING:
        message += " Currently on stage **{}** with **{}** remaining. {}".format(
            timer.current_stage.name,
            timer.pretty_remaining,
            timer.current_stage.message
        )
    else:
        message += (
            "\nTimer is not running! Start it with `{prefix}start` "
            "(or `{prefix}start [pattern]` to use a custom timer pattern)."
        ).format(prefix=ctx.best_prefix)

    await ctx.reply(message, reference=ctx.msg)

    # Poke a welcome message to the timer channel if we are somewhere else
    if not this_channel:
        await timer.channel.send("*{} has joined **{}***. Good luck!".format(
            ctx.author.mention,
            timer.name,
        ))


@module.cmd("leave",
            group="Timer Usage",
            short_help="Leave your current group.",
            aliases=['unsub'])
@has_timers()
async def cmd_unsub(ctx):
    """
    Usage``:
        {prefix}leave
    Description:
        Leave your study group.
    Related:
        join, status, groups
    """
    sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
    if sub is None:
        await ctx.error_reply(
            "You are not in a study group! Join one with `{prefix}join`.".format(prefix=ctx.best_prefix)
        )
    else:
        await sub.timer.unsubscribe(ctx.author.id)
        await ctx.reply(
            "You left **{}**! You were subscribed for **{}**.".format(
                sub.timer.name,
                sub.pretty_clocked
            ),
            reference=ctx.msg
        )


@module.cmd("setup",
            group="Timer Control",
            short_help="Stop and change your group timer pattern.",
            aliases=['set'])
@has_timers()
async def cmd_set(ctx):
    """
    Usage``:
        {prefix}setup <timer pattern>
        {prefix}setup <saved pattern name>
    Description:
        Sets your group timer pattern (i.e. the pattern of work/break periods).

        See `{prefix}help patterns` and the examples below for more information about the pattern format. \
        A saved pattern name (see `{prefix}help presets`) may also be used in place of the associated pattern.

        *If the `admin_locked` timer option is set, this command requires timer admin permissions.*
    Related:
        join, start, reset, savepattern
    Examples:
        `{prefix}setup 50/10`  (`50` minutes work followed by `10` minutes break.)
        `{prefix}setup 25/5/25/5/25/10`  (A standard Pomodoro pattern of work and breaks.)
        `{prefix}setup Study, 50; Rest, 10`  (Another `50/10` pattern, now with custom stage names.)
    """
    sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
    if sub is None:
        return await ctx.error_reply(
            "You are not in a study group! Join one with `{prefix}join`.".format(prefix=ctx.best_prefix)
        )

    if sub.timer.settings.admin_locked.value and not await is_timer_admin(ctx.author):
        return await ctx.error_reply("This timer may only be setup by timer admins.")

    if not ctx.args:
        return await ctx.error_reply(
            "Please provide a timer pattern! See `{}help setup` for usage".format(ctx.best_prefix)
        )

    if sub.timer.state == TimerState.RUNNING:
        if not await ctx.ask("Are you sure you want to **stop and reset** your study group timer?"):
            return

    pattern = Pattern.from_userstr(ctx.args, timerid=sub.timer.roleid, userid=ctx.author.id, guildid=ctx.guild.id)
    await sub.timer.setup(pattern, ctx.author.id)

    content = "**{}** set up! Use `{}start` to start when ready.".format(sub.timer.name, ctx.best_prefix)
    asyncio.create_task(
        live_edit(
            None,
            _status_msg,
            'status',
            timer=sub.timer,
            ctx=ctx,
            content=content,
            reference=ctx.msg
        )
    )


@module.cmd("reset",
            group="Timer Control",
            short_help="Reset the timer pattern to the default.")
@has_timers()
async def cmd_reset(ctx):
    """
    Usage``:
        {prefix}reset
    Description:
        Stop your group timer, and reset the timer pattern to the timer default.
        (To change the default pattern, see `{prefix}tconfig default_pattern`.)

        *If the `admin_locked` timer option is set, this command requires timer admin permissions.*
    Related:
        tconfig, setup, stop
    """
    sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
    if sub is None:
        return await ctx.error_reply(
            "You are not in a study group! Join one with `{prefix}join`.".format(prefix=ctx.best_prefix)
        )

    if sub.timer.settings.admin_locked.value and not await is_timer_admin(ctx.author):
        return await ctx.error_reply("This timer may only be reset by timer admins.")

    if sub.timer.state == TimerState.RUNNING:
        if not await ctx.ask("Are you sure you want to **stop and reset** your study group timer?"):
            return

    await sub.timer.setup(sub.timer.default_pattern, ctx.author.id)

    content = "**{}** has been reset! Use `{}start` to start when ready.".format(sub.timer.name, ctx.best_prefix)
    asyncio.create_task(
        live_edit(
            None,
            _status_msg,
            'status',
            timer=sub.timer,
            ctx=ctx,
            content=content,
            reference=ctx.msg
        )
    )


@module.cmd("start",
            group="Timer Control",
            short_help="Start your group timer (and optionally change the pattern).",
            aliases=["restart"])
@has_timers()
async def cmd_start(ctx):
    """
    Usage``:
        {prefix}start
        {prefix}start <timer pattern>
        {prefix}start <saved pattern name>
        {prefix}restart
    Description:
        Start or restart your group timer.

        To modify the timer pattern (i.e. the pattern of work/break stages), \
        provide a timer pattern or a saved pattern name. \
        See `{prefix}help patterns` and the examples below for more information about the pattern format.

        *If the `admin_locked` timer option is set, this command requires timer admin permissions, unless\
        the timer is already stopped.*
    Related:
        stop, setup, tconfig, savepattern
    Examples:
        `{prefix}start` (Start/restart the timer with the current pattern.)
        `{prefix}start 50/10`  (`50` minutes work followed by `10` minutes break.)
        `{prefix}start 25/5/25/5/25/10`  (A standard Pomodoro pattern of work and breaks.)
        `{prefix}start Study, 50; Rest, 10`  (Another `50/10` pattern, now with custom stage names.)
    """
    sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
    if sub is None:
        return await ctx.error_reply(
            "You are not in a study group! Join one with `{prefix}join`.".format(prefix=ctx.best_prefix)
        )
    if sub.timer.state == TimerState.RUNNING:
        if sub.timer.settings.admin_locked.value and not await is_timer_admin(ctx.author):
            return await ctx.error_reply("This timer may only be restarted by timer admins.")

        if await ctx.ask("Are you sure you want to **restart** your study group timer?"):
            sub.timer.stop()
        else:
            return

    timer = sub.timer

    if ctx.args:
        pattern = Pattern.from_userstr(ctx.args, timerid=sub.timer.roleid, userid=ctx.author.id, guildid=ctx.guild.id)
        await timer.setup(pattern, ctx.author.id)

    this_channel = (ctx.ch == timer.channel)
    content = "Started **{}** in {}!".format(
        timer.name,
        timer.channel.mention
    ) if not this_channel else ''

    await timer.start()
    if ctx.args:
        asyncio.create_task(
            live_edit(
                None,
                _status_msg,
                'status',
                timer=timer,
                ctx=ctx,
                content=content,
                reference=ctx.msg
            )
        )
    elif not this_channel:
        await ctx.reply(content, reference=ctx.msg)


@module.cmd("stop",
            group="Timer Control",
            short_help="Stop your group timer.")
@has_timers()
async def cmd_stop(ctx):
    """
    Usage``:
        {prefix}stop
    Description:
        Stop your study group timer.

        *If the `admin_locked` timer option is set, this command requires timer admin permissions.*
    Related:
        start, reset, tconfig
    """
    sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
    if sub is None:
        return await ctx.error_reply(
            "You are not in a study group! Join one with `{prefix}join`.".format(prefix=ctx.best_prefix)
        )

    if sub.timer.settings.admin_locked.value and not await is_timer_admin(ctx.author):
        return await ctx.error_reply("This timer may only be stopped by timer admins.")

    if sub.timer.state != TimerState.RUNNING:
        # TODO: Might want an extra clause when we have Pause states
        return await ctx.error_reply(
            "Can't stop something that's not moving! (Your group timer is already stopped.)"
        )

    if len(sub.timer.subscribers) > 1:
        if not await ctx.ask("There are other people in your study group! "
                             "Are you sure you want to stop the study group timer?"):
            return

    sub.timer.stop()
    await ctx.reply("Your group timer has been stopped.")


async def _group_msg(msg, ctx=None):
    """
    Group message live-editor.
    """
    sections = []
    for tchan in client.interface.guild_channels.get(ctx.guild.id, {}).values():
        if len(tchan.timers) > 0:
            sections.append("{}\n\n{}".format(
                tchan.channel.mention,
                "\n\n".join(timer.pretty_summary for timer in tchan.timers)
            ))

    embed = discord.Embed(
        description="\n\n\n".join(sections) or "No timers in this guild!",
        colour=discord.Colour(0x9b59b6),
        title="Study groups",
        timestamp=datetime.datetime.utcnow()
    ).set_footer(text="Last Updated")

    if msg:
        try:
            await msg.edit(embed=embed)
            return msg
        except discord.HTTPException:
            pass
    else:
        return await ctx.reply(embed=embed)


@module.cmd("groups",
            group="Timer Usage",
            short_help="List the server study groups.",
            aliases=["timers"])
@has_timers()
async def cmd_groups(ctx):
    """
    Usage``:
        {prefix}groups
    Description:
        List all the study groups in this server.
    Related:
        join, newgroup, delgroup
    """
    # Handle there being no timers
    timers = ctx.timers.get_timers_in(ctx.guild.id)
    if not timers:
        return await ctx.error_reply(
            "This server doesn't have any study groups yet!\n"
            "Create one with `{prefix}newgroup <groupname>` "
            "(e.g. `{prefix}newgroup Pomodoro`).".format(prefix=ctx.best_prefix)
        )

    asyncio.create_task(live_edit(
        None,
        _group_msg,
        'groups',
        ctx=ctx
    ))


async def _status_msg(msg, timer, ctx, content='', reference=None):
    embed = discord.Embed(
        description=timer.status_string(show_seconds=True),
        colour=discord.Colour(0x9b59b6),
        timestamp=datetime.datetime.utcnow()
    ).set_footer(text="Last Updated")

    if msg:
        try:
            await msg.edit(content=content, embed=embed)
            return msg
        except discord.HTTPException:
            pass
    else:
        return await ctx.reply(content=content, embed=embed, reference=reference)


@module.cmd("status",
            group="Timer Usage",
            short_help="Show the status of a group.")
@has_timers()
async def cmd_status(ctx):
    """
    Usage``:
        {prefix}status
        {prefix}status <group>
    Description:
        Display the status of the provided group (or your current/selected group if none was given).

        The `group` may be given as a group name or partial name. \
        See `{prefix}groups` for the list of groups in this server.
    Related:
        groups, start, stop, setup
    """
    # Get target group
    if ctx.args:
        timer = await ctx.get_timers_matching(ctx.args, channel_only=False)
        if timer is None:
            return await ctx.error_reply("No groups found matching `{}`!".format(ctx.args))
    else:
        sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
        if sub:
            timer = sub.timer
        else:
            timer = await ctx.get_timers_matching('', channel_only=False)
            if timer is None:
                return await ctx.error_reply(
                    "This server doesn't have any study groups yet!\n"
                    "Create one with `{prefix}newgroup <groupname>` "
                    "(e.g. `{prefix}newgroup Pomodoro`).".format(prefix=ctx.best_prefix)
                )

    asyncio.create_task(
        live_edit(
            None,
            _status_msg,
            'status',
            ctx=ctx,
            timer=timer
        )
    )


@module.cmd("shift",
            group="Timer Control",
            short_help="Add or remove time from the current stage.")
@has_timers()
async def cmd_shift(ctx):
    """
    Usage``:
        {prefix}shift
        {prefix}shift <amount>
    Description:
        Adds or removes time from the current stage.
        When `amount` is *positive*, adds time to the stage, and removes time when `amount` is *negative*.
        `amount` must be given in minutes, with no units (see examples below).
        If `amount` is not given, instead aligns the start of the stage to the nearest hour.

        *If the `admin_locked` timer option is set, this command requires timer admin permissions.*
    Examples``:
        {prefix}shift +10
        {prefix}shift -10
    """
    sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
    if sub is None:
        return await ctx.error_reply(
            "You are not in a study group!"
        )

    if sub.timer.settings.admin_locked.value and not await is_timer_admin(ctx.author):
        return await ctx.error_reply("This timer may only be shifted by timer admins.")

    if sub.timer.state != TimerState.RUNNING:
        return await ctx.error_reply(
            "You can only shift a group timer while it is running!"
        )

    if len(sub.timer.subscribers) > 1:
        if not await ctx.ask("There are other people in your study group! "
                             "Are you sure you want to shift the study group timer?"):
            return

    if not ctx.args:
        quantity = None
    elif ctx.args.strip('+-').isdigit():
        quantity = (-1 if ctx.args.startswith('-') else 1) * int(ctx.args.strip('+-'))
    else:
        return await ctx.error_reply(
            "Could not parse `{}` as a shift amount!".format(ctx.args)
        )

    sub.timer.shift(quantity * 60 if quantity is not None else None)
    asyncio.create_task(
        live_edit(
            None,
            _status_msg,
            'status',
            timer=sub.timer,
            ctx=ctx,
            content="Timer shifted!",
            reference=ctx.msg
        )
    )


@module.cmd("skip",
            group="Timer Control",
            short_help="Skip the current stage.")
@has_timers()
async def cmd_skip(ctx):
    """
    Usage``:
        {prefix}skip
        {prefix}skip <number>
    Description:
        Skip the current timer stage, or the number of stages given.
    Examples``:
        {prefix}skip 1
    """
    sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
    if sub is None:
        return await ctx.error_reply(
            "You are not in a study group!"
        )
    timer = sub.timer

    if timer.settings.admin_locked.value and not await is_timer_admin(ctx.author):
        return await ctx.error_reply("This timer may only be skipped by timer admins.")

    if timer.state != TimerState.RUNNING:
        return await ctx.error_reply(
            "You can only skip stages of a group timer while it is running!"
        )

    if len(timer.subscribers) > 1:
        if not await ctx.ask("There are other people in your study group! "
                             "Are you sure you want to skip forwards?"):
            return

    # Collect the number of stages to skip
    count = 1
    pattern_len = len(timer.current_pattern.stages)
    if ctx.args:
        if not ctx.args.isdigit():
            return await ctx.error_reply(
                "**Usage:** `{prefix}skip [number].\n"
                "Couldn't parse the number of stages to skip.".format(prefix=ctx.best_prefix)
            )
        if len(ctx.args) > 10 or int(ctx.args) > pattern_len:
            return await ctx.error_reply(
                "Maximum number of skippable stages is `{}`.".format(pattern_len)
            )
        count = int(ctx.args)
        if count == 0:
            return await ctx.error_reply(
                "Skipping no stages.. done?"
            )

    # Calculate the shift time
    shift_by = timer.remaining + sum(
        timer.current_pattern.stages[(timer.stage_index + i + 1) % pattern_len].duration * 60
        for i in range(count - 1)
    ) - 1

    timer.shift(-1 * shift_by)
    content = "**{}** stages skipped!".format(count) if count > 1 else "Stage skipped!"
    await asyncio.sleep(1)
    asyncio.create_task(
        live_edit(
            None,
            _status_msg,
            'status',
            timer=sub.timer,
            ctx=ctx,
            content=content,
            reference=ctx.msg
        )
    )


@module.cmd("syncwith",
            group="Timer Control",
            short_help="Sync the timer with another group.",
            flags=('end',))
@has_timers()
async def cmd_syncwith(ctx, flags):
    """
    Usage``:
        {prefix}syncwith <group> [--end]
    Description:
        Synchronise your current timer with the timer of the provided group.
        This is usually done by *moving* the start of your current stage to the start of the target group's stage.
        If the `-end` flag is added, instead moves the *end* of your current stage to match the end of the target stage.

        *If the `admin_locked` timer option is set, this command requires timer admin permissions.*
    Examples``:
        {prefix}syncwith {ctx.example_group_name}
        {prefix}syncwith {ctx.example_group_name} --end
    """
    sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
    if sub is None:
        return await ctx.error_reply(
            "You are not in a study group!"
        )
    timer = sub.timer

    if timer.settings.admin_locked.value and not await is_timer_admin(ctx.author):
        return await ctx.error_reply("This timer may only be synced by a timer admin.")

    if timer.state != TimerState.RUNNING:
        return await ctx.error_reply(
            "Timers may only be synced while they are running!"
        )

    if ctx.args:
        target = await ctx.get_timers_matching(ctx.args, channel_only=False)
        if target is None and ctx.args.isdigit():
            # Last-ditch check, accept roleids from foreign guilds
            roleid = int(ctx.args)
            timer_row = tables.timers.fetch(roleid)
            if timer_row is not None and timer_row.guildid in ctx.timers.guild_channels:
                target = next(
                    (t for t in ctx.timers.guild_channels[timer_row.guildid][timer_row.channelid].timers
                     if t.roleid == roleid),
                    None
                )

        if target is None:
            return await ctx.error_reply("No target groups found matching `{}`!".format(ctx.args))
    else:
        return await ctx.error_reply(
            "**Usage:** `{}syncwith <group> [--end]`\n"
            "No target group provided!".format(ctx.best_prefix)
        )

    if len(timer.subscribers) > 1:
        if not await ctx.ask("There are other people in your study group! "
                             "Are you sure you want to sync it with **{}**?".format(target.name)):
            return

    if target.state != TimerState.RUNNING:
        return await ctx.error_reply(
            "Target timer isn't running! Use `{}restart` if you want to restart your timer.".format(ctx.best_prefix)
        )

    # Perform the actual sync
    diff = target.stage_start - timer.stage_start
    if flags['end']:
        diff += (target.current_stage.duration - timer.current_stage.duration) * 60

    timer.shift(diff)

    content = "Timer synced with **{}**!".format(target.name)
    asyncio.create_task(
        live_edit(
            None,
            _status_msg,
            'status',
            timer=sub.timer,
            ctx=ctx,
            content=content,
            reference=ctx.msg
        )
    )
