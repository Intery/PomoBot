import datetime as dt

from cmdClient import cmd
from cmdClient import checks

from utils import interactive # noqa


@cmd("history",
     group="Registry",
     desc="Display a list of past sessions in the current guild.",
     aliases=['hist'])
@checks.in_guild()
async def cmd_hist(ctx):
    """
    Usage``:
        history
    Description:
        Display a list of your past timer sessions in the current guild.
        All times are given in UTC.
    """
    # Get the past sessions for this user
    sessions = ctx.client.interface.registry.get_sessions_where(userid=ctx.author.id, guildid=ctx.guild.id)

    # Get the current timer if it exists
    timer = ctx.client.interface.get_timer_for(ctx.author.id)

    # Quit if we don't have anything
    if not sessions and not timer:
        return ctx.reply("You have not completed any timer sessions!")

    # Get today's date and timestamp
    today = dt.datetime.utcnow().date()
    today = dt.datetime(today.year, today.month, today.day)
    today_ts = dt.datetime.timestamp(today)

    # Build a sorted list of the author's sessions
    session_table = sorted(
        [(sesh['starttime'], sesh['duration']) for sesh in sessions],
        key=lambda tup: tup[0],
        reverse=True
    )

    # Add the current session if it exists
    if timer:
        sesh_data = timer.subscribed[ctx.author.id].session_data()
        session_table.insert(0, (sesh_data[3], sesh_data[4]))

    # Build the map (date_string, [session strings])
    day_sessions = []

    current_offset = 0
    current_sessions = []
    current_total = 0
    for start, dur in session_table:
        # Get current offset and corresponding session list
        date_offset = (today_ts - start) // (60 * 60 * 24) + 1

        # If we have a new offset, generate and store the old day's data
        if date_offset > current_offset:
            if current_sessions:
                day_str = (today - dt.timedelta(current_offset)).strftime("%A, %d %b %Y")
                dur_str = "{:<13}      {}".format("Total:", _parse_duration(current_total))
                day_sessions.append((day_str, current_sessions, dur_str))

            current_offset = date_offset
            current_sessions = []
            current_total = 0

        # Generate the session string
        sesh_str = "{} - {}  --  {}".format(
            dt.datetime.fromtimestamp(start).strftime("%H:%M"),
            dt.datetime.fromtimestamp(start + dur).strftime("%H:%M"),
            _parse_duration(dur)
        )
        current_sessions.append(sesh_str)

        current_total += dur

    # Add the last day
    # TODO: Is there a nicer recipe for this?
    if current_sessions:
        day_str = (today - dt.timedelta(current_offset)).strftime("%A, %d %b %Y")
        dur_str = "{:<13}      {}".format("Total:", _parse_duration(current_total))
        day_sessions.append((day_str, current_sessions, dur_str))

    # Make the pages
    pages = []
    num = len(day_sessions)
    for i, (day_str, sessions, total_str) in enumerate(day_sessions):
        page_str = " ({}/{})".format(i+1, num) if num > 1 else ""
        header = day_str + page_str

        page = (
            "All times are in UTC! The current time in UTC is {now}.\n"
            "```md\n"
            "{header}\n"
            "{header_rule}\n"
            "{session_list}\n"
            "{total_rule}\n"
            "{total_str}"
            "```"
        ).format(
            now=dt.datetime.utcnow().strftime("**%H:%M** on **%d %b %Y**"),
            header=header,
            header_rule='=' * len(header),
            session_list='\n'.join(sessions),
            total_rule='+' + (len(total_str) - 2) * '-' + '+',
            total_str=total_str
        )
        pages.append(page)

    # Finally, run the pager
    await ctx.pager(pages)


def _parse_duration(dur):
    dur = int(dur)
    hours = dur // 3600
    minutes = (dur % 3600) // 60
    seconds = dur % 60

    return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
