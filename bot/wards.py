from cmdClient import check
from cmdClient.checks import in_guild

from utils.timer_utils import is_timer_admin


@check(
    name="TIMER_READY",
    msg="I am restarting! Please try again in a moment."
)
async def timer_ready(ctx, *args, **kwargs):
    return ctx.client.interface.ready


@check(
    name="TIMER_ADMIN",
    msg=("You need to have one of the following to do this!\n"
         "- The `administrator` server permission.\n"
         "- The timer admin role (see the `timeradmin` command)."),
    requires=[in_guild]
)
async def timer_admin(ctx, *args, **kwargs):
    return await is_timer_admin(ctx.author)


@check(
    name="HAS_TIMERS",
    msg="No study groups have been created! Create a new group with the `newgroup` command.",
    requires=[in_guild, timer_ready]
)
async def has_timers(ctx, *args, **kwargs):
    return bool(ctx.timers.get_timers_in(ctx.guild.id))


@check(
    name="ADMIN",
    msg=("You need to be a server admin to do this!"),
    requires=[in_guild]
)
async def guild_admin(ctx, *args, **kwargs):
    return ctx.author.guild_permissions.administrator
