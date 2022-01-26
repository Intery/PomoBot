import discord

from cmdClient import cmd

from utils.lib import prop_tabulate
from utils import interactive  # noqa
from utils.timer_utils import is_timer_admin


# Set the command groups to appear in the help
group_hints = {
    'Guides': "*Short general usage guides for different aspects of PomoBot.*",
    'Timer Usage': "*View and join the server groups.*",
    'Timer Control': "*Setup and control the group timers. May need timer admin permissions!*",
    'Personal Settings': "*Control how I interact with you.*",
    'Registry': "*Server leaderboard and personal study statistics.*",
    'Registry Admin': "*View and modify server session data.*",
    'Saved Patterns': "*Name custom timer patterns for faster setup.*",
    'Group Admin': "*Create, delete, and configure study groups.*",
    'Server Configuration': "*Control how I behave in your server.*",
    'Meta': "*Information about me!*"
}
standard_group_order = (
    ('Timer Usage', 'Timer Control', 'Personal Settings'),
    ('Registry', 'Saved Patterns'),
    ('Meta', 'Guides'),
)
admin_group_order = (
    ('Group Admin', 'Server Configuration', 'Meta', 'Guides'),
    ('Timer Usage', 'Timer Control', 'Personal Settings'),
    ('Registry', 'Registry Admin', 'Saved Patterns'),
)

# Help embed format
title = "PomoBot Usage Manual and Command List"
header = """
Flexible study group system with Pomodoro-style timers!
Supports multiple groups and custom timer patterns.
Join the [support server](https://discord.gg/MnMrQDe) \
or make an issue on the [repository](https://github.com/Intery/PomoBot) if you have any \
questions or issues.

For more detailed information about each command use `{ctx.best_prefix}help <cmd>`.
(For example, see `{ctx.best_prefix}help newgroup` and `{ctx.best_prefix}help start`.)
"""

# Possible tips
tips = {
    'no_groups': "Get started by creating your first group with `{ctx.best_prefix}newgroup`!",
    'non_admin': "Use `{ctx.best_prefix}groups` to see the groups, and `{ctx.best_prefix}join` to join a group!",
    'admin': "Tweak timer behaviour with `{ctx.best_prefix}tconfig`."
}

help_groups = [
    ("Timer", "*View and interact with the guild group timers.*"),
    ("Registry", "*Timer leaderboard and session history.*"),
    ("Configuration", "*Create groups and configure their behaviour.*"),
    ("Misc", "*Other miscellaneous commands.*")
]

# Set the main help string
help_str = ("Flexible study or work group timer using a customisable Pomodoro system!\n"
            "Supports multiple groups and different timer setups.\n"
            "Join the [support server](https://discord.gg/MnMrQDe) "
            "or make an issue on the [repository](https://github.com/Intery/PomoBot) if you have any\n"
            "questions or issues.\n"
            "Use `,phelp cmd` to learn more about a command (e.g. ,phelp join).")

help_title = "CafePomodoro Documentation"


@cmd("help",
     group="Meta",
     short_help="Usage manual and command list.")
