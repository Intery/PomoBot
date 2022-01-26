from enum import IntEnum
from typing import Any, Optional

import pytz
import discord
from cmdClient.Context import Context
from cmdClient.lib import SafeCancellation

from meta import client
import Timer

from .base import UserInputError


class SettingType:
    """
    Abstract class representing a setting type.
    Intended to be used as a mixin for a Setting,
    with the provided methods implementing converter methods for the setting.
    """
    accepts: str = None  # User readable description of the acceptable values

    # Raw converters
    @classmethod
    def _data_from_value(cls, id: int, value, **kwargs):
        """
        Convert a high-level setting value to internal data.
        """
        raise NotImplementedError

    @classmethod
    def _data_to_value(cls, id: int, data: Any, **kwargs):
        """
        Convert internal data to high-level setting value.
        """
        raise NotImplementedError

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        """
        Parse user provided input into internal data.
        """
        raise NotImplementedError

    @classmethod
    def _format_data(cls, id: int, data: Any, **kwargs):
        """
        Convert internal data into a formatted user-readable string.
        """
        raise NotImplementedError


class Boolean(SettingType):
    """
    Boolean type, supporting truthy and falsey user input.
    Configurable to change truthy and falsey values, and the output map.

    Types:
        data: Optional[bool]
            The stored boolean value.
        value: Optional[bool]
            The stored boolean value.
    """
    accepts = "Yes/No, On/Off, True/False, Enabled/Disabled"

    # Values that are accepted as truthy and falsey by the parser
    _truthy = {"yes", "true", "on", "enable", "enabled"}
    _falsey = {"no", "false", "off", "disable", "disabled"}

    # The user-friendly output strings to use for each value
    _outputs = {True: "On", False: "Off", None: "Not Set"}

    @classmethod
    def _data_from_value(cls, id: int, value: Optional[bool], **kwargs):
        """
        Both data and value are of type Optional[bool].
        Directly return the provided value as data.
        """
        return value

    @classmethod
    def _data_to_value(cls, id: int, data: Optional[bool], **kwargs):
        """
        Both data and value are of type Optional[bool].
        Directly return the internal data as the value.
        """
        return data

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        """
        Looks up the provided string in the truthy and falsey tables.
        """
        _userstr = userstr.lower()
        if _userstr == "none":
            return None
        if _userstr in cls._truthy:
            return True
        elif _userstr in cls._falsey:
            return False
        else:
            raise UserInputError("Unknown boolean type `{}`".format(userstr))

    @classmethod
    def _format_data(cls, id: int, data: bool, **kwargs):
        """
        Pass the provided value through the outputs map.
        """
        return cls._outputs[data]


class Integer(SettingType):
    """
    Integer type. Storing any integer.

    Types:
        data: Optional[int]
            The stored integer value.
        value: Optional[int]
            The stored integer value.
    """
    accepts = "An integer."

    # Set limits on the possible integers
    _min = -4096
    _max = 4096

    @classmethod
    def _data_from_value(cls, id: int, value: Optional[bool], **kwargs):
        """
        Both data and value are of type Optional[int].
        Directly return the provided value as data.
        """
        return value

    @classmethod
    def _data_to_value(cls, id: int, data: Optional[bool], **kwargs):
        """
        Both data and value are of type Optional[int].
        Directly return the internal data as the value.
        """
        return data

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        """
        Relies on integer casting to convert the user string
        """
        if userstr.lower() == "none":
            return None

        try:
            num = int(userstr)
        except Exception:
            raise UserInputError("Couldn't parse provided integer.") from None

        if num > cls._max:
            raise UserInputError("Provided integer was too large!")
        elif num < cls._min:
            raise UserInputError("Provided integer was too small!")

        return num

    @classmethod
    def _format_data(cls, id: int, data: Optional[int], **kwargs):
        """
        Return the string version of the data.
        """
        if data is None:
            return None
        else:
            return str(data)


class String(SettingType):
    """
    String type, storing arbitrary text.
    Configurable to limit text length and restrict input options.

    Types:
        data: Optional[str]
            The stored string.
        value: Optional[str]
            The stored string.
    """
    accepts = "Any text"

    # Maximum length of string to accept
    _maxlen: int = None

    # Set of input options to accept
    _options: set = None

    # Whether to quote the string as code
    _quote: bool = True

    @classmethod
    def _data_from_value(cls, id: int, value: Optional[str], **kwargs):
        """
        Return the provided value string as the data string.
        """
        return value

    @classmethod
    def _data_to_value(cls, id: int, data: Optional[str], **kwargs):
        """
        Return the provided data string as the value string.
        """
        return data

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        """
        Check that the user-entered string is of the correct length.
        Accept "None" to unset.
        """
        if userstr.lower() == "none":
            # Unsetting case
            return None
        elif cls._maxlen is not None and len(userstr) > cls._maxlen:
            raise UserInputError("Provided string was too long! Maximum length is `{}`".format(cls._maxlen))
        elif cls._options is not None and not userstr.lower() in cls._options:
            raise UserInputError("Invalid option! Valid options are `{}`".format("`, `".join(cls._options)))
        else:
            return userstr

    @classmethod
    def _format_data(cls, id: int, data: str, **kwargs):
        """
        Wrap the string in backtics for formatting.
        Handle the special case where the string is empty.
        """
        if data:
            return "`{}`".format(data) if cls._quote else str(data)
        else:
            return None


