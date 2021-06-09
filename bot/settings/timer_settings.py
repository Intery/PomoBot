from data import tables
from utils.lib import prop_tabulate
from wards import timer_admin
from utils.lib import DotDict

from .base import Setting, ObjectSettings, ColumnData
from .setting_types import Boolean, String, Channel, PatternType, UserInputError


class TimerSettings(ObjectSettings):
    settings = DotDict()


class TimerSetting(ColumnData, Setting):
    _table_interface = tables.timers
    _id_column = 'roleid'
    _upsert = False

    write_ward = timer_admin

    category: str = 'Misc'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer = kwargs.get('timer', None)

    @property
    def timer(self):
        if self._timer is None:
            self._timer = self.client.interface.fetch_timer(self.id)
        return self._timer

    @property
    def embed(self):
        embed = super().embed
        embed.title = "Configuration options for `{}` in `{}`".format(
            self.display_name,
            self.timer.name
        )
        return embed

    def write(self, **kwargs):
        super().write(**kwargs)
        self.timer.load()


@TimerSettings.attach_setting
class name(String, TimerSetting):
    _data_column = 'name'

    category = 'Core'
    display_name = 'name'
    desc = "Name of the study group."

    long_desc = "Name of the group, shown in timer messages and used to join the timer."

    @classmethod
    async def _parse_userstr(cls, ctx, id: int, userstr: str, **kwargs):
        name = await super()._parse_userstr(ctx, id, userstr, **kwargs)
        if name is None or not name:
            raise UserInputError("Timer name cannot be none or empty!")
        if len(name) > 30:
            raise UserInputError("Timer name must be between `1` and `30` characters long!")
        if name.lower() in (timer.name.lower() for timer in ctx.timers.get_timers_in(ctx.guild.id)):
            raise UserInputError("Another timer already exists with this name!")
        return name


@TimerSettings.attach_setting
class channel(Channel, TimerSetting):
    _data_column = 'channelid'

    category = 'Core'
    display_name = 'channel'
    desc = "Text channel for timer subscription and messages."
    long_desc = (
        "Text channel where the timer sends stage updates and other messages. "
        "Unless the `globalgroups` server option is set, "
        "the timer may also only be joined from this channel."
    )

    @classmethod
    async def _parse_userstr(cls, ctx, id: int, userstr: str, **kwargs):
        channelid = await super()._parse_userstr(ctx, id, userstr, **kwargs)
        if channelid:
            channel = ctx.guild.get_channel(channelid)
            chan_perms = channel.permissions_for(ctx.guild.me)
            if not chan_perms.read_messages:
                raise UserInputError("Cannot read messages in {}.".format(channel.mention))
            elif not chan_perms.send_messages:
                raise UserInputError("Cannot send messages in {}.".format(channel.mention))
            elif not chan_perms.read_message_history:
                raise UserInputError("Cannot read message history in {}.".format(channel.mention))
            elif not chan_perms.embed_links:
                raise UserInputError("Cannot send embeds in {}.".format(channel.mention))
            elif not chan_perms.manage_messages:
                raise UserInputError("Cannot manage messages in {}.".format(channel.mention))
        return channelid


@TimerSettings.attach_setting
class default_pattern(PatternType, TimerSetting):
    _data_column = 'patternid'

    category = 'Core'
    display_name = 'default_pattern'
    desc = "Default timer pattern to use when timer is reset."

    long_desc = (
        "The timer pattern applied when the timer is reset.\n"
        "The timer may be reset either manually through the `reset` command, "
        "or automatically if the `auto_reset` timer setting is on."
    )


@TimerSettings.attach_setting
class auto_reset(Boolean, TimerSetting):
    _data_column = 'auto_reset'

    _default = False

    category = 'Core'
    display_name = 'auto_reset'
    desc = "Automatically reset when there are no members."

    long_desc = (
        "Automatically reset empty timers to their default pattern.\n"
        "When set, the timer will automatically stop and reset itself to the default pattern "
        "when it is empty. The reset occurs on the next stage change."
    )


@TimerSettings.attach_setting
class admin_locked(Boolean, TimerSetting):
    _data_column = 'admin_locked'

    _default = False

    category = 'Core'
    display_name = 'admin_locked'
    desc = "Whether timer members are restricted from controlling the timer."

    long_desc = (
        "Whether timer admin permissions are required to control the timer.\n"
        "When this is set, all **Timer Control** commands (such as `start`, `skip`, and `stop`) "
        "require timer admin permissions. This essentially makes the timer 'static', "
        "locked to a fixed pattern, and not modifiable by regular members.\n"
        "There is one exception to the timer control rule, "
        "in that members may start a timer that has been stopped (but not change its pattern). "
        "This is to support use of the `auto_reset` setting."
    )


