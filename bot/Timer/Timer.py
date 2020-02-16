import asyncio
import datetime
import discord
from enum import Enum


class Timer(object):
    clock_period = 5
    max_warning = 1

    def __init__(self, name, role, channel, clock_channel, stages=None):
        self.channel = channel
        self.clock_channel = clock_channel
        self.role = role
        self.name = name

        self.start_time = None  # Session start time
        self.current_stage_start = None  # Time at which the current stage started
        self.remaining = None  # Amount of time until the next stage starts
        self.state = TimerState.STOPPED  # Current state of the timer

        self.stages = stages  # List of stages in this timer
        self.current_stage = 0  # Index of current stage

        self.subscribed = {}  # Dict of subbed members, userid maps to (user, lastupdate, timesubbed)

        self.timer_messages = []  # List of sent messages that this timer owns, e.g. for reaction handling

        self.last_clockupdate = 0

        if stages:
            self.setup(stages)

    def __contains__(self, userid):
        """
        Containment interface acts as list of subscribers.
        """
        return userid in self.subscribed

    def setup(self, stages):
        """
        Setup the timer with a list of TimerStages.
        """
        self.stop()

        self.stages = stages
        self.current_stage = 0

        now = self.now()
        self.start_time = now

        self.remaining = stages[0].duration
        self.current_stage_start = now

        # Return self for method chaining
        return self

    async def update_clock_channel(self):
        """
        Try to update the name of the status channel with the current status
        """
        # Quit if there's no status channel set
        if self.clock_channel is None:
            return

        # Quit if we aren't due for a clock update yet
        if self.now() - self.last_clockupdate < self.clock_period:
            return

        # Get the name and time strings
        stage_name = self.stages[self.current_stage].name
        remaining_time = self.pretty_remaining()

        # Update the channel name, or quit silently if something goes wrong.
        try:
            await self.clock_channel.edit(name="{} - {}".format(stage_name, remaining_time))
        except Exception:
            pass
        self.last_clockupdate = self.now()

    def pretty_remaining(self):
        """
        Return a formatted version of the time remaining until the next stage.
        """
        return self.parse_dur(self.remaining)

    def pretty_pinstatus(self):
        """
        Return a formatted status string for use in the pinned status message.
        """
        subbed_names = [m.member.name for m in self.subscribed.values()]
        subbed_str = "```{}```".format(", ".join(subbed_names)) if subbed_names else "*No members*"

        if self.state in [TimerState.RUNNING, TimerState.PAUSED]:
            # Collect the component strings and data
            current_stage_name = self.stages[self.current_stage].name
            remaining = self.pretty_remaining()

            # Create a list of lines for the stage string
            longest_stage_len = max(len(stage.name) for stage in self.stages)
            stage_format = "`{{prefix}}{{name:>{}}}:` {{dur}} min  {{current}}".format(longest_stage_len)

            stage_str_lines = [
                stage_format.format(
                    prefix="->" if i == self.current_stage else "​  ",
                    name=stage.name,
                    dur=stage.duration,
                    current="(**{}**)".format(remaining) if i == self.current_stage else ""
                ) for i, stage in enumerate(self.stages)
            ]
            # Create the stage string itself
            stage_str = "\n".join(stage_str_lines)

            # Create the final formatted status string
            status_str = ("**{name}**: {current_stage_name} {paused}\n"
                          "{stage_str}\n"
                          "{subbed_str}").format(name=self.name,
                                                 role=self.role.mention,
                                                 paused=" ***Paused***" if self.state == TimerState.PAUSED else "",
                                                 current_stage_name=current_stage_name,
                                                 stage_str=stage_str,
                                                 subbed_str=subbed_str)
        elif self.state == TimerState.STOPPED:
            status_str = "**{}**: *Timer not running.*\n{}".format(self.name, subbed_str)
        return status_str

    def pretty_summary(self):
        """
        Return a short summary status message.
        """
        if self.stages:
            stage_str = "/".join(("**{}**".format(stage.duration) if i == self.current_stage else str(stage.duration))
                                 for i, stage in enumerate(self.stages))
        else:
            stage_str = "*Not set up.*"

        if self.state == TimerState.RUNNING:
            status_str = "Stage `{}`, `{}` remaining\n".format(self.stages[self.current_stage].name,
                                                               self.pretty_remaining())
        elif self.state == TimerState.PAUSED:
            status_str = "*Timer is paused.*\n"
        elif self.state == TimerState.STOPPED:
            status_str = ""

        if self.subscribed:
            member_str = "Members: " + ", ".join(s.member.mention for s in self.subscribed.values())
        else:
            member_str = "*No members.*"

        return "{} ({}): {}\n{}{}".format(
            self.role.mention,
            self.name,
            stage_str,
            status_str,
            member_str
        )

    def oneline_summary(self):
        """
        Return a one line summary status message
        """
        if self.state == TimerState.RUNNING:
            status = "Running"
        elif self.state == TimerState.PAUSED:
            status = "Paused"
        elif self.state == TimerState.STOPPED:
            status = "Stopped"

        if self.stages:
            stage_str = "/".join(str(stage.duration) for i, stage in enumerate(self.stages))
        else:
            stage_str = "not set up"

        return "{name}  ({status} with {members} members, {setup}.)".format(
            name=self.name,
            status=status,
            members=len(self.subscribed) if self.subscribed else 'no',
            setup=stage_str
        )

    async def change_stage(self, stage_index, notify=True, inactivity_check=True, report_old=True):
        """
        Advance the timer to the new stage.
        """
        stage_index = stage_index % len(self.stages)
        current_stage = self.stages[self.current_stage]
        new_stage = self.stages[stage_index]

        # Update clocked times for all the subbed users and handle inactivity
        needs_warning = []
        unsubs = []
        for subber in self.subscribed.values():
            subber.touch()
            if inactivity_check:
                if subber.warnings >= self.max_warning:
                    subber.warnings += 1
                    unsubs.append(subber)
                elif (self.now() - subber.last_seen) > current_stage.duration * 60:
                    subber.warnings += 1
                    if subber.warnings >= self.max_warning:
                        needs_warning.append(subber)

        # Handle not having any subscribers
        empty = (len(self.subscribed) == 0)

        # Handle notifications
        if notify:
            old_stage_str = "**{}** finished! ".format(current_stage.name) if report_old else ""
            if needs_warning:
                warning_str = ("{} you will be unsubscribed on the next stage "
                               "if you do not reply or react to this message.\n").format(
                    ", ".join(subber.member.mention for subber in needs_warning)
                )
            else:
                warning_str = ""
            if unsubs:
                unsub_str = "{} you have been unsubscribed due to inactivity!\n".format(
                    ", ".join(subber.member.mention for subber in unsubs)
                )
            else:
                unsub_str = ""

            main_line = "{}Starting **{}** ({} minutes). {}".format(
                old_stage_str,
                new_stage.name,
                new_stage.duration,
                new_stage.message
            )

            if not empty:
                out_msg = await self.channel.send(
                    ("{}\n{}\n"
                     "Please reply or react to this message to register your existence.\n{}{}").format(
                         self.role.mention,
                         main_line,
                         warning_str,
                         unsub_str
                     )
                )
                try:
                    await out_msg.add_reaction("✅")
                except Exception:
                    pass

                # Add the stage message to the owned message list
                self.timer_messages.append(out_msg)
                self.timer_messages = self.timer_messages[-5:]  # Truncate
            else:
                """
                await self.channel.send(
                    ("{}\n "
                     "{}No subscribers, stopping group timer.").format(
                         self.role.mention,
                         old_stage_str
                     )
                )
                self.stop()
                """
                pass

            # Notify the subscribers as desired
            for subber in self.subscribed.values():
                try:
                    out_msg = None
                    if subber in unsubs and subber.notify >= NotifyLevel.FINAL:
                        await subber.member.send(
                            "You have been unsubscribed from group **{}** in {} due to inactivity!".format(
                                self.name,
                                self.channel.mention
                            )
                        )
                    elif subber in needs_warning and subber.notify >= NotifyLevel.WARNING:
                        out_msg = await subber.member.send(
                            ("**Warning** from group **{}** in {}!\n"
                             "Please respond or react to a timer message "
                             "to avoid being unsubscribed on the next stage.\n{}").format(
                                 self.name,
                                 self.channel.mention,
                                 main_line
                             )
                        )
                    elif subber.notify >= NotifyLevel.ALL:
                        out_msg = await subber.member.send(
                            "Status update for group **{}** in {}!\n{}".format(self.name,
                                                                               self.channel.mention,
                                                                               main_line)
                        )
                    if out_msg is not None:
                        try:
                            await out_msg.add_reaction("✅")
                        except Exception:
                            pass
                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    pass

        for subber in unsubs:
            await subber.unsub()

        self.current_stage = stage_index
        self.current_stage_start = self.now()
        self.remaining = self.stages[stage_index].duration * 60

    async def start(self):
        """
        Start or restart the timer.
        """
        await self.change_stage(0, report_old=False)
        self.state = TimerState.RUNNING
        for subber in self.subscribed.values():
            subber.touch()
            subber.active = True

        asyncio.ensure_future(self.runloop())

    def stop(self):
        """
        Stop the timer, and ensure the subscriber clocked times are updated.
        """
        for subber in self.subscribed.values():
            subber.touch()
            subber.active = False

        self.state = TimerState.STOPPED

    async def runloop(self):
        while self.state == TimerState.RUNNING:
            self.remaining = int(60*self.stages[self.current_stage].duration - (self.now() - self.current_stage_start))
            if self.remaining <= 0:
                try:
                    await self.change_stage(self.current_stage + 1)
                except Exception:
                    pass

            await self.update_clock_channel()
            await asyncio.sleep(1)

    @staticmethod
    def now():
        """
        Helper to get the current UTC timestamp as an integer.
        """
        return int(datetime.datetime.timestamp(datetime.datetime.utcnow()))

    @staticmethod
    def parse_dur(diff):
        """
        Parse a duration given in seconds to a time string.
        """
        diff = max(diff, 0)
        hours = diff // 3600
        minutes = (diff % 3600) // 60
        seconds = diff % 60

        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

    def serialise(self):
        """
        Serialise current timer status to a dictionary.
        Does not serialise subscribers or fixed attributes such as channels.
        """
        return {
            'roleid': self.role.id,
            'name': self.name,
            'start_time': self.start_time,
            'current_stage_start': self.current_stage_start,
            'remaining': self.remaining,
            'state': self.state.value,
            'stages': [stage.serialise() for stage in self.stages] if self.stages else None,
            'current_stage': self.current_stage
        }

    def update_from_data(self, data):
        """
        Restore timer status from the provided status dict, as produced by `serialise`.
        """
        self.name = data['name']
        self.start_time = data['start_time']
        self.current_stage_start = data['current_stage_start']
        self.remaining = data['remaining']
        self.state = TimerState(data['state'])
        self.stages = [TimerStage.deserialise(stage_data) for stage_data in data['stages']] if data['stages'] else None
        self.current_stage = data['current_stage']

        asyncio.ensure_future(self.runloop())
        return self