class Channel(SettingType):
    """
    Channel type, storing a single `discord.Channel`.

    Types:
        data: Optional[int]
            The id of the stored Channel.
        value: Optional[discord.abc.GuildChannel]
            The stored Channel.
    """
    accepts = "Channel mention/id/name, or 'None' to unset"

    # Type of channel, if any
    _chan_type: discord.ChannelType = None

    @classmethod
    def _data_from_value(cls, id: int, value: Optional[discord.abc.GuildChannel], **kwargs):
        """
        Returns the channel id.
        """
        return value.id if value is not None else None

    @classmethod
    def _data_to_value(cls, id: int, data: Optional[int], **kwargs):
        """
        Uses the client to look up the channel id.
        Returns the Channel if found, otherwise None.
        """
        # Always passthrough None
        if data is None:
            return None

        return client.get_channel(data)

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        """
        Pass to the channel seeker utility to find the requested channel.
        Handle `0` and variants of `None` to unset.
        """
        if userstr.lower() in ('0', 'none'):
            return None
        else:
            channel = await ctx.find_channel(userstr, interactive=True, chan_type=cls._chan_type)
            if channel is None:
                raise SafeCancellation
            else:
                return channel.id

    @classmethod
    def _format_data(cls, id: int, data: Optional[int], **kwargs):
        """
        Retrieve an artificially created channel mention.
        If the channel does not exist, this will show up as invalid-channel.
        """
        if data is None:
            return None
        else:
            return "<#{}>".format(data)


class Role(SettingType):
    """
    Role type, storing a single `discord.Role`.
    Configurably allows returning roles which don't exist or are not seen by the client
    as `discord.Object`.

    Settings may override `get_guildid` if the setting object `id` is not the guildid.

    Types:
        data: Optional[int]
            The id of the stored Role.
        value: Optional[Union[discord.Role, discord.Object]]
            The stored Role, or, if the role wasn't found and `_strict` is not set,
            a discord Object with the role id set.
    """
    accepts = "Role mention/id/name, or 'None' to unset"

    # Whether to disallow returning roles which don't exist as `discord.Object`s
    _strict = True

    @classmethod
    def _data_from_value(cls, id: int, value: Optional[discord.Role], **kwargs):
        """
        Returns the role id.
        """
        return value.id if value is not None else None

    @classmethod
    def _data_to_value(cls, id: int, data: Optional[int], **kwargs):
        """
        Uses the client to look up the guild and role id.
        Returns the role if found, otherwise returns a `discord.Object` with the id set,
        depending on the `_strict` setting.
        """
        # Always passthrough None
        if data is None:
            return None

        # Fetch guildid
        guildid = cls._get_guildid(id, **kwargs)

        # Search for the role
        role = None
        guild = client.get_guild(guildid)
        if guild is not None:
            role = guild.get_role(data)

        if role is not None:
            return role
        elif not cls._strict:
            return discord.Object(id=data)
        else:
            return None

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        """
        Pass to the role seeker utility to find the requested role.
        Handle `0` and variants of `None` to unset.
        """
        if userstr.lower() in ('0', 'none'):
            return None
        else:
            role = await ctx.find_role(userstr, create=False, interactive=True)
            if role is None:
                raise SafeCancellation
            else:
                return role.id

    @classmethod
    def _format_data(cls, id: int, data: Optional[int], **kwargs):
        """
        Retrieve the role mention if found, otherwise the role id or None depending on `_strict`.
        """
        role = cls._data_to_value(id, data, **kwargs)
        if role is None:
            return "Not Set"
        elif isinstance(role, discord.Role):
            return role.mention
        else:
            return "`{}`".format(role.id)

    @classmethod
    def _get_guildid(cls, id: int, **kwargs):
        """
        Fetch the current guildid.
        Assumes that the guilid is either passed as a kwarg or is the object id.
        Should be overriden in other cases.
        """
        return kwargs.get('guildid', id)


class Emoji(SettingType):
    """
    Emoji type. Stores both custom and unicode emojis.
    """
    accepts = "Emoji, either built in or custom. Use 'None' to unset."

    @staticmethod
    def _parse_emoji(emojistr):
        """
        Converts a provided string into a PartialEmoji.
        If the string is badly formatted, returns None.
        """
        if ":" in emojistr:
            emojistr = emojistr.strip('<>')
            splits = emojistr.split(":")
            if len(splits) == 3:
                animated, name, id = splits
                animated = bool(animated)
                return discord.PartialEmoji(name, animated=animated, id=int(id))
        else:
            # TODO: Check whether this is a valid emoji
            return discord.PartialEmoji(emojistr)

    @classmethod
    def _data_from_value(cls, id: int, value: Optional[discord.PartialEmoji], **kwargs):
        """
        Both data and value are of type Optional[discord.PartialEmoji].
        Directly return the provided value as data.
        """
        return value

    @classmethod
    def _data_to_value(cls, id: int, data: Optional[discord.PartialEmoji], **kwargs):
        """
        Both data and value are of type Optional[discord.PartialEmoji].
        Directly return the internal data as the value.
        """
        return data

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        """
        Pass to the emoji string parser to get the emoji.
        Handle `0` and variants of `None` to unset.
        """
        if userstr.lower() in ('0', 'none'):
            return None
        else:
            return cls._parse_emoji(userstr)

    @classmethod
    def _format_data(cls, id: int, data: Optional[discord.PartialEmoji], **kwargs):
        """
        Return a string form of the partial emoji, which generally displays the emoji.
        """
        if data is None:
            return None
        else:
            return str(data)


