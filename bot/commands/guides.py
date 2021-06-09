import discord

from cmdClient import cmd


def guide(name, **kwargs):
    def wrapped(func):
        # Create command
        command = cmd(name, group="Guides", **kwargs)(func)
        command.smart_help = func
        return command
    return wrapped


@guide("patterns",
       short_help="How to change the timer work/break patterns.")
async def guide_patterns(ctx):
    pattern_gif = discord.File('assets/guide-gifs/pattern-guide.gif')
    embed = discord.Embed(
        title="Guide to changing your timer pattern",
        description="""
        A *timer pattern* is the sequence of stages the timer follows,\
        for example *50 minutes Work* followed by *10 minutes Break*.
        Each timer's pattern is easily customisable, and patterns may be saved for simpler timer setup.

        The pattern is usually given as the stage durations separated by `/`.\
        For example, `50/10` represents 50 minutes work followed by 10 minutes break.\
        See the extended format below for finer control over the pattern stages.

        To modify a timer's pattern, use the `start` or `setup` commands.\
        For example, use `{prefix}start 50/10` to start your timer with a `50/10` pattern.\
        `setup` will stop the timer and change the pattern, while `start` will also restart the timer.

        Patterns always repeat forever, so in the above example, \
        after the break is finished the 50 minute work stage will start again.

        *See the gif below and `,phelp start` for more pattern usage examples.*
        """.format(prefix=ctx.best_prefix)
    ).add_field(
        name="Extended Format",
        value="""
        The *stage names* and *stage messages* of a pattern may be customised using the *extended pattern format*.
        Stages are separated by `;` instead of `/`, and each stage has the form `name, duration, message`, \
        with the `message` being optional.\
        A `*` may be added after the duration to mark a stage as a "work" stage (visible in the study time summaries).
        For example a custom `50/10` pattern could be given as \
        ```Study🔥, 50*, Good luck!; Break🌝, 10, Have a rest.```
        """,
        inline=False
    ).add_field(
        name="Saving patterns",
        value="""
        Patterns may also be *saved* and given names using the `savepattern` command. \
        Simply type `{prefix}savepattern pattern` (replacing `pattern` with the desired pattern), \
        and enter the name when prompted. \
        The saved pattern name may then be used wherever a pattern is required, \
        including  in the `start` and `setup` commands.
        """.format(prefix=ctx.best_prefix),
        inline=False
    ).set_image(
        url='attachment://pattern-guide.gif'
    )

    await ctx.reply(embed=embed, file=pattern_gif)


@guide("settingup",
       short_help="Setting up {ctx.client.user.name} in your server.")
async def guide_setting_up(ctx):
    await ctx.reply("Setup guide coming soon!")


@guide("gettingstarted",
       short_help="Getting started with using {ctx.client.user.name}.")
async def guide_getting_started(ctx):
    await ctx.reply("Getting started guide coming soon!")
