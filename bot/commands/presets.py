from cmdClient import cmd
from cmdClient.checks import in_guild

from Timer import TimerInterface

from wards import timer_admin
from utils import timer_utils, interactive, ctx_addons  # noqa
from utils.lib import paginate_list


def get_presets(ctx):
    """
    Get the valid setup string presets in the current context.
    """
    presets = {}
    if ctx.guild:
        presets.update(ctx.client.config.guilds.get(ctx.guild.id, "timer_presets") or {})  # Guild presets
    presets.update(ctx.client.config.users.get(ctx.author.id, "timer_presets") or {})  # Personal presets

    return presets


def preset_summary(setupstr):
    """
    Return a summary string of stage durations for the given setup string.
    """
    # First compile the preset
    stages = TimerInterface.parse_setupstr(setupstr)
    return "/".join(str(stage.duration) for stage in stages)


@cmd("preset",
     group="Timer",
     desc="Create, view, and remove personal or guild setup string presets.",
     aliases=["addpreset", "presets", "rmpreset"])
async def cmd_preset(ctx):
    """
    Usage``:
        presets
        preset [presetname]
        addpreset [presetname]
        rmpreset <presetname>
    Description:
        Create, view, and remove personal or guild setup string presets.
        See the `setup` command documentation for more information about setup string format.

        Note that the `Timer Admin` role is required to create or remove guild presets.
    Forms::
        preset: Display information about the specified preset.
        presets: List available personal and guild presets.
        addpreset: Create a new preset. Prompts for name if not provided.
        rmpreset: Remove the specified preset.
    Related:
        setup
    """
    presets = get_presets(ctx)
    preset_list = list(presets.items())
    pretty_presets = [
        "{}\t ({})".format(name, preset_summary(preset))
        for name, preset in preset_list
    ]

    if ctx.alias.lower() == "presets":
        # Handle having no presets
        if not pretty_presets:
            return await ctx.embedreply("No presets available! Start creating presets with `addpreset`")

        # Format and return the list
        pages = paginate_list(pretty_presets, title="Available Timer Presets")
        return await ctx.pager(pages)
    elif ctx.alias.lower() == "preset":
        # Prompt for the preset if not given
        if not ctx.arg_str:
            preset = preset_list[await ctx.selector("Please select a preset.", pretty_presets)]
        elif ctx.arg_str not in presets:
            return await ctx.error_reply("Unrecognised preset `{}`.\n"
                                         "Use `presets` to view the available presets.".format(ctx.arg_str))
        else:
            preset = (ctx.arg_str, presets[ctx.arg_str])

        # Build preset info
        preset_info = "Preset `{}` with stages `{}`.\n```{}```".format(preset[0], preset_summary(preset[1]), preset[1])

        # Output info
        await ctx.reply(preset_info)
    elif ctx.alias.lower() == "addpreset":
        # Start by prompting for a name if none was given
        name = ctx.arg_str or await ctx.input("Please enter a name for the new timer preset.")

        # Ragequit on names with bad characters
        if "," in name or ";" in name:
            return await ctx.error_reply("Preset names must not contain `,` or `;`.")

        # Prompt for the setup string
        stages = None
        while stages is None:
            setupstr = await ctx.input(
                "Please enter the timer preset setup string."
            )
            # Handle cancellation
            if setupstr == "c":
                return await ctx.embedreply("Preset creation cancelled by user.")

            # Parse setup string to ensure validity
            stages = TimerInterface.parse_setupstr(setupstr)
            if stages is None:
                await ctx.error_reply("Setup string not understood.")

        # Prompt for whether to add a guild or personal preset
        preset_type = 1  # 0 is Guild preset and 1 is personal preset
        if await in_guild.run(ctx) and await timer_admin.run(ctx):
            preset_type = await ctx.selector(
                "What type of preset would you like to create?",
                ["Guild preset (available to everyone in the guild)",
                 "Personal preset (only available to yourself)"]
            )
        else:
            # Non-admins don't get an option
            preset_type = 1

        # Create the preset
        if preset_type == 0:
            guild_presets = ctx.client.config.guilds.get(ctx.guild.id, "timer_presets") or {}
            if name in guild_presets and not await ctx.ask("Preset `{}` already exists, overwrite?"):
                return
            guild_presets[name] = setupstr
            ctx.client.config.guilds.set(ctx.guild.id, "timer_presets", guild_presets)
            await ctx.embedreply("Guild preset `{}` created.".format(name))
        elif preset_type == 1:
            personal_presets = ctx.client.config.users.get(ctx.author.id, "timer_presets") or {}
            if name in personal_presets and not await ctx.ask("Preset `{}` already exists, overwrite?"):
                return
            personal_presets[name] = setupstr
            ctx.client.config.users.set(ctx.author.id, "timer_presets", personal_presets)
            await ctx.embedreply("Personal preset `{}` created.".format(name))
    elif ctx.alias.lower() == "rmpreset":
        # Handle trying to remove nonexistent preset
        if not ctx.arg_str:
            return await ctx.error_reply("Please provide a preset to remove.")
        if ctx.arg_str not in presets:
            return await ctx.error_reply("Unrecognised preset `{}`.".format(ctx.arg_str))

        personal_presets = ctx.client.config.users.get(ctx.author.id, "timer_presets") or {}
        if ctx.arg_str in personal_presets:
            personal_presets.pop(ctx.arg_str)
            ctx.client.config.users.set(ctx.author.id, "timer_presets", personal_presets)
        else:
            if not await timer_admin.run(ctx):
                return await ctx.error_reply("You need to be a timer admin to remove guild presets.")
            guild_presets = ctx.client.config.guilds.get(ctx.guild.id, "timer_presets") or {}
            guild_presets.pop(ctx.arg_str)
            ctx.client.config.guilds.set(ctx.guild.id, "timer_presets", guild_presets)

        await ctx.embedreply("Preset `{}` has been deleted.".format(ctx.arg_str))