async def cmd_help(ctx):
    """
    Usage``:
        {prefix}help [cmdname]
    Description:
        When used with no arguments, displays a list of commands with brief descriptions.
        Otherwise, shows documentation for the provided command.
    Examples:
        {prefix}help
        {prefix}help join
        {prefix}help newgroup
    """
    if ctx.arg_str:
        # Attempt to fetch the command
        command = ctx.client.cmd_names.get(ctx.arg_str.strip(), None)
        if command is None:
            return await ctx.error_reply(
                ("Command `{}` not found!\n"
                 "Write `{}help` to see a list of commands.").format(ctx.args, ctx.best_prefix)
            )

        smart_help = getattr(command, 'smart_help', None)
        if smart_help is not None:
            return await smart_help(ctx)

        help_fields = command.long_help.copy()
        help_map = {field_name: i for i, (field_name, _) in enumerate(help_fields)}

        if not help_map:
            await ctx.reply("No documentation has been written for this command yet!")

        for name, pos in help_map.items():
            if name.endswith("``"):
                # Handle codeline help fields
                help_fields[pos] = (
                    name.strip("`"),
                    "`{}`".format('`\n`'.join(help_fields[pos][1].splitlines()))
                )
            elif name.endswith(":"):
                # Handle property/value help fields
                lines = help_fields[pos][1].splitlines()

                names = []
                values = []
                for line in lines:
                    split = line.split(":", 1)
                    names.append(split[0] if len(split) > 1 else "")
                    values.append(split[-1])

                help_fields[pos] = (
                    name.strip(':'),
                    prop_tabulate(names, values)
                )
            elif name == "Related":
                # Handle the related field
                names = [cmd_name.strip() for cmd_name in help_fields[pos][1].split(',')]
                names.sort(key=len)
                values = [
                    (getattr(ctx.client.cmd_names.get(cmd_name, None), 'short_help', '') or '').format(ctx=ctx)
                    for cmd_name in names
                ]
                help_fields[pos] = (
                    name,
                    prop_tabulate(names, values)
                )

        aliases = getattr(command, 'aliases', [])
        alias_str = "(Aliases `{}`.)".format("`, `".join(aliases)) if aliases else ""

        # Build the embed
        embed = discord.Embed(
            title="`{}` command documentation. {}".format(command.name, alias_str),
            colour=discord.Colour(0x9b59b6)
        )
        for fieldname, fieldvalue in help_fields:
            embed.add_field(
                name=fieldname,
                value=fieldvalue.format(ctx=ctx, prefix=ctx.best_prefix),
                inline=False
            )
        embed.add_field(
            name="Still need help?",
            value="Join our [support server](https://discord.gg/MnMrQDe)!"
        )
        # TODO: Link to online docs

        embed.set_footer(text="[optional] and <required> denote optional and required arguments, respectively.")

        # Post the embed
        await ctx.reply(embed=embed)
    else:
        # Build the command groups
        cmd_groups = {}
        for command in ctx.client.cmds:
            # Get the command group
            group = getattr(command, 'group', "Misc")
            cmd_group = cmd_groups.get(group, [])
            if not cmd_group:
                cmd_groups[group] = cmd_group

            # Add the command name and description to the group
            cmd_group.append((command.name, getattr(command, 'short_help', '')))

        # Turn the command groups into strings
        stringy_cmd_groups = {}
        for group_name, cmd_group in cmd_groups.items():
            cmd_group.sort(key=lambda tup: len(tup[0]))
            stringy_cmd_groups[group_name] = prop_tabulate(*zip(*cmd_group))

        # Now put everything into a bunch of embeds
        if ctx.guild and await is_timer_admin(ctx.author):
            group_order = admin_group_order
            tip = tips['admin']
        else:
            group_order = standard_group_order
            tip = tips['non_admin']

        if ctx.guild and not ctx.timers.get_timers_in(ctx.guild.id):
            tip = tips['no_groups']

        help_embeds = []
        for page_groups in group_order:
            embed = discord.Embed(
                description=header.format(ctx=ctx),
                colour=discord.Colour(0x9b59b6),
                title=title
            )
            for group in page_groups:
                group_hint = group_hints.get(group, '').format(ctx=ctx)
                group_str = stringy_cmd_groups.get(group, None)
                if group_str:
                    embed.add_field(
                        name=group,
                        value="{}\n{}".format(group_hint, group_str).format(ctx=ctx),
                        inline=False
                    )
            help_embeds.append(embed)

        # Add the page numbers
        for i, embed in enumerate(help_embeds):
            embed.set_footer(text="Page {}/{}".format(i+1, len(help_embeds)))

        # Send the embeds
        if help_embeds:
            await ctx.pager(help_embeds, content="**Tip:** {}".format(tip.format(ctx=ctx)))
        else:
            await ctx.reply(embed=discord.Embed(description=help_str, colour=discord.Colour(0x9b59b6)))
