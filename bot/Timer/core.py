import json
import asyncio
import logging
import datetime
from collections import namedtuple

import cachetools
import discord

from meta import client, log
from data import tables
from settings import TimerSettings, GuildSettings

from .voice_notify import play_alert
from .lib import join_emoji, leave_emoji, now, parse_dur, best_prefix, TimerState, NotifyLevel, InvalidPattern


# NamedTuple represeting a pattern stage
Stage = namedtuple('Stage', ('name', 'duration', 'message', 'focus'))


class Pattern:
    _slots = ('row', 'stages')

    _cache = cachetools.LFUCache(1000)
    _table = tables.patterns

    default_work_stage = "Work"
    default_work_message = "Good luck!"
    default_break_stage = "Break"
    default_break_message = "Have a rest!"

    def __init__(self, row, stages=None):
        self.row = row
        self.stages = stages or [Stage(*stage) for stage in json.loads(row.stage_str)]
        self._cache[(self.__class__, self.row.patternid)] = self

    def __iter__(self):
        return iter(self.stages)

    def __str__(self):
        return self.display()

    def display(self, brief=None, truncate=None):
        brief = brief if brief is not None else self.row.short_repr
        if brief:
            if truncate and len(self.stages) > truncate:
                return "/".join(str(stage.duration) for stage in self.stages[:truncate]) + '/...'
            else:
                return "/".join(str(stage.duration) for stage in self.stages)
        else:
            return ";\n".join(
                "{0.name}, {0.duration}{1}, {0.message}".format(stage, '*' * stage.focus)
                for stage in self.stages
            )

    @classmethod
    def from_userstr(cls, string, timerid=None, userid=None, guildid=None):
        """
        Parse a user-provided string into a `Pattern`, if possible.
        Raises `InvalidPattern` for parsing errors.
        Where possible, an existing `Pattern` will be returned,
        otherwise a new `Pattern` will be created.

        Accepts kwargs to describe the parsing context.
        """
        if not string:
            raise InvalidPattern("No pattern provided!")

        # Parsing step
        pattern = None
        stages = None
        if ';' in string or ',' in string:
            # Long form
            # Accepts stages as 'name, length' or 'name, length, message'
            short_repr = False
            stage_blocks = string.strip(';').split(';')
            stages = []
            for block in stage_blocks:
                # Extract stage components
                parts = block.split(',', maxsplit=2)
                if len(parts) == 1:
                    raise InvalidPattern(
                        "`{}` is not of the form `name, length` or `name, length, message`.".format(block)
                    )
                elif len(parts) == 2:
                    name, dur = parts
                    message = None
                else:
                    name, dur, message = parts

                # Parse duration
                dur = dur.strip()
                focus = dur.startswith('*') or dur.endswith('*')
                if focus:
                    dur = dur.strip('* ')

                if not dur.isdigit():
                    raise InvalidPattern(
                        "`{}` in `{}` couldn't be parsed as a duration.".format(dur, block.strip())
                    )

                # Build and add stage
                stages.append(Stage(name.strip(), int(dur), (message or '').strip(), focus))
        elif '/' in string:
            # Short form
            # Only accepts numerical stages
            short_repr = True
            stage_blocks = string.strip('/').split('/')
            stages = []

            is_work = True  # Whether the current stage is a work or break stage
            default_focus = '*' not in string  # Whether to use default focus flags
            for block in stage_blocks:
                # Parse duration
                dur = block.strip()
                focus = dur.startswith('*') or dur.endswith('*')
                if focus:
                    dur = dur.strip('* ')

                if not dur.isdigit():
                    raise InvalidPattern(
                        "`{}` couldn't be parsed as a duration.".format(dur)
                    )

                # Build and add stage
                if is_work:
                    stages.append(Stage(
                        cls.default_work_stage,
                        int(dur),
                        cls.default_work_message,
                        focus=True if default_focus else focus
                    ))
                else:
                    stages.append(Stage(
                        cls.default_break_stage,
                        int(dur),
                        cls.default_break_message,
                        focus=False if default_focus else focus
                    ))

                is_work = not is_work
        else:
            # Attempt to find a matching preset
            if userid:
                row = tables.user_presets.select_one_where(userid=userid, preset_name=string)
                if row:
                    pattern = cls.get(row['patternid'])

            if not pattern and guildid:
                row = tables.guild_presets.select_one_where(guildid=guildid, preset_name=string)
                if row:
                    pattern = cls.get(row['patternid'])

            if not pattern:
                raise InvalidPattern("Patterns must have more than one stage!")

        if stages:
            # Create the stage string
            stage_str = json.dumps(stages)

            # Fetch or create the pattern row
            row = cls._table.fetch_or_create(
                short_repr=short_repr,
                stage_str=stage_str
            )

            # Initialise and return the pattern
            if row.patternid in cls._cache:
                pattern = cls._cache[row.patternid]
            else:
                pattern = cls(row, stages=stages)

        return pattern

    @classmethod
    @cachetools.cached(_cache)
    def get(cls, patternid):
        return cls(cls._table.fetch(patternid))


