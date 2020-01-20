from cmdClient import Context
from cmdClient.lib import InvalidContext, UserCancelled, ResponseTimedOut
from . import interactive


@Context.util
async def find_role(ctx, userstr, interactive=False, collection=None):
    """
    Find a guild role given a partial matching string,
    allowing custom role collections and several behavioural switches.

    Parameters
    ----------
    userstr: str
        String obtained from a user, expected to partially match a role in the collection.
        The string will be tested against both the id and the name of the role.
    interactive: bool
        Whether to offer the user a list of roles to choose from,
        or pick the first matching role.
    collection: List(discord.Role)
        Collection of roles to search amongst.
        If none, uses the guild role list.

    Returns
    -------
    discord.Role:
        If a valid role is found.
    None:
        If no valid role has been found.

    Raises
    ------
    cmdClient.lib.UserCancelled:
        If the user cancels interactive role selection.
    cmdClient.lib.ResponseTimedOut:
        If the user fails to respond to interactive role selection within `60` seconds`
    """
    # Handle invalid situations and input
    if not ctx.guild:
        raise InvalidContext("Attempt to use find_role outside of a guild.")

    if userstr == "":
        raise ValueError("User string passed to find_role was empty.")

    # Create the collection to search from args or guild roles
    collection = collection if collection else ctx.guild.roles

    # If the unser input was a number or possible role mention, get it out
    roleid = userstr.strip('<#@&!>')
    roleid = int(roleid) if roleid.isdigit() else None
    searchstr = userstr.lower()

    # Find the role
    role = None

    # Check method to determine whether a role matches
    def check(role):
        return (role.id == roleid) or (searchstr in role.name.lower())

    # Get list of matching roles
    roles = list(filter(check, collection))

    if len(roles) == 0:
        # Nope
        role = None
    elif len(roles) == 1:
        # Select our lucky winner
        role = roles[0]
    else:
        # We have multiple matching roles!
        if interactive:
            # Interactive prompt with the list of roles
            role_names = [role.name for role in roles]

            try:
                selected = await ctx.selector(
                    "`{}` roles found matching `{}`!".format(len(roles), userstr),
                    role_names,
                    timeout=60
                )
            except UserCancelled:
                raise UserCancelled("User cancelled role selection.") from None
            except ResponseTimedOut:
                raise ResponseTimedOut("Role selection timed out.") from None

            role = roles[selected]
        else:
            # Just select the first one
            role = roles[0]

    if role is None:
        await ctx.error_reply("Couldn't find a role matching `{}`!".format(userstr))

    return role


@Context.util
async def find_channel(ctx, userstr, interactive=False, collection=None, chan_type=None):
    """
    Find a guild channel given a partial matching string,
    allowing custom channel collections and several behavioural switches.

    Parameters
    ----------
    userstr: str
        String obtained from a user, expected to partially match a channel in the collection.
        The string will be tested against both the id and the name of the channel.
    interactive: bool
        Whether to offer the user a list of channels to choose from,
        or pick the first matching channel.
    collection: List(discord.Channel)
        Collection of channels to search amongst.
        If none, uses the full guild channel list.
    chan_type: discord.ChannelType
        Type of channel to restrict the collection to.

    Returns
    -------
    discord.Channel:
        If a valid channel is found.
    None:
        If no valid channel has been found.

    Raises
    ------
    cmdClient.lib.UserCancelled:
        If the user cancels interactive channel selection.
    cmdClient.lib.ResponseTimedOut:
        If the user fails to respond to interactive channel selection within `60` seconds`
    """
    # Handle invalid situations and input
    if not ctx.guild:
        raise InvalidContext("Attempt to use find_channel outside of a guild.")

    if userstr == "":
        raise ValueError("User string passed to find_channel was empty.")

    # Create the collection to search from args or guild channels
    collection = collection if collection else ctx.guild.channels
    if chan_type is not None:
        collection = [chan for chan in collection if chan.type == chan_type]

    # If the user input was a number or possible channel mention, extract it
    chanid = userstr.strip('<#@&!>')
    chanid = int(chanid) if chanid.isdigit() else None
    searchstr = userstr.lower()

    # Find the channel
    chan = None

    # Check method to determine whether a channel matches
    def check(chan):
        return (chan.id == chanid) or (searchstr in chan.name.lower())

    # Get list of matching roles
    channels = list(filter(check, collection))

    if len(channels) == 0:
        # Nope
        chan = None
    elif len(channels) == 1:
        # Select our lucky winner
        chan = channels[0]
    else:
        # We have multiple matching channels!
        if interactive:
            # Interactive prompt with the list of channels
            chan_names = [chan.name for chan in channels]

            try:
                selected = await ctx.selector(
                    "`{}` channels found matching `{}`!".format(len(channels), userstr),
                    chan_names,
                    timeout=60
                )
            except UserCancelled:
                raise UserCancelled("User cancelled channel selection.") from None
            except ResponseTimedOut:
                raise ResponseTimedOut("Channel selection timed out.") from None

            chan = channels[selected]
        else:
            # Just select the first one
            chan = channels[0]

    if chan is None:
        await ctx.error_reply("Couldn't find a channel matching `{}`!".format(userstr))

    return chan
