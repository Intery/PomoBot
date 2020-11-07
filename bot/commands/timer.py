# import datetime
import discord
from cmdClient import cmd
from cmdClient.checks import in_guild

from Timer import TimerState, NotifyLevel

from utils import timer_utils, interactive, ctx_addons  # noqa

from wards import timer_ready

from presets import get_presets


@cmd("join",
     group="Timer",
     desc="Join a group bound to the current channel.",
     aliases=['sub'])
@in_guild()
@timer_ready()
async def cmd_join(ctx):
    """
    Usage``:
        join
        join <group>
    Description:
        Join a group in the current channel or guild.
        If there are multiple matching groups, or no group is provided,
        will show the group selector.
    Related:
        leave, status, groups, globalgroups
    Examples``:
        join espresso
    """
    # Get the timer they want to join
    globalgroups = ctx.client.config.guilds.get(ctx.guild.id, 'globalgroups')
    timer = await ctx.get_timers_matching(ctx.arg_str, channel_only=(not globalgroups), info=True)

    if timer is None:
        return await ctx.error_reply(
            ("No matching groups in this {}.\n"
             "Use the `groups` command to see the groups in this guild!").format(
                 'guild' if globalgroups else 'channel'
             )
        )

    # Query if the author is already in a group
    current_timer = ctx.client.interface.get_timer_for(ctx.guild.id, ctx.author.id)
    if current_timer is not None:
        if current_timer == timer:
            return await ctx.error_reply("You are already in this group!\n"
                                         "Use `status` to see the current timer status.")

        chan_info = " in {}".format(current_timer.channel.mention) if current_timer.channel != ctx.ch else ""
        result = await ctx.ask("You are already in the group `{}`{}.\nAre you sure you want to switch?".format(
            current_timer.name,
            chan_info
        ))
        if not result:
            return

        await current_timer.subscribed[ctx.author.id].unsub()

    # Subscribe the member
    await ctx.client.interface.sub(ctx, ctx.author, timer)

    # Specify channel info if they are joining from a different channel
    this_channel = (timer.channel == ctx.ch)
    chan_info = " in {}".format(timer.channel.mention) if not this_channel else ""

    # Reply with the join message
    message = "You have joined the group **{}**{}!".format(timer.name, chan_info)
    if ctx.author.bot:
        message += " Good luck, colleague!"
    if timer.state == TimerState.RUNNING:
        message += "\nCurrently on stage **{}** with **{}** remaining. {}".format(
            timer.stages[timer.current_stage].name,
            timer.pretty_remaining(),
            timer.stages[timer.current_stage].message
        )
    elif timer.stages:
        message += "\nGroup timer is set up but not running. Use `start` to start the timer!"
    else:
        message += "\nSet up the timer with `set`!"

    await ctx.reply(message)

    # Poke a welcome message to the timer channel if we are somewhere else
    if not this_channel:
        await timer.channel.send("*{} has joined **{}***. Good luck!".format(
            ctx.author.mention,
            timer.name,
        ))


@cmd("leave",
     group="Timer",
     desc="Leave your current group.",
     aliases=['unsub'])
@in_guild()
@timer_ready()
async def cmd_unsub(ctx):
    """
    Usage``:
        leave
    Description:
        Leave your current group, and unsubscribe from the group timer.
    Related:
        join, status, groups
    """
    timer = ctx.client.interface.get_timer_for(ctx.guild.id, ctx.author.id)
    if timer is None:
        return await ctx.error_reply(
            "You need to join a group before you can leave one!"
        )

    session = await ctx.client.interface.unsub(ctx.guild.id, ctx.author.id)
    clocked = session[-1]

    dur = int(clocked)
    hours = dur // 3600
    minutes = (dur % 3600) // 60
    seconds = dur % 60

    dur_str = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

    await ctx.reply("You have been unsubscribed from **{}**! You were subscribed for **{}**.".format(
        timer.name,
        dur_str
    ))


@cmd("set",
     group="Timer",
     desc="Setup the stages of a group timer.",
     aliases=['setup', 'reset'])
