from utils import seekers, ctx_addons  # noqa
from wards import has_timers, timer_admin

from Timer import module


@module.cmd("forcekick",
            group="Timer Control",
            short_help="Kick a member from a study group.",
            aliases=('kick',))
@has_timers()
@timer_admin()
async def cmd_forcekick(ctx):
    """
    Usage``:
        {prefix}forcekick <user>
    Description:
        Forcefully unsubscribe a group member.

        *Requires timer admin permissions.*
    Examples``:
        {prefix}forcekick {ctx.author.name}
    """
    if not ctx.args:
        return await ctx.error_reply(
            "**Usage:** `{}forcekick <user>`\n"
            "Please provided a user to kick.".format(ctx.best_prefix)
        )
    subscribers = [
        sub for timer in ctx.timers.get_timers_in(ctx.guild.id) for sub in timer.subscribers.values()
    ]
    members = [
        sub.member for sub in subscribers if sub.member
    ]
    if len(members) != len(subscribers):
        # There are some subscribers without a member! First get them
        for sub in subscribers:
            if not sub.member:
                await sub._fetch_member()
        members = [
            sub.member for sub in subscribers if sub.member
        ]

    member = await ctx.find_member(ctx.args, collection=members, silent=True)
    if not member:
        return await ctx.error_reply("No subscriber found matching `{}`!".format(ctx.args))

    sub = ctx.timers.get_subscriber(member.id, member.guild.id)
    if not sub:
        return await ctx.error_reply("This member is no longer subscribed!")

    await sub.timer.unsubscribe(sub.userid, post=True)

    if ctx.ch != sub.timer.channel:
        await ctx.embed_reply("{} was unsubscribed.".format(member.mention))
