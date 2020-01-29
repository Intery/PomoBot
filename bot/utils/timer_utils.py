from cmdClient import Context
from cmdClient.lib import UserCancelled, ResponseTimedOut


@Context.util
async def get_timers_matching(ctx, name_str, channel_only=True, info=False):
    """
    Interactively get a guild timer matching the given string.

    Parameters
    ----------
    name_str: str
        Name or partial name of a group timer in the current guild or channel.
    channel_only: bool
        Whether to match against the groups in the current channel or those in the whole guild.
    info: bool
        Whether to display some summary info about the timer in the selector.

    Returns: Timer

    Raises
    ------
    cmdClient.lib.UserCancelled:
        Raised if the user manually cancels the selection.
    cmdClient.lib.ResponseTimedOut:
        Raised if the user fails to respond to the selector within `120` seconds.
    """
    # Get the full timer list
    if channel_only:
        timers = ctx.client.interface.get_channel_timers(ctx.ch.id)
    else:
        timers = ctx.client.interface.get_guild_timers(ctx.guild.id)

    # If there are no timers, quit early
    if not timers:
        return None

    # Build a list of matching timers
    name_str = name_str.strip()
    timers = [timer for timer in timers if name_str.lower() in timer.name.lower()]

    if len(timers) == 0:
        return None
    elif len(timers) == 1:
        return timers[0]
    else:
        if info:
            select_from = [timer.oneline_summary() for timer in timers]
        else:
            select_from = [timer.name for timer in timers]

        try:
            selected = await ctx.selector("Multiple matching groups found, please select one.", select_from)
        except ResponseTimedOut:
            raise ResponseTimedOut("Group selection timed out.") from None
        except UserCancelled:
            raise UserCancelled("User cancelled group selection.") from None

        return timers[selected]