class TimerState(Enum):
    """
    Enum representing the current running state of the timer.
    STOPPED: The timer either hasn't been set up, or has been stopped externally.
    RUNNING: The timer is running normally.
    PAUSED: The timer has been paused by a user.
    """
    STOPPED = 1
    RUNNING = 2
    PAUSED = 3


class TimerStage(object):
    """
    Small data class to encapsualate a "stage" of a timer.

    Parameters
    ----------
    name: str
        The human readable name of the stage.
    duration: int
        The number of minutes the stage lasts for.
    message: str
        An optional message to send when starting this stage.
    focus: bool
        Whether `focus` mode is set for this stage.
    modifiers: Dict(str, bool)
        An unspecified collection of stage modifiers, stored for external use.
    """
    __slots__ = ('name', 'message', 'duration', 'focus', 'modifiers')

    def __init__(self, name, duration, message="", focus=False, **modifiers):
        self.name = name
        self.duration = duration
        self.message = message

        self.focus = focus

        self.modifiers = modifiers

    def serialise(self):
        """
        Serialise stage to a serialisable dictionary.
        """
        return {
            'name': self.name,
            'duration': self.duration,
            'message': self.message,
            'focus': self.focus,
            'modifiers': self.modifiers
        }

    @classmethod
    def deserialise(cls, data_dict):
        """
        Deserialise stage from a dictionary formatted like the output of `serialise.
        """
        return cls(
            data_dict['name'],
            data_dict['duration'],
            message=data_dict['message'],
            focus=data_dict['focus'],
            **data_dict['modifiers']
        )


