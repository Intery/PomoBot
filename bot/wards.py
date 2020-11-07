from cmdClient import check


@check(
    name="TIMER_ADMIN",
    msg=("You need to have one of the following to use this command.\n"
         "- The `manage_guild` permission in this guild.\n"
         "- The timer admin role (refer to the `adminrole` command).")
)
async def timer_admin(ctx, *args, **kwargs):
    if ctx.author.guild_permissions.manage_guild:
        return True

    roleid = ctx.client.config.guilds.get(ctx.guild.id, "timeradmin")
    if roleid is None:
        return False

    return roleid in [r.id for r in ctx.author.roles]


@check(
    name="TIMER_READY",
    msg="I am restarting! Please try again in a moment."
)
async def timer_ready(ctx, *args, **kwargs):
    return ctx.client.interface.ready