class Timer:
    __slots__ = (
        'data',
        'settings',
        'state',
        'current_pattern',
        'stage_index',
        'stage_start',
        '_loop_wait_task',
        'subscribers',
        'message_ids',
        'guild',
        'role',
        'channel',
        'voice_channel',
        'last_voice_update'
    )

    _table = tables.timers

    max_warnings = 1

    def __init__(self, data):
        self.data = data
        self.settings = TimerSettings(data.roleid, timer=self)

        self.state: TimerState = TimerState.UNSET  # State of the timer
        self.current_pattern: Pattern = None  # Current pattern set up
        self.stage_index: int = None  # Index of the current stage in the pattern
        self.stage_start: int = None  # Timestamp of the start of the stage

        self._loop_wait_task = None  # Task used to trigger runloop read

        self.subscribers = {}  # TimerSubscribers in the timer
        self.message_ids = []  # Notification messages owned by the timer

        self.last_voice_update = 0  # Timestamp of last vc update

        # Discord objects, intialised in `Timer.load()`
        self.guild: discord.Guild = None
        self.role: discord.Role = None
        self.channel: discord.TextChannel = None
        self.voice_channel: discord.VoiceChannel = None

    def __getattr__(self, key):
        # TODO: Dangerous due to potential property attribute errors
        if key in self.data.table.columns:
            return getattr(self.data, key)
        else:
            raise AttributeError(key)

    def __contains__(self, userid):
        return userid in self.subscribers

    @property
    def default_pattern(self) -> Pattern:
        return Pattern.get(self.data.patternid)

    @property
    def current_stage(self):
        return self.current_pattern.stages[self.stage_index]

    @property
    def remaining(self):
        """
        The remaining time (in seconds) in the current stage.
        """
        return int(60*self.current_stage.duration - (now() - self.stage_start))

    @property
    def pretty_remaining(self):
        return parse_dur(
            self.remaining,
            show_seconds=True
        ) if self.state == TimerState.RUNNING else '*Not Running*'

    @property
    def pinstatus(self):
        """
        Return a formatted status string for use in the pinned status message.
        """
        return self.status_string()

    @property
    def voice_channel_name(self):
        return self.settings.vc_name.value.replace(
            "{stage_name}", self.current_stage.name
        ).replace(
            "{remaining}", parse_dur(
                int(60*self.current_stage.duration - (now() - self.stage_start)),
                show_seconds=False
            )
        ).replace(
            "{name}", self.data.name
        ).replace(
            "{stage_dur}", parse_dur(self.current_stage.duration * 60, show_seconds=False)
        ).replace(
            "{sub_count}", str(len(self.subscribers))
        ).replace(
            "{pattern}", (self.current_pattern or self.default_pattern).display(brief=True, truncate=6)
        )

    @property
    def oneline_summary(self):
        """
        Return a one line summary status message
        """
        if self.state == TimerState.RUNNING:
            status = "Running"
        elif self.state == TimerState.PAUSED:
            status = "Paused"
        elif self.state in (TimerState.STOPPED, TimerState.UNSET):
            status = "Stopped"

        return "{name}  ({status} with {members} members, {setup}.)".format(
            name=self.data.name,
            status=status,
            members=len(self.subscribers) if self.subscribers else 'no',
            setup=(self.current_pattern or self.default_pattern).display(brief=True)
        )

    @property
    def pretty_summary(self):
        pattern = self.current_pattern or self.default_pattern
        stage_str = "/".join(
            "{1}{0}{1}".format(stage.duration, (i == self.stage_index) * '**')
            for i, stage in enumerate(pattern.stages)
        )

        if self.state == TimerState.RUNNING:
            status_str = "Stage `{}`, `{}` remaining\n".format(self.current_stage.name, self.pretty_remaining)
        elif self.state == TimerState.PAUSED:
            status_str = "*Timer is paused.*\n"
        else:
            status_str = ''

        if self.subscribers:
            member_str = "Members: " + ", ".join("<@{}>".format(uid) for uid in self.subscribers)
        else:
            member_str = "*No members.*"

        return "{}{}: {}\n{}{}".format(
            self.role.mention,
            "({})".format(self.data.name) if self.data.name != self.role.name else '',
            stage_str,
            status_str,
            member_str
        )

    def status_string(self, show_seconds=False):
        subbed_names = [m.name for m in self.subscribers.values()]
        subbed_str = "```{}```".format(", ".join(subbed_names)) if subbed_names else "*No members*"

        if self.state in (TimerState.RUNNING, TimerState.PAUSED, TimerState.STOPPED):
            running = self.state in (TimerState.RUNNING, TimerState.PAUSED)

            # Collect the component strings and data
            pretty_remaining = parse_dur(
                int(60*self.current_stage.duration - (now() - self.stage_start)),
                show_seconds=show_seconds
            ) if running else ''

            # Create the stage string
            longest_stage_len = max(len(stage.name) for stage in self.current_pattern.stages)
            stage_format = "`{{prefix}}{{name:>{}}}:` {{dur}} min  {{current}}".format(longest_stage_len)

            stage_str = '\n'.join(
                stage_format.format(
                    prefix="->" if running and i == self.stage_index else "​  ",
                    name=stage.name,
                    dur=stage.duration,
                    current="(**{}**)".format(pretty_remaining) if running and i == self.stage_index else ''
                ) for i, stage in enumerate(self.current_pattern.stages)
            )

            # Create the final formatted status string
            status_str = ("**{name}**: {stage} {paused}\n"
                          "{stage_str}\n"
                          "{subbed_str}").format(name=self.data.name,
                                                 paused=" ***Paused***" if self.state == TimerState.PAUSED else "",
                                                 stage=self.current_stage.name if running else "*Timer not running.*",
                                                 stage_str=stage_str,
                                                 subbed_str=subbed_str)
        else:
            status_str = "**{}**: *Timer not set up.*\n{}".format(self.data.name, subbed_str)

        return status_str

    @classmethod
    def create(cls, roleid, guildid, name, channelid, **kwargs):
        log("Creating Timer with (roleid={!r}, guildid={!r}, name={!r}, channelid={!r})".format(roleid,
                                                                                                guildid,
                                                                                                name,
                                                                                                channelid),
            context="rid:{}".format(roleid))

        # Remove any existing timers under the same roleid
        cls._table.delete_where(roleid=roleid)

        # Create new timer
        data = cls._table.create_row(roleid=roleid,
                                     guildid=guildid,
                                     name=name,
                                     channelid=channelid,
                                     **kwargs)

        # Instantiate and return
        return cls(data)

    async def destroy(self):
        log("Destroying Timer with data {!r}".format(self.data), context="rid:{}".format(self.data.roleid))

        # Stop the timer and unsubscribe all members
        self.stop()
        for subid in list(self.subscribers.keys()):
            await self.unsubscribe(subid)

        # Remove the timer from data
        self._table.delete_where(roleid=self.data.roleid)

    def load(self):
        """
        Load discord objects from data.

        Returns
        -------
        `True` if the timer successfully loaded.
        `False` if the guild, channel, or role no longer exist.
        """
        data = self.data

        self.guild = client.get_guild(data.guildid)
        if not self.guild:
            log("Timer gone, guild (gid: {}) no longer exists.".format(data.guildid),
                "tid:{}".format(data.roleid))
            return False

        self.role = self.guild.get_role(data.roleid)
        if not self.role:
            log("Timer gone, role no longer exists.",
                "tid:{}".format(data.roleid))
            return False

        self.channel = self.guild.get_channel(data.channelid)
        if not self.channel:
            log("Timer gone, channel (cid: {}) no longer exists.".format(data.channelid),
                "tid:{}".format(data.roleid))
            return False

        if data.voice_channelid:
            self.voice_channel = self.guild.get_channel(data.voice_channelid)

        return True

    async def post(self, *args, **kwargs):
        """
        Safely send a message to the timer channel.
        If an error occurs, in most cases ignore it.
        As such, is not guaranteed to yield a `discord.Message`.
        """
        # TODO: Reconsider if we want some form of cleanup here
        try:
            return await self.channel.send(*args, **kwargs)
        except discord.Forbidden:
            # We are not allowed to send to the timer channel
            # Stop the timer
            self.stop()
        except discord.HTTPException:
            # An unknown discord error occured
            # Silently continue
            pass

    async def setup(self, pattern=None, actor=None):
        """
        Setup the timer with the given timer pattern.
        If no pattern is given, uses the default pattern.
        """
        pattern = pattern or self.default_pattern

        log("Setting up timer with pattern {!r}.".format(pattern.row), context="rid:{}".format(self.data.roleid))

        # Ensure timer is stopped
        self.stop()

        # Update runtime data for new pattern
        self.current_pattern = pattern
        self.stage_index = 0

        tables.timer_pattern_history.insert(
            timerid=self.data.roleid,
            patternid=pattern.row.patternid,
            modified_by=actor
        )

    async def start(self):
        """
        Start the timer with the current pattern, or the default pattern.
        """
        log("Starting timer.", context="rid:{}".format(self.data.roleid))
        if not self.current_pattern:
            await self.setup()

        await self.change_stage(0, inactivity_check=False, finished_old=False)
        self.state = TimerState.RUNNING
        for subber in self.subscribers.values():
            subber.new_session()

        asyncio.create_task(self.runloop())

    def stop(self):
        """
        Stop the timer.
        """
        if not self.state == TimerState.STOPPED:
            log("Stopping timer.", context="rid:{}".format(self.data.roleid))
            # Trigger session save on all subscribers
            for subber in self.subscribers.values():
                subber.close_session()

            # Change status to stopped
            self.state = TimerState.STOPPED

            # Cancel loop wait task
            if self._loop_wait_task and not self._loop_wait_task.done():
                self._loop_wait_task.cancel()

    def shift(self, amount=None):
        """
        Shift the running timer forwards or backwards by the provided amount.
        If `amount` is not given, aligns the start of the session to the nearest (UTC) hour.

        `amount` is the amount (in seconds) the stage start is shifted *forwards*.
        This effectively adds `amount` to the stage duration, since it will change `amount` seconds later.
        """
        if amount is None:
            # Get the difference to the nearest hour
            started = datetime.datetime.utcfromtimestamp(self.stage_start)
            amount = started.minute * 60 + started.second
            if amount > 1800:
                amount = 3600 - amount
            else:
                amount = -1 * amount

        # Find the target stage and new stage start
        remaining_amount = -1 * amount
        i = self.stage_index
        is_first = True
        while True:
            stage = self.current_pattern.stages[i]
            stage_remaining = self.remaining if is_first else stage.duration * 60
            if remaining_amount >= stage_remaining:
                is_first = False
                remaining_amount -= stage_remaining
                i = (i + 1) % len(self.current_pattern.stages)
            else:
                break
        target_stage = i
        if is_first:
            new_stage_start = self.stage_start - remaining_amount
            shifts = [(self.stage_index, -remaining_amount)]
        else:
            new_stage_start = now() - remaining_amount
            shifts = [
                (self.stage_index, now() - self.stage_start),
                (target_stage, -1 * remaining_amount)
            ]

        # Apply shifts
        for subber in self.subscribers.values():
            for shift in shifts:
                subber.stage_shift(*shift)

        # Update timer
        self.stage_index = target_stage
        self.stage_start = new_stage_start

        # Cancel loop wait task to rerun runloop
        if self._loop_wait_task and not self._loop_wait_task.done():
            self._loop_wait_task.cancel()

    async def change_stage(self, stage_index, post=True, inactivity_check=True, finished_old=True):
        """
        Change the timer stage to the given index in the current pattern.

        Parameters
        ----------
        stage_index: int
            Index to move to in the current pattern.
            Will be modded by the lenth of the pattern.
        post: bool
            Whether to post a stage change message in the linked text channel.
        """
        log(
            "Changing stage from {} to {}. (post={}, inactivity_check={}, finished_old={})".format(
                self.stage_index,
                stage_index,
                post,
                inactivity_check,
                finished_old
            ), context="rid:{}".format(self.data.roleid), level=logging.DEBUG
        )

        # If the stage change is triggered by finishing a stage, adjust current time to match
        if finished_old:
            _now = self.stage_start + self.current_stage.duration * 60
            if not -3600 < _now - now() < 3600:
                # Don't voice notify if there is a significant real time difference
                post = False
        else:
            _now = now()

        # Update stage info and save the current and new stages
        old_stage = self.current_stage
        old_index = self.stage_index

        self.stage_index = stage_index % len(self.current_pattern.stages)
        self.stage_start = _now
        new_stage = self.current_stage

        # Update the voice channel
        asyncio.create_task(self.update_voice())

        if len(self.subscribers) == 0:
            # Skip notification and subscriber checks
            # Handle empty reset, if enabled
            if self.settings.auto_reset.value:
                await self.setup()
            return

        # Update subscriber sessions
        if finished_old:
            for sub in self.subscribers.values():
                sub.stage_finished(old_index)

        # Track subscriber inactivity
        needs_warning = []
        unsubs = []
        if inactivity_check:
            for sub in self.subscribers.values():
                if sub.warnings >= self.max_warnings:
                    sub.warnings += 1
                    unsubs.append(sub)
                elif (_now - sub.last_seen) > old_stage.duration * 60:
                    sub.warnings += 1
                    if sub.warnings >= self.max_warnings:
                        needs_warning.append(sub)

        # Build message components
        old_stage_str = "**{}** finished! ".format(old_stage.name) if finished_old else ""
        warning_str = (
            "{} you will be unsubscribed on the next stage if you do not respond or react to this message.\n".format(
                ', '.join('<@{}>'.format(sub.userid) for sub in needs_warning)
            )
        ) if needs_warning else ""
        unsub_str = (
            "{} you have been unsubscribed due to inactivity!\n".format(
                ', '.join('<@{}>'.format(sub.userid) for sub in unsubs)
            )
        ) if unsubs else ""
        main_line = "{}Starting **{}** ({} minutes). {}".format(
            old_stage_str,
            new_stage.name,
            new_stage.duration,
            new_stage.message
        )
        please_line = (
            "Please respond or react to this message to avoid being unsubscribed.\n"
        ) if not self.settings.compact.value else ""

        # Post stage change message, if required
        if post:
            make_unmentionable = False
            can_manage = self.guild.me.guild_permissions.manage_roles and self.guild.me.top_role > self.role
            # Make role mentionable
            if not self.role.mentionable and can_manage:
                try:
                    await self.role.edit(mentionable=True, reason="Notifying for stage change.")
                    make_unmentionable = True
                except discord.HTTPException:
                    pass

            # Send the message
            out_msg = await self.post(
                "{} {}\n{}{}{}".format(
                    self.role.mention,
                    main_line,
                    please_line,
                    warning_str,
                    unsub_str
                    )
            )
            if out_msg:
                # Mark the message as being tracked
                self.message_ids.append(out_msg.id)
                self.message_ids = self.message_ids[-5:]  # Truncate

                # Add the check reaction
                try:
                    await out_msg.add_reaction(join_emoji)
                    await out_msg.add_reaction(leave_emoji)
                except discord.HTTPException:
                    pass

            if make_unmentionable:
                try:
                    await self.role.edit(mentionable=False, reason="Notifying finished.")
                except discord.HTTPException:
                    pass

        # Do the voice alert, if required
        if self.settings.voice_alert.value and self.voice_channel and finished_old and post:
            asyncio.create_task(play_alert(self.voice_channel))

        # Notify and unsubscribe as required
        for sub in list(self.subscribers.values()):
            try:
                to_send = None
                if sub in unsubs:
                    sub = await self.unsubscribe(sub.userid)
                    if sub.notify_level >= NotifyLevel.FINAL:
                        to_send = (
                            "You have been unsubscribed from the group **{}** in {} due to inactivity!\n"
                            "You were subscribed for **{}**."
                        ).format(self.data.name, self.channel.mention, sub.pretty_clocked)
                elif sub in needs_warning and sub.notify_level >= NotifyLevel.WARNING:
                    to_send = (
                        "**Warning** from group **{}** in {}!\n"
                        "Please respond or react to a timer message "
                        "to avoid being unsubscribed on the next stage.\n{}".format(
                            self.data.name,
                            self.channel.mention,
                            main_line
                        )
                    )
                elif sub.notify_level >= NotifyLevel.ALL:
                    to_send = "Status update for group **{}** in {}!\n{}".format(self.data.name,
                                                                                 self.channel.mention,
                                                                                 main_line)

                if to_send is not None:
                    await sub.send(to_send)
            except discord.HTTPException:
                pass

    async def subscribe(self, member, post=False):
        """
        Subscribe a new member to the timer.
        This may raise `discord.HTTPException`.
        """
        log("Subscribing {!r}.".format(member), context="rid:{}".format(self.data.roleid))
        studyrole = GuildSettings(member.guild.id).studyrole.value
        if studyrole:
            await member.add_roles(self.role, studyrole, reason="Applying study group role and global studyrole.")
        else:
            await member.add_roles(self.role, reason="Applying study group role.")
        subscriber = TimerSubscriber(self, member.id, member=member)
        if self.state == TimerState.RUNNING:
            subscriber.new_session()

        self.subscribers[member.id] = subscriber

        if post:
            # Send a welcome message
            welcome = "Welcome to **{}**, {}!".format(self.data.name, member.mention)
            welcome += ' ' if self.settings.compact.value else '\n'

            if self.state == TimerState.RUNNING:
                welcome += "Currently on stage **{}** with **{}** remaining. {}".format(
                    self.current_stage.name,
                    self.pretty_remaining,
                    self.current_stage.message
                )
            elif self.state in (TimerState.STOPPED, TimerState.UNSET):
                welcome += (
                    "The group timer is not running. Start it with `{0}start` "
                    "(or `{0}start <pattern>` to use a different timer pattern)."
                ).format(best_prefix(member.guild.id))
            await self.post(welcome)
        return subscriber

    async def unsubscribe(self, userid, post=False):
        """
        Unsubscribe a member from the timer.
        Raises `ValueError` if the user isn't subscribed.
        Returns the old subscriber for session reporting.
        """
        log("Unsubscribing (uid:{}).".format(userid), context="rid:{}".format(self.data.roleid))

        if userid not in self.subscribers:
            raise ValueError("Attempted to unsubscribe a non-existent user!")
        subscriber = self.subscribers.pop(userid)
        subscriber.close_session()

        studyrole = GuildSettings(self.guild.id).studyrole.value
        try:
            # Use a manual request to avoid requiring the member object
            await client.http.remove_role(self.guild.id, userid, self.role.id, reason="Removing study group role.")
            if studyrole:
                await client.http.remove_role(self.guild.id, userid, studyrole.id, reason="Removing global studyrole.")
        except discord.HTTPException:
            pass

        if post:
            await self.post(
                "Goodbye <@{}>! You were subscribed for **{}**.".format(
                    userid, subscriber.pretty_clocked
                )
            )

        return subscriber

    async def update_voice(self):
        """
        Update the name of the associated voice channel.
        """
        if not self.voice_channel or self.voice_channel not in self.guild.channels:
            # Return if there is no associated voice channel
            return
        if self.state != TimerState.RUNNING:
            # Don't update if we aren't running
            return
        if now() - self.last_voice_update < 10 * 60:
            # Return if the last update was less than 10 minutes ago (discord ratelimiting)
            return

        name = self.voice_channel_name

        if name == self.voice_channel.name:
            # Don't update if there are no changes
            return

        log("Updating vc name to {}.".format(name),
            context="rid:{}".format(self.data.roleid),
            level=logging.DEBUG)
        try:
            self.last_voice_update = now()
            await self.voice_channel.edit(name=name)
            self.last_voice_update = now()
        except discord.HTTPException:
            # Nothing we can do
            pass

    async def runloop(self):
        """
        Central runloop.
        Handles firing stage-changes and voice channel updates.
        """
        while self.state == TimerState.RUNNING:
            remaining = self.remaining
            if remaining <= 0:
                try:
                    await self.change_stage(self.stage_index + 1)
                except Exception:
                    log("Exception encountered while changing stage.",
                        context="rid:{}".format(self.role.id),
                        level=logging.ERROR,
                        add_exc_info=True)
            elif remaining > 600 and self.subscribers:
                await self.update_voice()

            self._loop_wait_task = asyncio.create_task(asyncio.sleep(min(600, remaining)))
            try:
                await self._loop_wait_task
            except asyncio.CancelledError:
                pass

    def serialise(self):
        return {
            'roleid': self.data.roleid,
            'state': self.state.value,
            'patternid': self.current_pattern.row.patternid if self.current_pattern else None,
            'stage_index': self.stage_index,
            'stage_start': self.stage_start,
            'message_ids': self.message_ids,
            'subscribers': [subber.serialise() for subber in self.subscribers.values()],
            'last_voice_update': self.last_voice_update
        }

    def restore_from(self, data):
        log("Restoring Timer (rid:{}).".format(data['roleid']), context='TIMER_RESTORE')
        self.stage_index = data['stage_index']
        self.stage_start = data['stage_start']
        self.state = TimerState(data['state'])
        self.current_pattern = Pattern.get(data['patternid'] if data['patternid'] is not None else self.patternid)
        self.message_ids = data['message_ids']
        self.last_voice_update = data['last_voice_update']

        self.subscribers = {}
        for sub_data in data['subscribers']:
            subber = TimerSubscriber(self, sub_data['userid'], name=sub_data['name'])
            subber.restore_from(sub_data)
            self.subscribers[sub_data['userid']] = subber

        asyncio.create_task(self.runloop())