@in_guild()
@timer_ready()
async def cmd_set(ctx):
    """
    Usage``:
        set
        set <setup string>
        set <presetname>
    Description:
        Setup the stages of the timer you are subscribed to.
        When used with no parameters, uses the following default setup string:
        ```
        Study, 25, Good luck!; Break, 5, Have a rest.;
        Study, 25, Good luck!; Break, 5, Have a rest.;
        Study, 25, Good luck!; Long Break, 10, Have a rest.
        ```
        Stages are separated by semicolons,
        and are of the format `stage name, stage duration, stage message`.
        The `stage message` is optional.

        See the `presets` command for more information on using setup presets.
    Related:
        join, start, presets
    """
    # Get the timer we are acting on
    timer = ctx.client.interface.get_timer_for(ctx.guild.id, ctx.author.id)
    if timer is None:
        tchan = ctx.client.interface.channels.get(ctx.ch.id, None)
        if tchan is None or not tchan.timers:
            await ctx.error_reply("There are no timers in this channel!")
        else:
            await ctx.error_reply("Please join a group first!")
        return

    # If the timer is running, prompt for confirmation
    if timer.state == TimerState.RUNNING:
        if ctx.arg_str:
            if not await ctx.ask("The timer is running! Are you sure you want to reset it?"):
                return
        else:
            if not await ctx.ask("The timer is running! Are you sure you want to reset it? "
                                 "This will reset the stage sequence to the default!"):
                return

    if not ctx.arg_str:
        # Use the default setup string
        # TODO: Customise defaults for different timers
        setupstr = (
            "Study, 25, Good luck!; Break, 5, Have a rest.;"
            "Study, 25, Good luck!; Break, 5, Have a rest.;"
            "Study, 25, Good luck!; Long Break, 10, Have a rest."
        )
        stages = ctx.client.interface.parse_setupstr(setupstr)
    else:
        # Parse the provided setup string
        if "," in ctx.arg_str:
            # Parse as a standard setup string
            stages = ctx.client.interface.parse_setupstr(ctx.arg_str)
            if stages is None:
                return await ctx.error_reply("Didn't understand setup string!")
        else:
            # Parse as a preset
            presets = get_presets(ctx)
            if ctx.arg_str in presets:
                stages = ctx.client.interface.parse_setupstr(presets[ctx.arg_str])
            else:
                return await ctx.error_reply(
                    ("Didn't recognise the timer preset `{}`.\n"
                     "Use the `presets` command to view available presets.").format(ctx.arg_str)
                )

    timer.setup(stages)
    await ctx.reply("Timer pattern set up! Start when ready.")


@cmd("start",
     group="Timer",
     desc="Start your timer.",
     aliases=["restart"])
@in_guild()
@timer_ready()
async def cmd_start(ctx):
    """
    Usage``:
        start
        start <setup string>
    Description:
        Start the timer you are subscribed to.
        Can be used with a setup string to set up and start the timer in one go.
    """
    timer = ctx.client.interface.get_timer_for(ctx.guild.id, ctx.author.id)
    if timer is None:
        tchan = ctx.client.interface.channels.get(ctx.ch.id, None)
        if tchan is None or not tchan.timers:
            await ctx.error_reply("There are no timers in this channel!")
        else:
            await ctx.error_reply("Please join a group first!")
        return
    if timer.state == TimerState.RUNNING:
        if await ctx.ask("Are you sure you want to restart your study group timer?"):
            timer.stop()
        else:
            return

    if ctx.arg_str:
        stages = ctx.client.interface.parse_setupstr(ctx.arg_str)

        if stages is None:
            return await ctx.error_reply("Didn't understand setup string!")

        timer.setup(stages)

    if not timer.stages:
        return await ctx.error_reply("Please set up the timer first!")

    await timer.start()

    if timer.channel != ctx.ch:
        await ctx.reply("Timer has been started in {}".format(timer.channel.mention))


@cmd("stop",
     group="Timer",
     desc="Stop your timer.")
@in_guild()
@timer_ready()
async def cmd_stop(ctx):
    """
    Usage``:
        stop
    Description:
        Stop the timer you are subscribed to.
    """
    timer = ctx.client.interface.get_timer_for(ctx.guild.id, ctx.author.id)
    if timer is None:
        tchan = ctx.client.interface.channels.get(ctx.ch.id, None)
        if tchan is None or not tchan.timers:
            await ctx.error_reply("There are no timers in this channel!")
        else:
            await ctx.error_reply("Please join a group first!")
        return
    if timer.state == TimerState.STOPPED:
        return await ctx.error_reply("Can't stop something that's not moving!")

    if len(timer.subscribed) > 1:
        if not await ctx.ask("There are other people in your study group! "
                             "Are you sure you want to stop the study group timer?"):
            return

    timer.stop()
    await ctx.reply("Your timer has been stopped.")


