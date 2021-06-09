import datetime as dt
import json

import pytz
import discord
from cmdClient.checks import in_guild

from Timer import module, Pattern
from Timer.lib import parse_dur

from data import tables
from data.queries import get_session_user_totals
from utils.lib import paginate_list, timestamp_utcnow, prop_tabulate
from wards import timer_admin, has_timers
from settings import UserSettings


@module.cmd("leaderboard",
            group="Registry",
            short_help="Server study leaderboards over a given time period.",
            aliases=('lb',))
@has_timers()
async def cmd_leaderboard(ctx):
    """
    Usage``:
        {prefix}lb [day | week | month | year]
    Description:
        Display the server study board in the given timeframe (or all time).

        The timeframe is determined using the *guild timezone* (see `{prefix}timezone`).
    Examples``:
        {prefix}lb
        {prefix}lb week
        {prefix}lb year
    """
    # Extract the target timeframe
    title = None
    period_start = None
    spec = ctx.args.lower()
    timezone = ctx.guild_settings.timezone.value
    day_start = dt.datetime.now(tz=timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    if not spec or spec == 'all':
        period_start = None
        title = "All-Time Leaderboard"
    elif spec == 'day':
        period_start = day_start
        title = "Daily Leaderboard"
    elif spec == 'week':
        period_start = day_start - dt.timedelta(days=day_start.weekday())
        title = "Weekly Leaderboard"
    elif spec == 'month':
        period_start = day_start.replace(day=1)
        title = "{} Leaderboard".format(period_start.strftime('%B'))
    elif spec == 'year':
        period_start = day_start.replace(month=1, day=1)
        title = "{} Leaderboard".format(period_start.year)
    else:
        return await ctx.error_reply(
            "Unrecognised timeframe `{}`.\n"
            "**Usage:**`{}leaderboard day | month | week | year`".format(ctx.args, ctx.best_prefix)
        )
    start_ts = int(period_start.astimezone(pytz.utc).timestamp() if period_start else 0)

    # lb data from saved sessions
    lb_rows = get_session_user_totals(start_ts, guildid=ctx.guild.id)

    # Currently running sessions
    subscribers = {
        sub.userid: sub
        for timer in ctx.timers.get_timers_in(ctx.guild.id) for sub in timer.subscribers.values()
        if sub.session
    }

    # Calculate names and totals
    names = {}
    user_totals = {}
    for row in lb_rows:
        names[row['userid']] = row['name'] or str(row['userid'])
        user_totals[row['userid']] = row['total']

    max_unsaved = int(timestamp_utcnow() - start_ts)
    for uid, sub in subscribers.items():
        if sub.member:
            names[uid] = sub.member.name
        elif uid not in names:
            names[uid] = sub.name

        user_totals[uid] = user_totals.get(uid, 0) + min((sub.unsaved_time, max_unsaved))

    if not user_totals:
        return await ctx.reply(
            "No session data to show! "
            "Join a running timer to start recording data."
        )

    # Sort based on total duration
    sorted_totals = sorted(
        [(uid, names[uid], user_totals[uid]) for uid in user_totals],
        key=lambda tup: tup[2],
        reverse=True
    )

    # Format and find index of author
    lb_strings = []
    author_index = None
    max_name_len = min((30, max(len(name) for name in names.values())))
    for i, (uid, name, total) in enumerate(sorted_totals):
        if author_index is None and uid == ctx.author.id:
            author_index = i
        lb_strings.append(
            "{:<{}}\t{:<9}".format(
                name,
                max_name_len,
                parse_dur(total, show_seconds=True)
            )
        )

    page_len = 20
    pages = paginate_list(lb_strings, block_length=page_len, title=title)
    start_page = author_index // page_len if author_index is not None else 0

    await ctx.pager(
        pages,
        start_at=start_page
    )


_history_pattern = """\
```md
{day} ({tz}) (Page {page}/{page_count})

Period        | Duration | Focused  | Pattern
---------------------------------------------
{sessions}
+-----------------------------------+
{total}
```
"""
_history_session_pattern = (
    "{start} - {end} | {duration} | {focused} | {pattern}"
)
_history_total_pattern = (
    "{start} - {end} | {duration} | {focused}"
)


@module.cmd("history",
            group="Registry",
            short_help="Show your personal study session history.",
            aliases=('hist',))
@in_guild()
async def cmd_history(ctx):
    """
    Usage``:
        {prefix}history
    Description:
        Display your day by day study session history.

        The times are determined using your personal timezone (see `{prefix}mytimezone`).
    """
    timezone = ctx.author_settings.timezone.value

    # Get the saved session rows, ordered by newest first
    rows = tables.session_patterns.select_where(
        _extra="ORDER BY start_time DESC",
        guildid=ctx.guild.id,
        userid=ctx.author.id
    )

    if not rows:
        return await ctx.reply(
            "You have no recorded sessions! Join a running timer to start recording study time!"
        )

    # Bin these into days
    day_rows = {}
    for row in rows:
        # Get the row day
        start_day = (
            dt.datetime
            .utcfromtimestamp(row['start_time'])
            .replace(tzinfo=pytz.utc)
            .astimezone(timezone)
            .strftime("%A, %d/%b/%Y")
        )
        if start_day not in day_rows:
            day_rows[start_day] = [row]
        else:
            day_rows[start_day].append(row)

    # Create the pages
    # TODO: If there are too many sessions in a day (~30), this may cause overflow issues
    pages = []
    page_count = len(day_rows)
    for i, (day, rows) in enumerate(day_rows.items()):
        # Sort day sessions in time ascending order
        rows.reverse()

        # Build session lines
        row_lines = []
        for row in rows:
            start = (
                dt.datetime
                .utcfromtimestamp(row['start_time'])
                .replace(tzinfo=pytz.utc)
                .astimezone(timezone)
            )
            end = start + dt.timedelta(seconds=row['duration'])
            pattern = '/'.join(str(stage[1]) for stage in json.loads(row['stage_str'])) if row['stage_str'] else ''
            row_lines.append(
                _history_session_pattern.format(
                    start=start.strftime("%H:%M"),
                    end=end.strftime("%H:%M"),
                    duration=parse_dur(row['duration'] or 0, show_seconds=True),
                    focused=parse_dur(row['focused_duration'] or 0, show_seconds=True),
                    pattern=pattern
                )
            )
        sessions = '\n'.join(row_lines)

        # Build total info
        start = (
            dt.datetime
            .utcfromtimestamp(rows[0]['start_time'])
            .replace(tzinfo=pytz.utc)
            .astimezone(timezone)
            .strftime("%H:%M")
        )
        end = (
            dt.datetime
            .utcfromtimestamp(rows[-1]['start_time'] + rows[-1]['duration'])
            .replace(tzinfo=pytz.utc)
            .astimezone(timezone)
            .strftime("%H:%M")
        )
        duration = sum(row['duration'] for row in rows)
        focused = sum(row['focused_duration'] or 0 for row in rows)
        total_str = _history_total_pattern.format(
            start=start,
            end=end,
            duration=parse_dur(duration, show_seconds=True),
            focused=parse_dur(focused, show_seconds=True)
        )

        # Add to page list
        pages.append(
            _history_pattern.format(
                day=day,
                tz=timezone,
                page=i+1,
                page_count=page_count,
                sessions=sessions,
                total=total_str
            )
        )
    await ctx.pager(pages)


def utctimestamp(aware_dt):
    return int(aware_dt.astimezone(pytz.utc).timestamp())


def _get_user_time_since(guildid, userid, period_start):
    start_ts = int(utctimestamp(period_start) if period_start else 0)
    rows = get_session_user_totals(start_ts, guildid=guildid, userid=userid)
    return rows[0]['total'] if rows else 0


@module.cmd("stats",
            group="Registry",
            short_help="View a table of personal study statistics.",
            aliases=('profile',))
@has_timers()
async def cmd_stats(ctx):
    """
    Usage``:
        {prefix}stats
        {prefix}stats <user-mention>
    Description:
        View summary study statistics for yourself or the mentioned user.
    """
    target = None
    if ctx.args:
        maybe_id = ctx.args.strip('<!@>')
        if not maybe_id.isdigit():
            return await ctx.error_reply(
                "**Usage:** `{}stats [mention]`\n"
                "Couldn't parse `{}` as a user mention or id!".format(ctx.best_prefix, ctx.args)
            )
        targetid = int(maybe_id)
        target = ctx.guild.get_member(targetid)
    else:
        target = ctx.author
        targetid = ctx.author.id

    timezone = UserSettings(targetid).timezone.value
    day_start = dt.datetime.now(tz=timezone).replace(hour=0, minute=0, second=0, microsecond=0)

    sub = ctx.timers.get_subscriber(targetid, ctx.guild.id)
    if not target and sub and sub.member:
        target = sub.member
    unsaved = sub.unsaved_time if sub else 0

    # Total session count and duration
    summary_row = tables.sessions.select_one_where(
        select_columns=('COUNT() AS count', 'SUM(duration) AS total'),
        userid=targetid,
        guildid=ctx.guild.id
    )
    if not summary_row['count']:
        if target == ctx.author:
            return await ctx.embed_reply(
                "You have no recorded sessions! Join a running timer to start recording study time!"
            )
        else:
            return await ctx.embed_reply(
                "<@{}> has no recorded sessions!".format(targetid)
            )
    session_count = summary_row['count']
    total_duration = summary_row['total']

    # Favourites
    pattern_rows = tables.session_patterns.select_where(
        select_columns=('SUM(duration) AS total', 'patternid'),
        _extra="GROUP BY patternid ORDER BY total DESC LIMIT 5",
        userid=targetid,
        guildid=ctx.guild.id
    )
    print([dict(row) for row in pattern_rows])
    pattern_pairs = [
        (Pattern.get(row['patternid']).display(brief=True, truncate=6) if row['patternid'] is not None else "Unknown",
         row['total'])
        for row in pattern_rows
    ]
    max_len = max(len(p) for p, _ in pattern_pairs)
    pattern_block = "```{}```".format(
        '\n'.join(
            "{:<{}} - {} ({}%)".format(
                pattern,
                max_len,
                parse_dur(total),
                (total * 100) // total_duration
            )
            for pattern, total in pattern_pairs
        )
    )

    timer_rows = tables.session_patterns.select_where(
        select_columns=('SUM(duration) AS total', 'roleid'),
        _extra="GROUP BY roleid ORDER BY total DESC LIMIT 5",
        userid=targetid,
        guildid=ctx.guild.id
    )
    timer_pairs = []
    for row in timer_rows:
        timer_row = tables.timers.fetch(row['roleid'])
        if timer_row:
            name = timer_row.name
        else:
            name = str(row['roleid'])
        timer_pairs.append((name, row['total']))
    max_len = max(len(t) for t, _ in timer_pairs)
    timer_block = "```{}```".format(
        '\n'.join(
            "{:^{}} - {} ({}%)".format(
                timer_name,
                max_len,
                parse_dur(total),
                (total * 100) // total_duration
            )
            for timer_name, total in timer_pairs
        )
    )

    # Calculate streak and first session
    streak = 0
    day_window = (day_start, day_start + dt.timedelta(days=1))
    ts_window = (utctimestamp(day_window[0]), utctimestamp(day_window[1]))

    session_rows = tables.sessions.select_where(
        select_columns=('start_time', 'start_time + duration AS end_time'),
        _extra="ORDER BY start_time DESC",
        guildid=ctx.guild.id,
        userid=targetid
    )
    first_session_ts = session_rows[-1]['start_time']
    session_periods = ((row['start_time'], row['end_time']) for row in session_rows)

    # Account for the current day
    start_time, end_time = next(session_periods, (0, 0))
    if sub or end_time > ts_window[0]:
        streak += 1
    day_window = (day_window[0] - dt.timedelta(days=1), day_window[0])
    ts_window = (utctimestamp(day_window[0]), ts_window[0])

    for start, end in session_periods:
        if end < ts_window[0]:
            break
        elif start < ts_window[1]:
            streak += 1
            day_window = (day_window[0] - dt.timedelta(days=1), day_window[0])
            ts_window = (utctimestamp(day_window[0]), ts_window[0])

    # Binned time totals
    time_totals = {}
    total_fields = {
        'Today': day_start,
        'This Week': day_start - dt.timedelta(days=day_start.weekday()),
        'This Month': day_start.replace(day=1),
        'This Year': day_start.replace(month=1, day=1),
        'All Time': None
    }
    for name, start in total_fields.items():
        time_totals[name] = parse_dur(
            _get_user_time_since(ctx.guild.id, targetid, start) + unsaved,
            show_seconds=False
        )
    subtotal_table = prop_tabulate(*zip(*time_totals.items()))

    # Format stats into the final embed
    desc = (
        "**{}** sessions completed, with a total of **{}** hours."
    ).format(session_count, total_duration // 3600)
    if sub:
        desc += "\nCurrently studying in **{}** (in {}) for **{}**!".format(
            sub.timer.name,
            sub.timer.channel.mention,
            parse_dur(sub.clocked_time + unsaved, show_seconds=True)
        )

    embed = (
        discord.Embed(
            title="Study Statistics",
            description=desc,
            timestamp=dt.datetime.utcfromtimestamp(first_session_ts)
        )
        .set_footer(text="Studying Since")
        .add_field(
            name="Subtotals",
            value=subtotal_table,
            inline=True
        )
        .add_field(
            name="Streak",
            value="**{}** days!".format(streak),
            inline=True
        )
        .add_field(
            name="Favourite Patterns",
            value=pattern_block,
            inline=False
        )
        .add_field(
            name="Favourite Groups",
            value=timer_block,
            inline=True
        )
    )
    if not target:
        try:
            target = await ctx.guild.fetch_member(targetid)
        except discord.HTTPException:
            pass
    if target:
        embed.set_author(name=target.name, icon_url=target.avatar_url)
    else:
        row = tables.users.fetch(targetid)
        name = row.name if row else str(target.id)
        embed.set_author(name=name)
    await ctx.reply(embed=embed)


@module.cmd("clearregistry",
            group="Registry Admin",
            short_help="Remove all session history in this server.")
@timer_admin()
async def cmd_clearregistry(ctx):
    """
    Usage``:
        {prefix}clearregistry
    Description:
        Remove **all** session history in the server.
        This will reset the server leaderboard, along with all personal statistics (including `stats` and `hist`).
        ***This cannot be undone.***

        *This command requires timer admin permissions.*
    """
    prompt = (
        "Are you sure you want to delete **all** session history in this server? "
        "This will reset the leaderboard and all member history. "
        "**This cannot be undone**."
    )
    if not await ctx.ask(prompt):
        return
    tables.sessions.delete_where(guildid=ctx.guild.id)
    await ctx.reply("All session data has been deleted.")


"""
@module.cmd("forgetuser",
            group="Registry Admin",
            short_help="Remove all session history for a given member.")
@in_guild()
async def cmd_forgetuser(ctx):
    ...


@module.cmd("delsession",
            group="Registry Admin",
            short_help="Remove a selected session from the registry.")
@in_guild()
async def cmd_delsession(ctx):
    ...


@module.cmd("showsessions",
            group="Registry Admin",
            short_help="Show recent study sessions, with optional filtering.")
@in_guild()
async def cmd_showsessions(ctx):
    ...


@module.cmd("showtimerhistory",
            group="Registry Admin",
            short_help="Show the pattern log for a given timer.")
@in_guild()
async def cmd_showtimerhistory(ctx):
    ...
"""
