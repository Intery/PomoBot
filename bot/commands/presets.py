import datetime
import discord
from cmdClient.checks import in_guild

from Timer import Pattern, module

from data import tables
from utils import timer_utils, interactive, ctx_addons  # noqa
from utils.lib import prop_tabulate, paginate_list
from utils.timer_utils import is_timer_admin


def _fetch_presets(ctx):
    """
    Fetch the current valid presets in this context.
    Returns a list of the form (preset_type, preset_row).
    Accounts for user pattern name overrides.
    """
    user_rows = tables.user_presets.select_where(userid=ctx.author.id)
    guild_rows = tables.guild_presets.select_where(guildid=ctx.guild.id)

    presets = {}
    presets.update(
        {row['preset_name'].lower(): (0, row) for row in guild_rows}
    )
    presets.update(
        {row['preset_name'].lower(): (1, row) for row in user_rows}
    )
    return list(reversed(list(presets.values())))


def _format_preset(preset_type, preset_row):
    """
    Format the available patterns into a pretty-viewable list.
    Returns a list of tuples `(pattern_str, preset_type, pattern)`.
    """
    pattern = Pattern.get(preset_row['patternid'])
    return "{} ({}, {})".format(
                preset_row['preset_name'],
                'Personal' if preset_type == 1 else 'Server',
                pattern.display(brief=True)
            )


@module.cmd("savepattern",
            group="Saved Patterns",
            short_help="Name a given pattern.")
@in_guild()
async def cmd_savepattern(ctx):
    """
    Usage``:
        {prefix}savepattern <pattern>
    Description:
        See `{prefix}help patterns` for more information about timer patterns.
    Examples``:
        {prefix}savepattern 50/10
        {prefix}savepattern Work, 50, Good luck!; Break, 10, Have a rest.
    """
    if ctx.args:
        pattern = Pattern.from_userstr(ctx.args)
    else:
        # Get the current timer pattern, if applicable
        sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
        if sub is not None:
            pattern = sub.timer.current_pattern or sub.timer.default_pattern
        else:
            # Request pattern
            pattern = Pattern.from_userstr(await ctx.input(
                "Please enter the timer pattern you want to save.\n"
                "**Tip**: See `{}help patterns` for more information "
                "about creating or using timer patterns".format(ctx.best_prefix)
            ))

    # Confirm and request name
    name = await ctx.input(
        "Please enter a name for this pattern."
        "```{}```".format(pattern.display())
    )
    if not name:
        return

    # Ask for preset type
    pattern_type = 0
    if await is_timer_admin(ctx.author):
        options = (
            "User Pattern (the saved pattern is available to you across all servers).",
            "Server Pattern (the saved pattern is available to everyone in this server)."
        )
        pattern_type = await ctx.selector("Would you like to create a User or Server pattern?", options)

    # Save preset
    if pattern_type == 0:
        # User preset
        tables.user_presets.insert(userid=ctx.author.id, preset_name=name, patternid=pattern.row.patternid)
        await ctx.reply(
            "Saved the new user pattern `{name}`. "
            "Apply it by joining any study group and writing `{prefix}start {name}`.".format(
                prefix=ctx.best_prefix,
                name=name
            )
        )
    else:
        # Guild preset
        tables.guild_presets.insert(
            guildid=ctx.guild.id,
            preset_name=name,
            created_by=ctx.author.id,
            patternid=pattern.row.patternid
        )
        await ctx.reply(
            "Saved the new guild pattern `{name}`. "
            "Any member may now apply it by joining a study group and writing `{prefix}start {name}`.".format(
                prefix=ctx.best_prefix,
                name=name
            )
        )


@module.cmd("delpattern",
            group="Saved Patterns",
            short_help="Delete a saved pattern by name.",
            aliases=('rmpattern',))
@in_guild()
async def cmd_delpattern(ctx):
    """
    Usage``:
        {prefix}delpattern <pattern-name>
    Description:
        Delete the given saved pattern.
    """
    is_admin = await is_timer_admin(ctx.author)
    is_user_preset = True

    if not ctx.args:
        # Prompt for a saved pattern to remove
        presets = _fetch_presets(ctx)
        if not presets:
            return await ctx.reply(
                "No saved patterns exist yet! "
                "See `{}help savepattern` for information about saving a pattern.".format(
                    ctx.best_prefix
                )
            )
        if not is_admin:
            presets = [preset for preset in presets if preset[0] == 1]

        ids = [row['patternid'] for _, row in presets]
        tables.patterns.fetch_rows_where(patternid=ids)

        pretty_presets = [_format_preset(t, row) for t, row in presets]
        result = await ctx.selector(
            "Please select a saved pattern to remove.",
            pretty_presets
        )
        is_user_preset, row = presets[result]
    else:
        row = tables.user_presets.select_one_where(userid=ctx.author.id, preset_name=ctx.args)
        if not row:
            is_user_preset = False
            row = tables.guild_presets.select_one_where(guildid=ctx.guild.id, preset_name=ctx.args)
        if not row:
            return await ctx.error_reply(
                "No saved pattern found called `{}`.".format(ctx.args)
            )

    if not is_user_preset:
        if is_admin:
            tables.guild_presets.delete_where(guildid=ctx.guild.id, preset_name=ctx.args)
            await ctx.reply("Removed saved server pattern `{}`.".format(row['preset_name']))
        else:
            await ctx.error_reply("You need timer admin permissions to remove a saved server pattern!")
    else:
        tables.user_presets.delete_where(userid=ctx.author.id, preset_name=ctx.args)
        await ctx.reply("Removed saved personal pattern `{}`.".format(row['preset_name']))


