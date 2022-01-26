import discord

from utils.lib import prop_tabulate
from settings import TimerSettings, UserInputError
from wards import has_timers

from Timer import module


@module.cmd("timerconfig",
            group="Group Admin",
            short_help="Advanced timer configuration.",
            aliases=("tconfig", "groupconfig"))
@has_timers()
async def cmd_tconfig(ctx):
    """
    Usage:
        `{prefix}tconfig help` (*See short descriptions of all the timer settings.*)
        `{prefix}tconfig [timer name]` (*See the current settings for the given timer.*)
        `{prefix}tconfig [timer name] <setting>` (*See details about the given setting.*)
        `{prefix}tconfig [timer name] <setting> <value>` (*Modify a setting in the given timer.*)
    Description:
        View or set advanced timer settings.

        The `timer name` argument is optional and you will be prompted to select a timer if it is not provided. \
        However, **if the timer name contains a space it must be given in quotes**.
        Partial timer names are also supported.

        *Modifying timer settings requires at least timer admin permissions.*
    Examples``:
        {prefix}tconfig help
        {prefix}tconfig "{ctx.example_group_name}"
        {prefix}tconfig "{ctx.example_group_name}" default_pattern
        {prefix}tconfig "{ctx.example_group_name}" default_pattern 50/10
    """
    # Cache and map setting info
    timers = ctx.timers.get_timers_in(ctx.guild.id)
    timer_names = (timer.name.lower() for timer in timers)
    setting_displaynames = {setting.display_name.lower(): setting for setting in TimerSettings.settings.values()}
    args = ctx.args

    cats = {}  # Timer setting categories
    for setting in TimerSettings.settings.values():
        if setting.category not in cats:
            cats[setting.category] = {}
        cats[setting.category][setting.display_name] = setting

    # Parse
    timer = None
    setting = None
    value = None
    if args.lower() == 'help':
        # No parsing to do
        # Signified by empty timer value
        pass
    elif args:
        splits = args[1:].split('"', maxsplit=1) if args.startswith('"') else args.split(maxsplit=1)
        maybe_name = splits[0]
        if maybe_name.lower() in setting_displaynames and maybe_name.lower() not in timer_names:
            # Assume the provided name is a setting name
            setting = setting_displaynames[maybe_name.lower()]
            value = splits[1] if len(splits) > 1 else None

            # Retrieve the timer from context, or prompt
            sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
            if sub is not None:
                timer = sub.timer
            elif len(timers) == 1:
                timer = timers[0]
            else:
                timer = await ctx.get_timers_matching(
                    '', channel_only=False, info=True,
                    header="Please select a group to configure."
                )
        else:
            timer = await ctx.get_timers_matching(maybe_name, channel_only=False, info=True)
            if not timer:
                return await ctx.error_reply("No groups found matching `{}`.".format(maybe_name))
            if len(splits) > 1 and splits[1]:
                remaining_splits = splits[1].split(maxsplit=1)
                setting = setting_displaynames.get(remaining_splits[0].lower(), None)
                if setting is None:
                    return await ctx.error_reply(
                        "`{}`is not a timer setting!\n"
                        "Use `{}tconfig \"{}\"` to see the available settings.".format(
                            remaining_splits[1], ctx.best_prefix, timer.name
                        )
                    )
                if len(remaining_splits) > 1:
                    value = remaining_splits[1]
    else:
        # Retrieve the timer from context, or prompt
        sub = ctx.timers.get_subscriber(ctx.author.id, ctx.guild.id)
        if sub is not None:
            timer = sub.timer
        elif len(timers) == 1:
            timer = timers[0]
        else:
            timer = await ctx.get_timers_matching(
                '', channel_only=False, info=True,
                header="Please select a group to view."
            )

    # Handle different modes
    if timer is None or setting is None:
        # Display timer configuration or descriptions
        fields = (
            (cat, prop_tabulate(*zip(*(
                (setting.display_name, setting.get(timer.roleid).formatted if timer is not None else setting.desc)
                for name, setting in cat_settings.items()
            ))))
            for cat, cat_settings in cats.items()
        )
        if timer:
            embed = discord.Embed(
                title="Timer configuration for `{}`".format(timer.name),
                description=(
                    "**Tip:** See `{0}help tconfig` for command usage and examples, "
                    "and `{0}tconfig help` to see short descriptions of each setting.".format(ctx.best_prefix)
                )
            )
        else:
            embed = discord.Embed(
                title="Timer configuration options",
                description=(
                    "**Tip:** See `{}help tconfig` for command usage and examples.".format(ctx.best_prefix)
                )
            )
        embed.set_footer(
            text="Use \"{}tconfig timer setting [value]\" to see or modify a setting.".format(
                ctx.best_prefix
            )
        )
        for i, (name, value) in enumerate(fields):
            embed.add_field(name=name, value=value, inline=(bool(timer) and bool((i + 1) % 3)))
        await ctx.reply(embed=embed)
    elif value is None:
        # Display setting information for the given timer and value
        await ctx.reply(embed=setting.get(timer.roleid).embed)
    else:
        # Check the write ward
        if not await setting.write_ward.run(ctx):
            return await ctx.error_reply(setting.write_ward.msg)

        # Write the setting value
        try:
            (await setting.parse(timer.roleid, ctx, value)).write()
        except UserInputError as e:
            await ctx.reply(embed=discord.Embed(
                description="{} {}".format('❌', e.msg),
                color=discord.Colour.red()
            ))
        else:
            await ctx.reply(embed=discord.Embed(description="{} Setting updated!".format('✅')))
