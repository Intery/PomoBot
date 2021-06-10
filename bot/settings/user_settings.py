import datetime
import Timer

from data import tables
from utils.lib import prop_tabulate, DotDict

from .base import Setting, ObjectSettings, ColumnData, UserInputError
from .setting_types import Timezone, IntegerEnum


class UserSettings(ObjectSettings):
    settings = DotDict()


class UserSetting(ColumnData, Setting):
    _table_interface = tables.users
    _id_column = 'userid'


@UserSettings.attach_setting
class timezone(Timezone, UserSetting):
    attr_name = 'timezone'
    _data_column = 'timezone'

    _default = 'UTC'

    display_name = 'timezone'
    desc = "Timezone for displaying history and session data."
    long_desc = (
        "Timezone used for displaying your historical sessions and study profile."
    )

    @property
    def success_response(self):
        return (
            "Your personal timezone is now {}. "
            "This will apply to your session history and profile, but *not* to the server leaderboard.\n"
            "Your current time is **{}**."
        ).format(self.formatted, datetime.datetime.now(tz=self.value).strftime("%H:%M"))


@UserSettings.attach_setting
class notify_level(IntegerEnum, UserSetting):
    attr_name = 'notify_level'
    _data_column = 'notify_level'

    _enum = Timer.NotifyLevel
    _default = _enum.WARNING

    display_name = 'notify_level'
    desc = 'Control when you receive DM stage notifications.'
    long_desc = (
        "Control when you receive notifications "
        "via DM when a timer you are in changes stage (e.g. from `Work` to `Break`)."
    )

    accepts = "One of the following options."
    accepted_dict = {
        'all': "Receive all stage changes and status updates via DM.",
        'warning': "Only receive a DM for inactivity warnings.",
        'final': "Only receive a DM after being kicked for inactivity.",
        'never': "Never receive status updates via DM."
    }
    accepted_table = prop_tabulate(*zip(*accepted_dict.items()))

    success_responses = {
        _enum.ALL: "You will receive all stage changes and status updates via DM.",
        _enum.WARNING: "You will only receive a DM for inactivity warnings.",
        _enum.FINAL: "You will only receive a DM after being kicked for inactivity.",
        _enum.NEVER: "You will never receive status updates via DM."
    }

    @property
    def embed(self):
        embed = super().embed
        embed.add_field(
            name="Accepted Values",
            value=self.accepted_table
        )
        return embed

    @property
    def success_response(self):
        return (
            "Your notification level is now {}.\n{}"
        ).format(self.formatted, self.success_responses[self.value])

    @classmethod
    async def _parse_userstr(cls, ctx, id, userstr, **kwargs):
        try:
            value = await super()._parse_userstr(ctx, id, userstr, **kwargs)
        except UserInputError:
            raise UserInputError(
                "Unrecognised notification level `{}`. "
                "Please use one of the options below.\n{}".format(userstr, cls.accepted_table)
            ) from None
        return value