@cmd("groups",
     group="Timer",
     desc="View the guild's groups.",
     aliases=["timers"])
@in_guild()
@timer_ready()
async def cmd_groups(ctx):
    # Handle there being no timers
    if not ctx.client.interface.get_guild_timers(ctx.guild.id):
        return await ctx.error_reply("There are no groups set up in this guild!")

    if "live_grouptokens" not in ctx.client.objects:
        ctx.client.objects["live_grouptokens"] = {}
    ctx.client.objects["live_grouptokens"][ctx.ch.id] = ctx.msg.id

    async def _groups():
        # Check if we have a new token
        if ctx.client.objects["live_grouptokens"].get(ctx.ch.id, 0) != ctx.msg.id:
            return None

        # Build the embed description
        sections = []
        for tchan in ctx.client.interface.guild_channels[ctx.guild.id]:
            sections.append("{}\n\n{}".format(
                tchan.channel.mention,
                "\n\n".join(timer.pretty_summary() for timer in tchan.timers)
            ))

        embed = discord.Embed(
            description="\n\n\n".join(sections),
            colour=discord.Colour(0x9b59b6),
            title="Group timers in this guild"
        )
        return {'embed': embed}

    await ctx.live_reply(_groups)


@cmd("status",
     group="Timer",
     desc="View detailed information about a group.",
     aliases=["group", "timer"])
@in_guild()
@timer_ready()
async def cmd_group(ctx):
    """
    Usage``:
        status [group]
    Description:
        Display detailed information about the current group or the specified group.
    """
    if ctx.arg_str:
        timer = await ctx.get_timers_matching(ctx.arg_str, channel_only=False)
        if timer is None:
            return await ctx.error_reply("No groups matching `{}`!".format(ctx.arg_str))
    else:
        timer = ctx.client.interface.get_timer_for(ctx.guild.id, ctx.author.id)
        if timer is None:
            timer = await ctx.get_timers_matching("", channel_only=False)
            if timer is None:
                return await ctx.error_reply("No groups are set up in this guild.")

    if "live_statustokens" not in ctx.client.objects:
        ctx.client.objects["live_statustokens"] = {}
    ctx.client.objects["live_statustokens"][ctx.ch.id] = ctx.msg.id

    async def _status():
        # Check if we have a new token
        if ctx.client.objects["live_statustokens"].get(ctx.ch.id, 0) != ctx.msg.id:
            return None

        embed = discord.Embed(
            description=timer.pretty_pinstatus(),
            colour=discord.Colour(0x9b59b6)
        )
        return {'embed': embed}

    await ctx.live_reply(_status)


@cmd("notify",
     group="Timer",
     desc="Configure your personal notification level.",
     aliases=["dm"])
async def cmd_notify(ctx):
    """
    Usage``:
        notify
        notify <level>
    Description:
        View or set your notification level.
        The possible levels are described below.
    Notification levels::
        all: Receive all stage changes and status updates via DM.
        warnings: Only receive a DM for inactivity warnings (default).
        kick: Only receive a DM after being kicked for inactivity.
        none: Never get sent any status updates via DM.
    Examples``:
        notify warnings
    """
    if not ctx.arg_str:
        # Read the current level and report
        level = ctx.client.config.users.get(ctx.author.id, "notify_level") or None
        level = NotifyLevel(level) if level is not None else NotifyLevel.WARNING

        if level == NotifyLevel.ALL:
            await ctx.reply("Your notification level is `ALL`.\n"
                            "You will be notified of all group status changes by direct message.")
        elif level == NotifyLevel.WARNING:
            await ctx.reply("Your notification level is `WARNING`.\n"
                            "You will receive a direct message when you are about to be kicked for inactivity.")
        elif level == NotifyLevel.FINAL:
            await ctx.reply("Your notification level is `KICK`.\n"
                            "You will only be messaged when you are kicked for inactivity.")
        elif level == NotifyLevel.NONE:
            await ctx.reply("Your notification level is `NONE`.\n"
                            "You will never be direct messaged about group status updates.")
    else:
        content = ctx.arg_str.lower()

        newlevel = None
        message = None
        if content in ["all", "everything"]:
            newlevel = NotifyLevel.ALL
            message = ("Your notification level has been set to `ALL`\n"
                       "You will be notified of all group status changes by direct message.")
        elif content in ["warnings", "warning"]:
            newlevel = NotifyLevel.WARNING
            message = ("Your notification level has been set to `WARNING`.\n"
                       "You will receive a direct message when you are about to be kicked for inactivity.")
        elif content in ["final", "kick"]:
            newlevel = NotifyLevel.FINAL
            message = ("Your notification level has been set to `KICK`.\n"
                       "You will only be messaged when you are kicked for inactivity.")
        elif content in ["none", "dnd"]:
            newlevel = NotifyLevel.NONE
            message = ("Your notification level has been set to `NONE`.\n"
                       "You will never be direct messaged about group status updates.")
        else:
            await ctx.error_reply(
                "I don't understand notification level `{}`! See `help notify` for valid levels.".format(ctx.arg_str)
            )
        if newlevel is not None:
            # Update the db entry
            ctx.client.config.users.set(ctx.author.id, "notify_level", newlevel.value)

            # Update any existing timers
            for subber in ctx.client.interface.get_subs_for(ctx.author.id):
                subber.notify = NotifyLevel(newlevel)

            # Send the update message
            await ctx.reply(message)


