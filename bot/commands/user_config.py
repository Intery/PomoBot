from settings import UserSettings

from Timer import module


@module.cmd(
    "mytimezone",
    group="Personal Settings",
    short_help=("Timezone for displaying session data. "
                "(Currently {ctx.author_settings.timezone.formatted})"),
    aliases=('mytz',)
)
async def cmd_mytimezone(ctx):
    """
    Usage``:
        {prefix}mytimezone
        {prefix}mytimezone <tz name>
    Setting Description:
        {ctx.author_settings.settings.timezone.long_desc}
    Accepted Values:
        Timezone names must be from the "TZ Database Name" column of \
        [this list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
        For example, `Europe/London`, `Australia/Melbourne`, or `America/New_York`.
    """
    await UserSettings.settings.timezone.command(ctx, ctx.author.id)


@module.cmd(
    "notify",
    group="Personal Settings",
    short_help=("DM notification level. "
                "(Currently {ctx.author_settings.notify_level.formatted})")
)
async def cmd_notify(ctx):
    """
    Usage``:
        {prefix}notify
        {prefix}notify <notify_level>
    Setting Description:
        {ctx.author_settings.settings.notify_level.long_desc}
    Accepted Values:
        {ctx.author_settings.settings.notify_level.accepted_table}
    """
    await UserSettings.settings.notify_level.command(ctx, ctx.author.id)
