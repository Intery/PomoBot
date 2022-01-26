import datetime

from data import tables
from wards import timer_admin, guild_admin
from meta import client
from utils.lib import DotDict

from .base import Setting, ObjectSettings, ColumnData, UserInputError
from .setting_types import Role, Boolean, String, Timezone


class GuildSettings(ObjectSettings):
    settings = DotDict()


class GuildSetting(ColumnData, Setting):
    _table_interface = tables.guilds
    _id_column = 'guildid'

    write_ward = timer_admin


@GuildSettings.attach_setting
class timer_admin_role(Role, GuildSetting):
    attr_name = 'timer_admin_role'
    _data_column = 'timer_admin_roleid'

    write_ward = guild_admin

    display_name = 'timer_admin_role'
    desc = 'Role required to create and configure timers.'
    long_desc = (
        "Role required to create and configure timers.\n"
        "Having this role allows members to use most configuration commands "
        "such as those under `Group Admin`, `Server Configuration`, "
        "and `Registry Admin`.\n"
        "Having the administrator server permission also allows use of these commands, "
        "and some commands, such as `timeradmin` itself, require this permission instead.\n"
        "(Required permissions for commands are listed in their `help` pages.)"
    )

    @property
    def success_response(self):
        return "The timer admin role is now {}.".format(self.formatted)


@GuildSettings.attach_setting
class show_tips(Boolean, GuildSetting):
    attr_name = 'show_tips'
    _data_column = 'show_tips'

    _default = True

    display_name = 'display_tips'
    desc = 'Display usage tips for setting up and using the bot.'
    long_desc = (
        "Display usage tips and hints on the output of various commands."
    )

    @property
    def success_response(self):
        return "Usage tips are now {}.".format("Enabled" if self.value else "Disabled")


@GuildSettings.attach_setting
class globalgroups(Boolean, GuildSetting):
    attr_name = 'globalgroups'
    _data_column = 'globalgroups'

    _default = False

    display_name = 'globalgroups'
    desc = 'Whether timers may be joined from any channel.'
    long_desc = (
        "By default, groups may only be joined from the text channel they are bound to. "
        "This setting allows members to join study groups from any channel."
    )

    @property
    def success_response(self):
        if self.value:
            return "Groups may now be joined from any channel."
        else:
            return "Groups may now only be joined from the text channel they are bound to."


@GuildSettings.attach_setting
class prefix(String, GuildSetting):
    attr_name = 'prefix'
    _data_column = 'prefix'

    _default = client.prefix

    write_ward = guild_admin

    display_name = 'prefix'
    desc = 'The bot command prefix.'
    long_desc = (
        "The command prefix required to run any command.\n"
        "My mention will also always function as a prefix."
    )

    @property
    def success_response(self):
        return "The command prefix is now `{0}`. (E.g. `{0}help`.)".format(self.value)


@GuildSettings.attach_setting
class timezone(Timezone, GuildSetting):
    attr_name = 'timezone'
    _data_column = 'timezone'

    _default = 'UTC'

    write_ward = guild_admin

    display_name = 'timezone'
    desc = 'The server leaderboard timezone.'
    long_desc = (
        "The leaderboard timezone.\n"
        "The current day/week/month/year displayed on the leaderboard will be calculated using this timezone."
    )

    @property
    def success_response(self):
        return (
            "The leaderboard timezone is now {}. "
            "The current time is **{}**."
        ).format(self.formatted, datetime.datetime.now(tz=self.value).strftime("%H:%M"))


@GuildSettings.attach_setting
class studyrole(Role, GuildSetting):
    attr_name = 'studyrole'
    _data_column = 'studyrole_roleid'

    write_ward = guild_admin

    display_name = 'studyrole'
    desc = 'Common study role given to all timer members.'
    long_desc = (
        "This role will be given to members when they join any group, "
        "and removed when they leave the group, acting as a global study role.\n"
        "The purpose is to facilitate easier simpler study permission management, "
        "for example to control what channels studying members see."
    )

    @classmethod
    async def _parse_userstr(cls, ctx, id: int, userstr: str, **kwargs):
        roleid = await super()._parse_userstr(ctx, id, userstr, **kwargs)
        if roleid:
            role = ctx.guild.get_role(roleid)
            # Check permissions
            if role >= ctx.guild.me.top_role:
                raise UserInputError("The study role must be lower than my top role!")
        return roleid

    @property
    def success_response(self):
        if self.data:
            return "The global study role is now {}.".format(self.value.mention)
        else:
            return "The global study role has been removed."