@module.cmd("savedpatterns",
            group="Saved Patterns",
            short_help="View the accessible saved patterns.",
            aliases=('presets', 'patterns', 'showpatterns'))
@in_guild()
async def cmd_savedpatterns(ctx):
    """
    Usage``:
        {prefix}savedpatterns
    Description:
        List the personal and server-wide saved patterns accessible for custom timer setup.
    """
    presets = _fetch_presets(ctx)
    if not presets:
        return await ctx.reply(
            "No saved patterns exist yet! See `{}help savepattern` for information about saving a pattern.".format(
                ctx.best_prefix
            )
        )

    ids = [row['patternid'] for _, row in presets]
    tables.patterns.fetch_rows_where(patternid=ids)

    pretty_presets = [_format_preset(t, row) for t, row in presets]

    await ctx.pager(
        paginate_list(pretty_presets, title="Saved Patterns")
    )


@module.cmd("showpattern",
            group="Saved Patterns",
            short_help="View details about a saved pattern.")
@in_guild()
async def cmd_showpattern(ctx):
    """
    Usage``:
        {prefix}showpattern <pattern-name>
    Description:
        Show details about the provided saved pattern.
    """
    is_user_preset = True
    if not ctx.args:
        # Prompt for a saved pattern to display
        presets = _fetch_presets(ctx)
        if not presets:
            return await ctx.reply(
                "No saved patterns exist yet! See `{}help savepattern` for information about saving a pattern.".format(
                    ctx.best_prefix
                )
            )

        ids = [row['patternid'] for _, row in presets]
        tables.patterns.fetch_rows_where(patternid=ids)

        pretty_presets = [_format_preset(t, row) for t, row in presets]
        result = await ctx.selector(
            "Please select a saved pattern to view.",
            pretty_presets
        )
        is_user_preset, row = presets[result]
    else:
        row = tables.user_presets.select_one_where(userid=ctx.author.id, preset_name=ctx.args)
        if not row:
            is_user_preset = False
            row = tables.guild_presets.select_one_where(guildid=ctx.guild.id, preset_name=ctx.args)

        if not row:
            return await ctx.error_reply(
                "No saved pattern found called `{}`.".format(ctx.args)
            )

    # Extract pattern information
    pid = row['patternid']
    pattern = Pattern.get(pid)

    if is_user_preset:
        session_data = tables.sessions.select_one_where(
            select_columns=('SUM(duration)', ),
            patternid=pid,
            userid=ctx.author.id
        )
        setup_data = tables.timer_pattern_history.select_one_where(
            select_columns=('COUNT()', ),
            patternid=pid,
            modified_by=ctx.author.id
        )
    else:
        session_data = tables.sessions.select_one_where(
            select_columns=('SUM(duration)', ),
            patternid=pid,
            guildid=ctx.guild.id
        )
        setup_data = tables.timer_pattern_history.select_one_where(
            select_columns=('COUNT()', ),
            patternid=pid,
            timerid=[timer.role.id for timer in ctx.timers.get_timers_in(ctx.guild.id)]
        )
    total_dur = session_data[0] or 0
    times_used = setup_data[0] or 0

    table = prop_tabulate(
        ('Created by', 'Used', 'Used for'),
        ("<@{}>".format(ctx.author.id if is_user_preset else row['created_by']) if row['created_by'] else "Unknown",
         "{} times".format(times_used),
         "{:.1f} hours (total session duration)".format(total_dur / 3600))
    )
    embed = discord.Embed(
        title="{} Pattern `{}`".format('User' if is_user_preset else 'Guild', row['preset_name']),
        description=table,
        timestamp=datetime.datetime.utcfromtimestamp(row['created_at'])
    ).set_footer(
        text='Created At'
    ).add_field(
        name='Pattern',
        value="```{}```".format(pattern.display())
    )
    await ctx.reply(embed=embed)