@cmd("rename",
     group="Timer",
     desc="Rename your group.")
@in_guild()
@timer_ready()
async def cmd_rename(ctx):
    """
    Usage``:
        rename <groupname>
    Description:
        Set the name of your current group to `groupname`.
    Arguments::
        groupname: The new name for your group, less than `20` charachters long.
    Related:
        join, status, groups
    """
    timer = ctx.client.interface.get_timer_for(ctx.guild.id, ctx.author.id)
    if timer is None:
        return await ctx.error_reply(
            "You need to join a group first!"
        )
    if not (0 < len(ctx.arg_str) < 20):
        return await ctx.error_reply(
            "Please supply a new group name under `20` characters long!\n"
            "**Usage:** `rename <groupname>`"
        )
    timer.name = ctx.arg_str
    await ctx.embedreply("Your group has been renamed to **{}**.".format(ctx.arg_str))


@cmd("syncwith",
     group="Timer",
     desc="Sync the start of your group timer with another group")
@in_guild()
@timer_ready()
async def cmd_syncwith(ctx):
    """
    Usage``:
        syncwith <group>
    Description:
        Align the start of your group timer with the other group.
        This will possibly change your stage without notification.
    Arguments::
        group: The name of the group to sync with.
    Related:
        join, status, groups, set
    """
    # Check an argumnet was given
    if not ctx.arg_str:
        return await ctx.error_reply("No group name provided!\n**Usage:** `syncwith <group>`.")

    # Check the author is in a group
    current_timer = ctx.client.interface.get_timer_for(ctx.guild.id, ctx.author.id)
    if current_timer is None:
        return await ctx.error_reply("You can only sync a group you are a member of!")

    # Get the target timer to sync with
    sync_timer = await ctx.get_timers_matching(ctx.arg_str, channel_only=False)
    if sync_timer is None:
        return await ctx.error_reply("No groups matching `{}`!".format(ctx.arg_str))

    # Check both timers are set up
    if not sync_timer.stages or not current_timer.stages:
        return await ctx.error_reply("Both the current and target timer must be set up first!")

    # Calculate the total duration from the start of the timer
    target_duration = sum(stage.duration for i, stage in enumerate(sync_timer.stages) if i < sync_timer.current_stage)
    target_duration *= 60
    target_duration += sync_timer.now() - sync_timer.current_stage_start

    # Calculate the target stage in the current timer
    i = -1
    elapsed = 0
    while elapsed < target_duration:
        i = (i + 1) % len(current_timer.stages)
        elapsed += current_timer.stages[i].duration * 60

    # Calculate new stage start
    new_stage_start = sync_timer.now() - (current_timer.stages[i].duration * 60 - (elapsed - target_duration))

    # Change the stage and adjust the time
    await current_timer.change_stage(i, notify=False, inactivity_check=False, report_old=False)
    current_timer.current_stage_start = new_stage_start
    current_timer.remaining = elapsed - target_duration

    # Notify the user
    await ctx.embedreply(current_timer.pretty_pinstatus(), title="Timers synced!")
