from cmdClient.checks import in_guild

from settings import GuildSettings

from Timer import module


@module.cmd(
    "globalgroups",
    group="Server Configuration",
    short_help=("Whether groups may be joined outside their channel. "
                "(`{ctx.guild_settings.globalgroups.formatted}`)")
)
@in_guild()
async def cmd_globalgroups(ctx):
    """
    Usage``:
        {prefix}globalgroups
        {prefix}globalgroups on | off
    Setting Description:
        {ctx.guild_settings.settings.globalgroups.long_desc}
    """
    await GuildSettings.settings.globalgroups.command(ctx, ctx.guild.id)


@module.cmd(
    "prefix",
    group="Server Configuration",
    short_help=("The server command prefix. "
                "(Currently `{ctx.guild_settings.prefix.formatted}`)")
)
@in_guild()
async def cmd_prefix(ctx):
    """
    Usage``:
        {prefix}prefix
        {prefix}prefix <new-prefix>
    Setting Description:
        {ctx.guild_settings.settings.prefix.long_desc}
    """
    await GuildSettings.settings.prefix.command(ctx, ctx.guild.id)


@module.cmd(
    "timeradmin",
    group="Server Configuration",
    short_help=("The role required for timer admin actions. "
                "({ctx.guild_settings.timer_admin_role.formatted})")
)
@in_guild()
async def cmd_timeradmin(ctx):
    """
    Usage``:
        {prefix}timeradmin
        {prefix}timeradmin <role>
    Setting Description:
        {ctx.guild_settings.settings.timer_admin_role.long_desc}
    Accepted Values:
        Roles maybe given as their name, id, or partial name.

        *Modifying the `timeradmin` role requires the `administrator` server permission.*
    """
    await GuildSettings.settings.timer_admin_role.command(ctx, ctx.guild.id)


@module.cmd(
    "timezone",
    group="Server Configuration",
    short_help=("The server leaderboard timezone. "
                "({ctx.guild_settings.timezone.formatted})")
)
@in_guild()
async def cmd_timezone(ctx):
    """
    Usage``:
        {prefix}timezone
        {prefix}timezone <tz name>
    Setting Description:
        {ctx.guild_settings.settings.timezone.long_desc}
    Accepted Values:
        Timezone names must be from the "TZ Database Name" column of \
        [this list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
        For example, `Europe/London`, `Australia/Melbourne`, or `America/New_York`.
    """
    await GuildSettings.settings.timezone.command(ctx, ctx.guild.id)


@module.cmd(
    "studyrole",
    group="Server Configuration",
    short_help=("The global study role. "
                "({ctx.guild_settings.studyrole.formatted})")
)
@in_guild()
async def cmd_studyrole(ctx):
    """
    Usage``:
        {prefix}studyrole
        {prefix}studyrole <role>
    Setting Description:
        {ctx.guild_settings.settings.studyrole.long_desc}
    Accepted Values:
        Roles maybe given as their name, id, or partial name.
    """
    await GuildSettings.settings.studyrole.command(ctx, ctx.guild.id)


"""
@module.cmd("config",
            group="Server Configuration",
            short_help="View and modify server configuration.")
@in_guild()
async def cmd_config(ctx):
    # Cache and map some info for faster access
    setting_displaynames = {setting.display_name.lower(): setting for setting in GuildSettings.settings.values()}

    if not ctx.args or ctx.args.lower() == 'help':
        # Display the current configuration, with either values or descriptions
        props = {
            setting.display_name: setting.get(ctx.guild.id).formatted if not ctx.args else setting.desc
            for setting in GuildSettings.settings.values()
        }
        table = prop_tabulate(*zip(*props.items()))
        embed = discord.Embed(
            description="{table}\n\nUse `{prefix}config <name>` to view more information.".format(
                prefix=ctx.best_prefix,
                table=table
            ),
            title="Server settings"
        )
        await ctx.reply(embed=embed)
    else:
        # Some args were given
        parts = ctx.args.split(maxsplit=1)

        name = parts[0]
        setting = setting_displaynames.get(name.lower(), None)
        if setting is None:
            return await ctx.error_reply(
                "Server setting `{}` doesn't exist! Use `{}config` to see all server settings".format(
                    name, ctx.best_prefix
                )
            )

        if len(parts) == 1:
            # config <setting>
            # View config embed for provided setting
            await ctx.reply(embed=setting.get(ctx.guild.id).embed)
        else:
            # config <setting> <value>
            # Check the write ward
            if not await setting.write_ward.run(ctx):
                await ctx.error_reply(setting.msg)

            # Attempt to set config setting
            try:
                (await setting.parse(ctx.guild.id, ctx, parts[1])).write()
            except UserInputError as e:
                await ctx.reply(embed=discord.Embed(
                    description="{} {}".format('❌', e.msg),
                    Colour=discord.Colour.red()
                ))
            else:
                await ctx.reply(embed=discord.Embed(
                    description="{} Setting updated!".format('✅'),
                    Colour=discord.Colour.green()
                ))
"""
