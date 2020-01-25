import discord

from cmdClient import cmd
from cmdClient.lib import ResponseTimedOut, UserCancelled

# from Timer import create_timer


@cmd("newgroup",
     group="Timer Config",
     desc="Create a new timer group.")
async def cmd_addgrp(ctx):
    """
    Usage:
        newgroup
        newgroup <name>
        newgroup <name>, <role>, <channel>, <clock channel>
    Description:
        Creates a new group with the specified properties.
        With no arguments or just `name`, uses guided prompts to get the remaining information.
    Related:
        Use `group` to see information about a particular group.
        Use `groups` to view or manage the guild's groups.
        Use `delgroup` to delete a group.
    Examples:
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