class PatternType(SettingType):
    """
    Pattern type. Stores a valid Timer Pattern.

    Types:
        data: Optional[int]
            The stored patternid
        value: Optional[Timer.Pattern]
            The Timer.Pattern stored
    """
    accepts = "A valid timer pattern."

    @classmethod
    def _data_from_value(cls, id: int, value, **kwargs):
        if value is not None:
            return value.row.patternid

    @classmethod
    def _data_to_value(cls, id: int, data: Optional[int], **kwargs):
        return Timer.Pattern.get(data) if data is not None else None

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        if userstr.lower() == "none":
            return None

        pattern = Timer.Pattern.from_userstr(
            userstr,
            userid=ctx.author.id,
            guildid=ctx.guild.id if ctx.guild else None,
            timerid=id
        )

        return pattern.row.patternid

    @classmethod
    def _format_data(cls, id: int, data: Optional[int], brief=True, **kwargs):
        """
        Return the string version of the data.
        """
        if data is not None:
            return cls._data_to_value(id, data, **kwargs).display(brief=brief)


class Timezone(SettingType):
    """
    Timezone type, storing a valid timezone string.

    Types:
        data: Optional[str]
            The string representing the timezone in POSIX format.
        value: Optional[timezone]
            The pytz timezone.
    """
    accepts = (
        "A timezone name from [this list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) "
        "(e.g. `Europe/London`)."
    )

    @classmethod
    def _data_from_value(cls, id: int, value: Optional[str], **kwargs):
        """
        Return the provided value string as the data string.
        """
        if value is not None:
            return str(value)

    @classmethod
    def _data_to_value(cls, id: int, data: Optional[str], **kwargs):
        """
        Return the provided data string as the value string.
        """
        if data is not None:
            return pytz.timezone(data)

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        """
        Check that the user-entered string is of the correct length.
        Accept "None" to unset.
        """
        if userstr.lower() == "none":
            # Unsetting case
            return None
        try:
            timezone = pytz.timezone(userstr)
        except pytz.exceptions.UnknownTimeZoneError:
            timezones = [tz for tz in pytz.all_timezones if userstr.lower() in tz.lower()]
            if len(timezones) == 1:
                timezone = timezones[0]
            elif timezones:
                result = await ctx.selector(
                    "Multiple matching timezones found, please select one.",
                    timezones
                )
                timezone = timezones[result]
            else:
                raise UserInputError(
                    "Unknown timezone `{}`. "
                    "Please provide a TZ name from "
                    "[this list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)".format(userstr)
                ) from None

        return str(timezone)

    @classmethod
    def _format_data(cls, id: int, data: str, **kwargs):
        """
        Wrap the string in backtics for formatting.
        Handle the special case where the string is empty.
        """
        if data:
            return "`{}`".format(data)
        else:
            return 'Not Set'


class IntegerEnum(SettingType):
    """
    Integer Enum type, accepting limited strings, storing an integer, and returning an IntEnum value

    Types:
        data: Optional[int]
            The stored integer.
        value: Optional[Any]
            The corresponding Enum member
    """
    accepts = "A valid option."

    # Enum to use for mapping values
    _enum: IntEnum = None

    # Custom map to format the value. If None, uses the enum names.
    _output_map = None

    @classmethod
    def _data_from_value(cls, id: int, value: ..., **kwargs):
        """
        Return the value corresponding to the enum member
        """
        if value is not None:
            return value.value

    @classmethod
    def _data_to_value(cls, id: int, data: ..., **kwargs):
        """
        Return the enum member corresponding to the provided integer
        """
        if data is not None:
            return cls._enum(data)

    @classmethod
    async def _parse_userstr(cls, ctx: Context, id: int, userstr: str, **kwargs):
        """
        Find the corresponding enum member's value to the provided user input.
        Accept "None" to unset.
        """
        userstr = userstr.lower()

        options = {name.lower(): mem.value for name, mem in cls._enum.__members__.items()}

        if userstr == "none":
            # Unsetting case
            return None
        elif userstr not in options:
            raise UserInputError("Invalid option!")
        else:
            return options[userstr]

    @classmethod
    def _format_data(cls, id: int, data: int, **kwargs):
        """
        Format the data using either the `_enum` or the provided output map.
        """
        if data is not None:
            value = cls._enum(data)
            if cls._output_map:
                return cls._output_map[value]
            else:
                return "`{}`".format(value.name)
