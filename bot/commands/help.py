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
async def cmd_addgrp(ctx):
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
        pass
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

            if group_name == help_groups[-1][0] or sum([len(field.splitlines()) for _, field in active_fields]) > 20:
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
