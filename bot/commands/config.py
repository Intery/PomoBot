from cmdClient import cmd
from cmdClient.lib import ResponseTimedOut, UserCancelled

# from Timer import create_timer

from utils import seekers


@cmd("addgroup")
async def cmd_addgrp(ctx):
    """
    Usage:
        addgroup <group name>, <study role>, <study channel>, <timer voice channel>
    Description:
        Creates a new group with the specified properties.
        Use `delgroup` to remove a group and `groups` to view the guild's groups.
    """
    # TODO: Interactive input when one or no args are given.
    args = ctx.arg_str.split(",")
    if len(args) != 4:
        return await ctx.error_reply(
            "Incorrect number of arguments! Usage:\n"
            "`addgroup <group name>, <study role>, <study channel>, <timer voice channel>`"
        )

    name, role_str, channel_str, vchannel_str = args

    # Find the specified objects
    try:
        role = await ctx.find_role(role_str.strip(), interactive=True)
        channel = await ctx.find_channel(channel_str.strip(), interactive=True)
        vchannel = await ctx.find_channel(vchannel_str.strip(), interactive=True)
    except UserCancelled:
        raise UserCancelled("User cancelled selection, no group was created.") from None
    except ResponseTimedOut:
        raise ResponseTimedOut("Selection timed out, no group was created.") from None

    if role is None or channel is None or vchannel is None:
        return

    # Create the timer
    create_timer(ctx.client, name, role, channel, vchannel)

    await ctx.reply("Group **{}** has been created and bound to channel {}.".format(name, channel.mention))
