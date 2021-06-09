import asyncio
import logging
import discord

from cmdClient import cmd
from cmdClient.lib import ResponseTimedOut
from cmdClient.Context import Context

from Timer import Pattern
from utils import ctx_addons, seekers, interactive  # noqa
from wards import timer_admin, timer_ready


@cmd('newgroup',
     group="Group Admin",
     aliases=('newtimer', 'create', 'creategroup'),
     short_help="Create a new study group.",
     flags=('role==', 'channel==', 'voice==', 'pattern=='))
@timer_admin()
@timer_ready()
async def cmd_newgroup(ctx: Context, flags):
    """
    Usage``:
        {prefix}newgroup <group-name> [flags]
    Description:
        Create a new study group (also called a timer) in the guild.
    Flags::
        role: Role to give to members in the study group.
        channel: Text channel where timer messages are posted.
        voice: Voice channel associated with the group.
        pattern: Default timer pattern used when resetting the group timer.
    Examples``:
        {prefix}newgroup AwesomeStudyGroup
        {prefix}newgroup ExtraAwesomeStudyGroup --channel #studychannel --pattern 50/10
    """
    timers = ctx.timers.get_timers_in(ctx.guild.id)

    # Parse the group name
    name = ctx.args
    if name:
        if len(name) > 30:
            return await ctx.error_reply("The group name must be under 30 characters!")
    else:
        while not name or len(name) > 30:
            try:
                if not name:
                    name = await ctx.input("Please enter a name for the new study group:")
                else:
                    name = await ctx.input("The group name must be under 30 characters! Please try again:")
            except ResponseTimedOut:
                raise ResponseTimedOut("Session timed out! No group created.")

    if any(name.lower() == timer.data.name.lower() for timer in timers):
        return await ctx.error_reply("There is already a group with this name!")
    name_line = "**Creating new study group `{}`.**".format(name)

    # Parse flags
    role = None
    if flags['role']:
        role = await ctx.find_role(flags['role'], interactive=True)
        if not role:
            return

    channel = None
    if flags['channel']:
        channel = await ctx.find_channel(flags['channel'], interactive=True, chan_type=discord.ChannelType.text)
        if not channel:
            return

    voice = None
    if flags['voice']:
        voice = await ctx.find_channel(flags['voice'], interactive=True, chan_type=discord.ChannelType.voice)
        if not voice:
            return

    pattern = None
    if flags['pattern']:
        pattern = Pattern.from_userstr(flags['pattern'])

    # Extract parameters and report lines
    me = ctx.guild.me

    role_line = ""
    role_error_line = ""
    role_created = False
    guild_perms = me.guild_permissions
    if not guild_perms.manage_roles:
        role_error_line = "Lacking `MANAGE ROLES` guild permission."
    elif role is not None:
        role_line = "Using provided group role {}.".format(role.mention)
        if role >= me.top_role:
            role_error_line = "Provided role {} is higher than my top role.".format(role.mention)
        elif any(role.id == timer.data.roleid for timer in timers):
            role_error_line = "Provided role {} is already associated to a group!".format(role.mention)
    else:
        # Attempt to find existing role
        role = next((role for role in ctx.guild.roles if role.name.lower() == name.lower()), None)
        if role:
            if role >= me.top_role:
                role_line = "Found existing role {}, but it is higher than my top role. ".format(role.mention)
                role = None
            else:
                role_line = "Using existing group role {}.".format(role.mention)

        if not role:
            # Create a new role
            role = await ctx.guild.create_role(name=name)
            role_created = True
            await asyncio.sleep(0.1)  # Ensure the caches are populated
            role_line += "Created the study group role {}.".format(role.mention)
    role_line += " This role will automatically be given to members when they join the group."

    channel = channel or ctx.ch
    channel_error_line = ''
    chan_perms = channel.permissions_for(me)
    if not chan_perms.read_messages:
        channel_error_line = "Cannot read messages in {}.".format(channel.mention)
    elif not chan_perms.send_messages:
        channel_error_line = "Cannot send messages in {}.".format(channel.mention)
    elif not chan_perms.read_message_history:
        channel_error_line = "Cannot read message history in {}.".format(channel.mention)
    elif not chan_perms.embed_links:
        channel_error_line = "Cannot send embeds in {}.".format(channel.mention)
    elif not chan_perms.manage_messages:
        channel_error_line = "Cannot manage messages in {}.".format(channel.mention)

    voice_line = ""
    voice_error_line = ""
    if voice is None:
        voice_line = (
            "To associate a voice channel (for voice alerts or to auto-join members) "
            "use `{}tconfig \"{}\" voice <voice-channel>`."
        ).format(ctx.best_prefix, name)
    else:
        other = next(
            (timer for timer in ctx.timers.get_timers_in(ctx.guild.id) if timer.voice_channelid == voice.id),
            None
        )

        voice_line = (
            "Group bound to provided voice channel {}.".format(voice.mention)
        )
        voice_perms = voice.permissions_for(me)
        if other is not None:
            voice_error_line = "{} is already bound to the group **{}**.".format(
                voice.mention,
                other.name
            )
        elif not voice_perms.connect:
            voice_error_line = "Cannot connect to voice channel."
        elif not voice_perms.speak:
            voice_error_line = "Cannot speak in voice channel."
        elif not voice_perms.view_channel:
            voice_error_line = "Cannot see voice channel."

    pattern_line = (
        "The default timer pattern (applied when the timer is reset, e.g. by `{0}reset`) is `{1}`. "
    ).format(
        ctx.best_prefix,
        (pattern if pattern is not None else Pattern.get(0)).display(brief=True),
    )

    lines = [name_line, role_line, pattern_line, voice_line]
    errors = (role_error_line, channel_error_line, voice_error_line)
    if any(errors):
        # A permission error occured, report and exit
        error_lines = '\n'.join(
            '`{}`: {} {}'.format(cat, '❌' if error else '✅', '*{}*'.format(error) if error else '')
            for cat, error in zip(('Group role', 'Text channel', 'Voice channel'), errors)
        )

        embed = discord.Embed(
            title="Status",
            description=error_lines,
            colour=discord.Colour.red()
        )
        lines.append("**Couldn't create the new group due to a permission or parameter error.**")
        await ctx.reply(
            content='\n'.join(lines),
            embed=embed
        )
        if role_created:
            await role.delete()
    else:
        # Create the new group and report
        timer = ctx.timers.create_timer(
            role, channel, name,
            voice_channelid=voice.id if voice else None,
            patternid=pattern.row.patternid if pattern else 0
        )
        if not timer:
            # This shouldn't happen, due to the permission check
            ctx.client.log(
                "Failed to create timer!",
                context='mid:{}'.format(ctx.msg.id),
                level=logging.ERROR
            )
            lines.append("**An unknown error occured, please try again later.**")
            return await ctx.reply('\n'.join(lines))
        # TODO: Initial usage tips
        # Info about cloning?
        lines[0] = "**Created the study group {} in {}.**".format(
            '`{}`'.format(name) if name != role.name else role.mention,
            channel.mention
        )
        lines[1] = "The role {} will be automatically given to members when they join the group.".format(role.mention)
        lines.append("*For more advanced configuration options see `{}tconfig \"{}\"`.*".format(ctx.best_prefix, name))
        tips = (
            "• Join the new group using `{prefix}join` in {channel}{voice_msg}.\n"
            "• Then start the group timer with `{prefix}start`.\n"
            "• To change the pattern of work/break times instead use `{prefix}start <pattern>`.\n"
            " (E.g. `{prefix}start 50/10` for `50` minutes work and `10` minutes break.)\n\n"
            "For more information, see `{prefix}help` for the command list and introductory guides, "
            "and use `{prefix}help cmd` to get detailed help with a particular command."
        ).format(
            prefix=ctx.best_prefix,
            channel=channel.mention,
            voice_msg=", or by joining the {} voice channel.".format(voice.mention) if voice else ''
        )
        await ctx.reply(
            '\n'.join(lines),
            embed=discord.Embed(title="Usage Tips", description=tips),
            allowed_mentions=discord.AllowedMentions.none()
        )


@cmd('delgroup',
     group="Group Admin",
     aliases=('rmgroup',),
     short_help="Delete a study group.")
@timer_admin()
@timer_ready()
async def cmd_delgroup(ctx):
    """
    Usage``:
        {prefix}delgroup <group-name>
    Description:
        Delete a guild study group.
    Examples``:
        {prefix}delgroup {ctx.example_group_name}
    """
    groups = ctx.timers.get_timers_in(ctx.guild.id)
    group = next((group for group in groups if group.data.name.lower() == ctx.args.lower()), None)

    if group is None:
        await ctx.error_reply("No group found with the name `{}`.".format(ctx.args))
    else:
        if await ctx.ask("Are you sure you want to delete the group `{}`?".format(group.data.name)):
            await ctx.timers.obliterate_timer(group)
            await ctx.reply("Deleted the group `{}`.".format(group.data.name))
            if await ctx.ask("Do you also want to delete the group discord role **{}**?".format(group.role.name)):
                try:
                    await group.role.delete()
                except discord.HTTPException:
                    await ctx.reply("Failed to delete the associated role!")
