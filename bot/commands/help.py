import discord

from cmdClient import cmd

from utils.lib import prop_tabulate


# Set the command groups to appear in the help
help_groups = [
    ("Timer Control", "*Commands to interact with your timer, or the ones in the current channel.*"),
    ("Registry", "*Guild timer leaderboard and session history.*"),
    ("Timer Config", "*Create timers and configure their behaviour.*"),
    ("Misc", "*Other miscellaneous commands.*")
]

# Set the main help string
help_str = ("Flexible study group timer using a customisable Pomodoro system!\n"
            "Supports multiple groups and different timer setups.\n"
            "Use the `guide` command to see a quick usage guide.")

help_title = "CafePomodoro Documentation"


@cmd("help",
     desc="Display information about commands.")
async def cmd_help(ctx):
    """
    Usage:
        help [cmdname]
    Description:
        When used with no arguments, displays a list of commands with brief descriptions.
        Otherwise, shows documentation for the provided command.
    Examples:
        help
        help help
    """
    if ctx.arg_str:
        # Attempt to fetch the command
        command = ctx.client.cmd_cache.get(ctx.arg_str.strip(), None)
        if command is None:
            return await ctx.error_reply(
                ("Command `{}` not found!\n"
                 "Use the `help` command without arguments to see a list of commands.").format(ctx.arg_str)
            )

        help_fields = command.long_help
        help_map = {field_name: i for i, (field_name, _) in enumerate(help_fields)}

        if not help_map:
            await ctx.reply("No documentation has been written for this command yet!")

        usage_index = help_map.get("Usage", None)
        if usage_index is not None:
            help_fields[usage_index] = ("Usage", "`{}`".format('`\n`'.join(help_fields[usage_index][1].splitlines())))

        examples_index = help_map.get("Examples", None)
        if examples_index is not None:
            help_fields[examples_index] = (
                "Examples",
                "`{}`".format('`\n`'.join(help_fields[examples_index][1].splitlines()))
            )

        aliases = getattr(command, 'aliases', [])
        alias_str = "(aliases `{}`)".format("`, `".join(aliases)) if aliases else ""

        # Build the embed
        embed = discord.Embed(
            title="Documentation for command `{}` {}".format(command.name, alias_str),
            colour=discord.Colour(0x9b59b6)
        )
        for fieldname, fieldvalue in help_fields:
            embed.add_field(name=fieldname, value=fieldvalue, inline=False)

        embed.set_footer(text="[optional] denotes an optional argument and <required> a required one")

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
            cmd_group.append((command.name, getattr(command, 'desc', "")))

        # Turn the command groups into strings
        stringy_cmd_groups = {}
        for group_name, cmd_group in cmd_groups.items():
            cmd_group.sort(key=lambda tup: len(tup[0]))
            stringy_cmd_groups[group_name] = prop_tabulate(*zip(*cmd_group))

        # Now put everything into a bunch of embeds
        help_embeds = []
        active_fields = []
        for group_name, group_desc in help_groups:
            group_str = stringy_cmd_groups.get(group_name, None)
            if group_str is None:
                continue

            active_fields.append((group_name, group_desc + '\n' + group_str))

            if group_name == help_groups[-1][0] or sum([len(field.splitlines()) for _, field in active_fields]) > 10:
                # Roll a new embed
                embed = discord.Embed(description=help_str, colour=discord.Colour(0x9b59b6), title=help_title)

                # Add the active fields
                for name, field in active_fields:
                    embed.add_field(name=name, value=field, inline=False)

                help_embeds.append(embed)

                # Clear the active fields
                active_fields = []

        # Add the page numbers
        for i, embed in enumerate(help_embeds):
            embed.set_footer(text="Page {}/{}".format(i+1, len(help_embeds)))

        # Send the embeds
        if help_embeds:
            await ctx.pager(help_embeds)
        else:
            await ctx.reply(embed=discord.Embed(description=help_str, colour=discord.Colour(0x9b59b6)))