class TimerChannel:
    """
    Represents a discord text channel holding one or more timers.

    Manages the pinned update message.
    """
    __slots__ = (
        'channel',
        'timers',
        'pinned_msg',
        'pinned_msg_id',
        'previous_desc',
        'failure_count'
    )

    def __init__(self, channel):
        self.channel: discord.TextChannel = channel

        self.timers = []
        self.pinned_msg = None
        self.pinned_msg_id = None

        self.previous_desc = ''

        self.failure_count = 0

    async def update_pin(self, force=False):
        if not force and self.failure_count > 5:
            return

        if self.channel not in self.channel.guild.channels:
            return

        if self.pinned_msg is None and self.pinned_msg_id is not None:
            try:
                self.pinned_msg = await self.channel.fetch_message(self.pinned_msg_id)
            except discord.HTTPException:
                self.pinned_msg_id = None

        desc = '\n\n'.join(timer.pinstatus for timer in self.timers)
        if desc and desc != self.previous_desc:
            self.previous_desc = desc

            # Build embed
            embed = discord.Embed(
                title="Pomodoro Timer Status",
                description=desc,
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="Last Updated")

            if self.pinned_msg is not None:
                try:
                    await self.pinned_msg.edit(embed=embed)
                except discord.NotFound:
                    self.pinned_msg = None
                except discord.HTTPException:
                    # An obscure permission error or discord dying?
                    self.failure_count += 1
                    return
            elif force or all(timer.state != TimerState.STOPPED for timer in self.timers):
                # Attempt to generate a new pinned message
                try:
                    self.pinned_msg = await self.channel.send(embed=embed)
                except discord.Forbidden:
                    # We can't send embeds, or maybe any messages?
                    # First stop the timers, then try to report the error
                    self.failure_count = 100
                    for timer in self.timers:
                        timer.stop()

                    perms = self.channel.permissions_for(self.channel.guild.me)
                    if perms.send_messages and not perms.embed_links:
                        try:
                            await self.channel.send(
                                "I require the `embed links` permission in this channel! Timers stopped."
                            )
                        except discord.HTTPException:
                            # Nothing we can do...
                            pass
                    return

                # Now attempt to pin the message
                try:
                    await self.pinned_msg.pin()
                except discord.Forbidden:
                    await self.channel.send(
                        "I don't have the `manage messages` permission required to pin the channel status message! "
                        "Please pin the message manually."
                    )
                except discord.HTTPException:
                    pass

    def serialise(self):
        return {
            'channelid': self.channel.id,
            'pinned_msg_id': self.pinned_msg.id if self.pinned_msg else None,
            'timers': [timer.serialise() for timer in self.timers]
        }

    def restore_from(self, data):
        log("Restoring Timer Channel (cid:{}).".format(data['channelid']), context='TIMER_RESTORE')
        self.pinned_msg_id = data['pinned_msg_id']

        timers = {timer.data.roleid: timer for timer in self.timers}
        for timer_data in data['timers']:
            timer = timers.get(timer_data['roleid'], None)
            if timer is not None:
                timer.restore_from(timer_data)