@TimerSettings.attach_setting
class voice_channel(Channel, TimerSetting):
    _data_column = 'voice_channelid'

    category = 'Voice'
    display_name = 'voice_channel'
    desc = "Associated voice channel for alerts and auto-subscriptions."

    long_desc = (
        "Voice channel used for alerts and automatic subscriptions.\n"
        "When set, this channel will be used for voice alerts when changing stage (see `voice_alerts`), "
        "and automatic (un)subscriptions when members join or leave the channel "
        "(see `track_vc_join` and `track_vc_leave`).\n"
        "The name of the voice channel will also be updated to reflect the timer status (see `vc_name`).\n"
        "To avoid ambiguitiy, each voice channel can be bound to at most one group."
    )

    @classmethod
    async def _parse_userstr(cls, ctx, id: int, userstr: str, **kwargs):
        channelid = await super()._parse_userstr(ctx, id, userstr, **kwargs)
        if channelid:
            channel = ctx.guild.get_channel(channelid)
            # Check whether another timer exists with this voice channel
            other = next(
                (timer for timer in ctx.timers.get_timers_in(ctx.guild.id) if timer.voice_channelid == channel.id),
                None
            )
            if other is not None:
                raise UserInputError("{} is already bound to the group **{}**".format(channel.mention, other.name))

            # Check voice channel permissions
            voice_perms = channel.permissions_for(ctx.guild.me)
            if not voice_perms.connect:
                raise UserInputError("Cannot connect to {}.".format(channel.mention))
            elif not voice_perms.speak:
                raise UserInputError("Cannot speak in {}.".format(channel.mention))
            elif not voice_perms.view_channel:
                raise UserInputError("Cannot see {}.".format(channel.mention))
        return channelid


@TimerSettings.attach_setting
class voice_alert(Boolean, TimerSetting):
    _data_column = 'voice_alert'

    _default = True

    category = 'Voice'
    display_name = 'voice_alerts'
    desc = "Emit voice alerts on stage changes."

    long_desc = (
        "When set, the bot will join the voice channel and emit an audio alert upon each stage change."
    )


@TimerSettings.attach_setting
class track_voice_join(Boolean, TimerSetting):
    _data_column = 'track_voice_join'

    _default = True

    category = 'Voice'
    display_name = 'track_vc_join'
    desc = "Automatically subscribe members joining the voice channel."

    long_desc = (
        "Whether to automatically subscribe members joining the voice channel."
    )


@TimerSettings.attach_setting
class track_voice_leave(Boolean, TimerSetting):
    _data_column = 'track_voice_leave'

    _default = True

    category = 'Voice'
    display_name = 'track_vc_leave'
    desc = "Automatically unsubscribe members leaving the voice channel."

    long_desc = (
        "Whether to automatically unsubscribe members leaving the voice channel."
    )


@TimerSettings.attach_setting
class compact(Boolean, TimerSetting):
    _data_column = 'compact'

    _default = False

    category = 'Format'
    display_name = 'compact'
    desc = "Use a more compact format for timer messages."

    long_desc = (
        "Whether to use a more compact format on timer messages, including "
        "stage change messages and subscription/unsubscription messages. "
        "Some information is lost, but this is generally safe to use on "
        "servers where the members have experience with the timer."
    )


@TimerSettings.attach_setting
class vc_name(String, TimerSetting):
    _data_column = 'voice_channel_name'

    _default = "{name} - {stage_name} ({remaining})"

    category = 'Format'
    display_name = 'vc_name'
    desc = "Updating name for the associated voice channel."
    accepts = "A short text string, accepting the following substitutions."

    long_desc = (
        "When a voice channel is associated to the timer (see `voice_channel`), "
        "the name of the voice channel will be updated to reflect the current status of the timer. "
        "This setting controls the format of that name.\n"
        "*Note that due to discord restrictions the name can update at most once per 10 minutes. "
        "The remaining time property will thus generally be inaccurate.*"
    )

    @classmethod
    async def _parse_userstr(cls, ctx, id: int, userstr: str, **kwargs):
        name = await super()._parse_userstr(ctx, id, userstr, **kwargs)

        if not (2 < len(name) < 100):
            raise UserInputError("Channel names must be between `2` and `100` characters long.")

        return name

    @property
    def embed(self):
        embed = super().embed

        fields = ("Current value", "Preview", "Default value", "Accepted input")
        values = (self.formatted or "Not Set",
                  "`{}`".format(self.timer.voice_channel_name),
                  self._format_data(self.id, self.default) or "None",
                  self.accepts)
        table = prop_tabulate(fields, values)
        embed.description = "{}\n{}".format(self.long_desc, table)

        subs = {
            '{name}': "Name of the study group.",
            '{stage_name}': "Name of the current stage.",
            '{stage_dur}': "Duration of the current stage.",
            '{remaining}': "(Approximate) number of minutes left in the stage.",
            '{sub_count}': "Number of members subscribed to the group.",
            '{pattern}': "Short-form of the current timer pattern."
        }

        embed.add_field(
            name="Accepted substitutions.",
            value=prop_tabulate(*zip(*subs.items()))
        )
        return embed


# TODO: default_work_name, default_work_message, default_break_name, default_break_message
# Q: How do we update the default pattern with this info? Maybe we should use placeholders for the defaults instead?
