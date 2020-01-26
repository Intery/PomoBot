import discord

from cmdClient import cmd
from cmdClient.lib import ResponseTimedOut, UserCancelled

# from Timer import create_timer


@cmd("newgroup",
     group="Timer Config",
     desc="Create a new timer group.")
async def cmd_addgrp(ctx):
    """
    Usage``:
        newgroup
        newgroup <name>
        newgroup <name>, <role>, <channel>, <clock channel>
    Description:
        Creates a new group with the specified properties.
        With no arguments or just `name` given, prompts for the remaining information.
    Parameters::
        name: The name of the group to create.
        role: The role given to people who join the group.
        channel: The text channel which can access this group.
        clock channel: The voice channel displaying the status of the group timer.
    Related:
        group, groups, delgroup
    Examples``:
        newgroup Espresso
        newgroup Espresso, Study Group 1, #study-channel, #espresso-vc
    """
    args = ctx.arg_str.split(",")
    args = [arg.strip() for arg in args]

    if len(args) == 4:
        name, role_str, channel_str, clockchannel_str = args

        # Find the specified objects
        try:
            role = await ctx.find_role(role_str.strip(), interactive=True)
            channel = await ctx.find_channel(channel_str.strip(), interactive=True)
            clockchannel = await ctx.find_channel(clockchannel_str.strip(), interactive=True)
        except UserCancelled:
            raise UserCancelled("User cancelled selection, no group was created.") from None
        except ResponseTimedOut:
            raise ResponseTimedOut("Selection timed out, no group was created.") from None

        # Create the timer
        timer = ctx.client.interface.create_timer(ctx.client, name, role, channel, clockchannel)
    elif len(args) >= 1 and args[0]:
        timer = await newgroup_interactive(ctx, name=args[0])
    else:
        timer = await newgroup_interactive(ctx)

    await ctx.reply("Group **{}** has been created and bound to channel {}.".format(timer.name, timer.channel.mention))


async def newgroup_interactive(ctx, name=None, role=None, channel=None, clock_channel=None):
    """
    Interactivly create a new study group.
    Takes keyword arguments to use any pre-existing data.
    """
    try:
        if name is None:
            name = await ctx.input("Please enter a friendly name for the new study group:")
        while role is None:
            role_str = await ctx.input(
                "Please enter the study group role. "
                "This role is given to people who join the group, "
                "and is used for notifications. "
                "It needs to be mentionable, and I need permission to give it to users.\n"
                "(Accepted input: Role name or partial name, role id, or role mention.)"
            )
            role = await ctx.find_role(role_str.strip(), interactive=True)

        while channel is None:
            channel_str = await ctx.input(
                "Please enter the text channel to bind the group to. "
                "The group will only be accessible from commands in this channel, "
                "and the channel will host the pinned status message for this group.\n"
                "(Accepted input: Channel name or partial name, channel id or channel mention.)"
            )
            channel = await ctx.find_channel(channel_str.strip(), interactive=True)

        while clock_channel is None:
            clock_channel_str = await ctx.input(
                "Please enter the group clock voice channel. "
                "The name of this channel will be updated with the current stage and time remaining. "
                "It is recommended that the channel only be visible to the study group role. "
                "I must have permission to update the name of this channel.\n"
                "(Accepted input: Channel name or partial name, channel id or channel mention.)"
            )
            channel = await ctx.find_channel(
                clock_channel_str.strip(),
                interactive=True,
                type=discord.ChannelType.voice
            )
    except UserCancelled:
        raise UserCancelled(
            "User cancelled during group creationa! "
            "No group was created."
        ) from None
    except ResponseTimedOut:
        raise ResponseTimedOut(
            "Timed out waiting for a response during group creation! "
            "No group was created."
        ) from None

    # We now have all the data we need
    return ctx.client.interface.create_timer(ctx.client, name, role, channel, clock_channel)


@cmd("delgroup",
     group="Timer Config",
     desc="Remove a timer group.")
async def cmd_dellgrp(ctx):
    """
    Usage``:
        delgroup <name>
    Description:
        Deletes the given group from the collection of timer groups in the current guild.
        If `name` is not given or matches multiple groups, will prompt for group selection.
    Parameters::
        name: The name of the group to delete.
    Related:
        group, groups, newgroup
    Examples``:
        delgroup Espresso
    """
    # Build lists of matching timers in the guild, and their names
    guild_timers = ctx.client.interface.get_guild_timers(ctx.guild.id)
    guild_timers = [timer for timer in guild_timers if ctx.arg_str in timer.name]
    names = [timer.name for timer in guild_timers]

    # Get the timer, prompting the user if there are multiple matches
    if not names:
        return await ctx.reply("No matching timers found!")
    elif len(names) == 1:
        timer = guild_timers[0]
    else:
        try:
            selected = await ctx.selector(names)
        except ResponseTimedOut:
            raise ResponseTimedOut("Group selection timed out! No groups were deleted.") from None
        except UserCancelled:
            raise UserCancelled("User cancelled group selection! No groups were deleted.") from None

        timer = guild_timers[selected]

    # Delete the timer
    ctx.client.interface.destroy_timer(timer)

    # Notify the user
    await ctx.reply("The group `{}` has been removed!".format(timer.name))