class TimerSubscriber:
    """
    Represents a member subscribed to a timer.
    """
    __slots__ = (
        'timer',
        'userid',
        '_name',
        'member',
        '_fetch_task',
        'subscribed_at',
        'last_seen',
        'warnings',
        'clocked_time',
        'session_started',
        'session',
    )

    def __init__(self, timer: Timer, userid, member=None, name=None):
        self.timer = timer  # Timer the member is subscribed to
        self.userid = userid  # Discord userid
        self.member = member  # Discord member object, if provided

        self._name = name  # Backup name used when there is no member object
        self._fetch_task = None  # Potential asyncio.Task for fetching the member object

        self.last_seen = now()  # Last seen, for activity tracking
        self.warnings = 0  # Current number of warnings
        self.clocked_time = 0  # Total clocked session time in this subscription (in seconds)

        self.session_started = None
        self.session = None

        if self.member and self.member.name != self.user_data.name:
            self.user_data.name = self.member.name

    @property
    def name(self):
        """
        Name of the member.
        May be retrieved from `_name` if the member doesn't exist yet.
        """
        return self.member.display_name if self.member else self._name or 'Unknown'

    @property
    def user_data(self):
        return tables.users.fetch_or_create(self.userid)

    @property
    def notify_level(self):
        raw = self.user_data.notify_level
        return NotifyLevel(raw) if raw is not None else NotifyLevel.WARNING

    @property
    def pretty_clocked(self):
        return parse_dur(self.clocked_time, True)

    @property
    def unsaved_time(self):
        """
        Clocked time not yet saved in a session.
        """
        return (now() - self.session_started) if self.session else 0

    def touch(self):
        """
        Update `last_seen`, and reset warning count.
        """
        self.last_seen = now()
        self.warnings = 0

    async def _fetch_member(self):
        try:
            self.member = await self.timer.guild.fetch_member(self.userid)
            if self.member.name != self.user_data.name:
                self.user_data.name = self.member.name
        except discord.HTTPException:
            pass

    async def send(self, *args, **kwargs):
        if self.member:
            await self.member.send(*args, **kwargs)
        else:
            if self._fetch_task is None:
                self._fetch_task = asyncio.create_task(self._fetch_member())
            if not self._fetch_task.done():
                try:
                    await self._fetch_task
                except asyncio.CancelledError:
                    pass
                await self.send(*args, **kwargs)

    def set_member(self, member):
        """
        Set the member for this subscriber, if unset.
        """
        if not self.member and member.id == self.userid:
            self.member = member
            if self.member.name != self.user_data.name:
                self.user_data.name = self.member.name

            if self._fetch_task:
                if self._fetch_task.done():
                    self._fetch_task = None
                else:
                    self._fetch_task.cancel()

    def new_session(self):
        """
        Start a new session for this subscriber.
        Requires the timer to be setup.
        Typically called after subscription or timer start.
        """
        # Close any existing session
        self.close_session()

        # Initialise the new session
        self.session_started = now()
        self.session = [(0, 0) for stage in self.timer.current_pattern]

        # Apply the initial join shift
        if self.timer.state == TimerState.RUNNING:
            shift = self.timer.stage_start - self.session_started
            self.session[self.timer.stage_index] = (0, shift)

    def close_session(self):
        """
        Save and close the current session, if any.
        This may occur upon unsubscribing or stopping/pausing the timer.
        """
        if self.session:
            _now = now()

            # Final shift
            if self.timer.state == TimerState.RUNNING:
                shift = _now - self.timer.stage_start
                count, current_shift = self.session[self.timer.stage_index]
                self.session[self.timer.stage_index] = (count, current_shift + shift)

            # Save session
            duration = _now - self.session_started
            focused_duration = sum(
                t[0] * stage.duration * 60 + t[1]
                for t, stage in zip(self.session, self.timer.current_pattern)
                if stage.focus
            )
            # Don't save if the session was under a minute
            if duration > 60:
                tables.sessions.insert(
                    guildid=self.timer.guild.id,
                    userid=self.userid,
                    roleid=self.timer.role.id,
                    start_time=self.session_started,
                    duration=duration,
                    focused_duration=focused_duration,
                    patternid=self.timer.current_pattern.row.patternid,
                    stages=json.dumps(self.session)
                )

            # Update clocked time
            self.clocked_time += duration

            # Reset session state
            self.session_started = None
            self.session = None

    def stage_finished(self, stageid):
        """
        Finish a stage, adding it to the running session
        """
        count, shift = self.session[stageid]
        self.session[stageid] = count + 1, shift

    def stage_shift(self, stageid, diff):
        """
        Shift a stage (i.e. move the stage start forwards by `shift`, temporarily increasing the stage length).
        """
        count, shift = self.session[stageid]
        self.session[stageid] = count, shift + diff

    def serialise(self):
        return {
            'userid': self.userid,
            'timerid': self.timer.role.id,
            'session_started': self.session_started,
            'session': self.session,
            'name': self.name
        }

    def restore_from(self, data):
        log("Restoring Subscriber (uid:{}).".format(data['userid']), context='TIMER_RESTORE')
        self.session_started = data['session_started']
        self.session = data['session']