class TimerChannel(object):
    """
    A data class representing a guild channel bound to (potentially) several timers.

    Parameters
    ----------
    channel: discord.Channel
        The bound discord guild channel
    timers: List(Timer)
        The timers bound to the channel
    msg: discord.Message
        A valid and current discord Message in the channel.
        Holds the updating timer status messages.
    """
    __slots__ = ('channel', 'timers', 'msg', 'old_desc')

    def __init__(self, channel):
        self.channel = channel

        self.timers = []
        self.msg = None

        self.old_desc = ""

    async def update(self):
        """
        Create or update the channel status message.
        """
        messages = [timer.pretty_pinstatus() for timer in self.timers]
        if messages:
            desc = "\n\n".join(messages)

            # Don't resend the same message
            if desc == self.old_desc:
                return
            self.old_desc = desc

            embed = discord.Embed(
                title="Pomodoro Timer Status",
                description=desc,
                timestamp=datetime.datetime.utcnow()
            )
            if self.msg is not None:
                try:
                    await self.msg.edit(embed=embed)
                except discord.NotFound:
                    self.msg = None
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

                """
                if all(timer.state == TimerState.STOPPED for timer in self.timers):
                    # Unpin and unset message
                    try:
                        await self.msg.unpin()
                    except Exception:
                        pass

                    self.msg = None
                """
            elif any(timer.state != TimerState.STOPPED for timer in self.timers):
                # Attempt to generate a new message
                try:
                    self.msg = await self.channel.send(embed=embed)
                except discord.Forbidden:
                    await self.channel.send("I require permission to send embeds in this channel! Stopping all timers.")
                    for timer in self.timers:
                        timer.stop()

                # Pin the message
                try:
                    await self.msg.pin()
                except Exception:
                    pass


