import discord
from cmdClient import cmd

from data import tables
from utils.lib import prop_tabulate


@cmd("about",
     group="Meta",
     short_help="Display some general information about me.")
async def cmd_about(ctx):
    """
    Usage``:
        {prefix}about
    Description:
        Replies with some general information about me.
    """
    # Gather usage statistics
    guild_row = tables.guilds.select_one_where(select_columns=('COUNT()',))
    guild_count = guild_row[0] if guild_row else 0

    timer_row = tables.timers.select_one_where(select_columns=('COUNT()',))
    timer_count = timer_row[0] if timer_row else 0

    session_row = tables.sessions.select_one_where(select_columns=('COUNT()', 'SUM(duration)'))
    session_count = session_row[0] if session_row else 0
    session_time = session_row[1] // 3600 if session_row else 0

    stats = {
        'Guilds': str(guild_count),
        'Timers': str(timer_count),
        'Recorded': "`{}` hours over `{}` sessions".format(session_time, session_count)
    }
    stats_str = prop_tabulate(*zip(*stats.items()))

    # Define links
    links = {
        'Support server': "https://discord.gg/MnMrQDe",
        'Invite me!': ("https://discordapp.com/oauth2/authorize"
                       "?client_id=674238793431384067&scope=bot&permissions=271608912"),
        'Github page': "https://github.com/Intery/PomoBot"
    }
    link_str = ', '.join("[{}]({})".format(name, link) for name, link in links.items())

    # Create embed
    desc = (
        "Flexible study or work group timer using a customisable Pomodoro system.\n"
        "Supports multiple groups and different timer setups.\n"
        "{stats}\n\n"
        "{links}"
    ).format(stats=stats_str, links=link_str)
    embed = discord.Embed(
        description=desc,
        colour=discord.Colour(0x9b59b6),
        title='About Me'
    )

    # Finally send!
    await ctx.reply(embed=embed)


@cmd("support",
     group="Meta",
     short_help="Sends my support server invite link.")
async def cmd_support(ctx):
    """
    Usage``:
        {prefix}support
    Description:
        Replies with the support server link.
    """
    await ctx.reply("Chat with our friendly support team here: https://discord.gg/MnMrQDe")


@cmd("invite",
     group="Meta",
     short_help="Invite me.")
async def cmd_invite(ctx):
    """
    Usage``:
        {prefix}invite
    Description:
        Replies with the bot invite link.
    """
    await ctx.reply("Invite PomoBot to your server with this link: {}".format(
        "<https://discordapp.com/oauth2/authorize?client_id=674238793431384067&scope=bot&permissions=271608912>"
    ))