class NotifyLevel(Enum):
    """
    Enum representing a subscriber's notification level.
    NONE: Never send direct messages.
    FINAL: Send a direct message when kicking for inactivity.
    WARNING: Send direct messages for unsubscription warnings.
    ALL: Send direct messages for all stage updates.
    """
    NONE = 1
    FINAL = 2
    WARNING = 3
    ALL = 4

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class TimerSubscriber(object):
    __slots__ = (
        'member',
        'timer',
        'interface',
        'notify',
        'client',
        'id',
        'time_joined',
        'last_updated',
        'clocked_time',
        'active',
        'last_seen',
        'warnings'
    )

    def __init__(self, member, timer, interface, notify=NotifyLevel.WARNING):
        self.member = member
        self.timer = timer
        self.interface = interface
        self.notify = notify

        self.client = interface.client
        self.id = member.id

        now = Timer.now()
        self.time_joined = now

        self.last_updated = now
        self.clocked_time = 0
        self.active = (timer.state == TimerState.RUNNING)

        self.last_seen = now
        self.warnings = 0

    async def unsub(self):
        return await self.interface.unsub(self.id)

    def bump(self):
        self.last_seen = Timer.now()
        self.warnings = 0

    def touch(self):
        """
        Update the clocked time based on the active status.
        """
        now = Timer.now()
        self.clocked_time += (now - self.last_updated) if self.active else 0
        self.last_updated = now

    def session_data(self):
        """
        Return session data in a format compatible with the registry.
        """
        self.touch()

        return (
            self.id,
            self.member.guild.id,
            self.timer.role.id,
            self.time_joined,
            self.clocked_time
        )

    def serialise(self):
        return {
            'id': self.id,
            'guildid': self.member.guild.id,
            'roleid': self.timer.role.id,
            'notify': self.notify.value,
            'time_joined': self.time_joined,
            'last_updated': self.last_updated,
            'clocked_time': self.clocked_time,
            'active': self.active,
            'last_seen': self.last_seen,
            'warnings': self.warnings
        }

    @classmethod
    def deserialise(cls, member, timer, interface, data):
        self = cls(member, timer, interface)

        self.time_joined = data['time_joined']
        self.last_updated = data['last_updated']
        self.clocked_time = data['clocked_time']
        self.active = data['active']
        self.notify = NotifyLevel(data['notify'])
        self.last_seen = data['last_seen']
        self.warnings = data['warnings']

        return self
