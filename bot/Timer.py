import time
import asyncio
import datetime
import discord
from enum import Enum


class Timer(object):
    def __init__(self, name, role, channel, statuschannel, stages=None):
        self.channel = channel
        self.statuschannel = statuschannel
        self.role = role
        self.name = name

        self.start_time = None  # Session start time
        self.current_stage_start = None  # Time at which the current stage started
        self.remaining = None  # Amount of time until the next stage starts
        self.state = TimerState.STOPPED  # Current state of the timer

        self.stages = stages  # List of stages in this timer
        self.current_stage = 0  # Index of current stage

        self.subscribed = {}  # Dict of subbed members, userid maps to (user, lastupdate, timesubbed)

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
        self.state = TimerState.STOPPED

        self.stages = stages
        self.current_stage = 0

        self.start_time = int(time.time())

        self.remaining = stages[0].duration
        self.current_stage_start = int(time.time())

        # Return self for method chaining
        return self

    async def update_statuschannel(self):
        """
        Try to update the name of the status channel with the current status
        """
        # Quit if there's no status channel set
        if self.statuschannel is None:
            return

        # Get the name and time strings
        stage_name = self.stages[self.current_stage].name
        remaining_time = self.pretty_remaining()

        # Update the channel name, or quit silently if something goes wrong.
        try:
            await self.statuschannel.edit(name="{} - {}".format(stage_name, remaining_time))
        except Exception:
            pass

    def pretty_remaining(self):
        """
        Return a formatted version of the time remaining until the next stage.
        """
        diff = int(60*self.stages[self.current_stage].duration - (time.time() - self.current_stage_start))
        diff = max(diff, 0)
        hours = diff // 3600
        minutes = (diff % 3600) // 60
        seconds = diff % 60

        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

    def pretty_pinstatus(self):
        """
        Return a formatted status string for use in the pinned status message.
        """
        if self.state in [TimerState.RUNNING, TimerState.PAUSED]:
            # Collect the component strings and data
            current_stage_name = self.stages[self.current_stage].name
            remaining = self.pretty_remaining()

            subbed_names = [m[0].name for m in self.subscribed.values()]
            subbed_str = "```{}```".format(", ".join(subbed_names)) if subbed_names else "*No subscribers*"

            # Create a list of lines for the stage string
            longest_stage_len = max(len(stage.name) for stage in self.stages)
            stage_format = "`{{prefix}}{{name:>{}}}:` {{dur}} min  {{current}}".format(longest_stage_len)

            stage_str_lines = [
                stage_format.format(
                    prefix="▶️" if i == self.current_stage else "​ ",
                    name=stage.name,
                    dur=stage.duration,
                    current="(**{}**)".format(remaining) if i == self.current_stage else ""
                ) for i, stage in enumerate(self.stages)
            ]
            # Create the stage string itself
            stage_str = "\n".join(stage_str_lines)

            # Create the final formatted status string
            status_str = ("**{name}** ({current_stage_name}){paused}\n"
                          "{stage_str}\n"
                          "{subbed_str}").format(name=self.name,
                                                 paused=" ***Paused***" if self.state==TimerState.PAUSED else "",
                                                 current_stage_name=current_stage_name,
                                                 stage_str=stage_str,
                                                 subbed_str=subbed_str)
        elif self.state == TimerState.STOPPED:
            status_str = "**{}**: *Not set up.*".format(self.name)
        return status_str

    def pretty_summary(self):
        """
        Return a one line summary status message.
        """
        pass

    async def change_stage(self, stage_index, notify=True, inactivity_check=True, report_old=True):
        """
        Advance the timer to the new stage.
        """
        stage_index = stage_index % len(self.stages)
        current_stage = self.stages[self.current_stage]
        new_stage = self.stages[stage_index]

        # Handle notifications
        if notify:
            old_stage_str = "**{}** finished! ".format(current_stage.name) if report_old else ""
            out_msg = await self.channel.send(
                ("{}\n{}Starting **{}** ({} minutes). {}\n"
                 "Please react to this message to register your presence!").format(
                     self.role.mention,
                     old_stage_str,
                     new_stage.name,
                     new_stage.duration,
                     new_stage.message
                 )
            )
            try:
                await out_msg.add_reaction("✅")
            except Exception:
                pass

        self.current_stage = stage_index
        self.current_stage_start = int(time.time())
        self.remaining = self.stages[stage_index].duration * 60

        # Handle inactivity
        pass

    async def start(self):
        """
        Start or restart the timer.
        """
        await self.change_stage(0, report_old=False)
        self.state = TimerState.RUNNING
        asyncio.ensure_future(self.runloop())

    async def runloop(self):
        while self.state == TimerState.RUNNING:
            self.remaining = int(60*self.stages[self.current_stage].duration - (time.time() - self.current_stage_start))
            if self.remaining <= 0:
                await self.change_stage(self.current_stage + 1)

            await self.update_statuschannel()
            await asyncio.sleep(5)

    async def sub(self, ctx, user):
        """
        Subscribe a new user to this timer list.
        """
        # Attempt to add the sub role
        try:
            await user.add_roles(self.role)
        except discord.Forbidden:
            await ctx.error_reply("Insufficient permissions to add the group role `{}`.".format(self.role.name))
        except discord.NotFound:
            await ctx.error_reply("Group role `{}` doesn't exist! This group is broken.".format(self.role.id))

        self.subscribed[user.id] = (user, time.time(), 0)


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
    __slots__ = ('channel', 'timers', 'msg')

    def __init__(self, channel):
        self.channel = channel

        self.timers = []
        self.msg = None


async def update_channel(client, tchan):
    """
    Update status message in the provided channel.

    Arguments
    ---------
    client: discord.Client
        The client to use to edit the message.
    tchan: TimerChannel
        The timer channel to update.
    """
    messages = [timer.pretty_pinstatus() for timer in tchan.timers]
    if messages:
        desc = "\n\n".join(messages)
        embed = discord.Embed(
            title="Pomodoro Timer Status",
            description=desc,
            timestamp=datetime.datetime.now()
        )
        if tchan.msg is not None:
            try:
                await tchan.msg.edit(embed=embed)
            except Exception:
                pass
        else:
            # Attempt to generate a new message
            try:
                tchan.msg = await tchan.channel.send(embed=embed)
            except discord.Forbidden:
                await tchan.channel.send("I need permission to send embeds in this channel! Stopping all timers.")
                for timer in tchan.timers:
                    timer.state = TimerState.STOPPED

            # Pin the message
            try:
                await tchan.msg.pin()
            except Exception:
                pass



def create_timer(client, name, role, channel, statuschannel):
    """
    Helper to create a new timer, add it to the caches, and save it to disk.
    """
    # Create the new timer
    new_timer = Timer(name, role, channel, statuschannel)

    # Get the list of timer channels associated to the current guild
    guild_channels = client.objects["timer_channels"].get(channel.guild.id)
    if guild_channels is None:
        guild_channels = {}
        client.objects["timer_channels"][channel.guild.id] = guild_channels

    # Add the new timer to the appropriate timer channel, creating if needed
    if channel.id in guild_channels:
        guild_channels[channel.id].timers.append(new_timer)
    else:
        tchan = TimerChannel(channel)
        tchan.timers.append(new_timer)

        guild_channels[channel.id] = tchan

    # Store the new timer in guild config
    channels = client.config.guilds.get(channel.guild.id, "timers") or []
    channels.append((name, role.id, channel.id, statuschannel.id))
    client.config.guilds.set(channel.guild.id, "timers", channels)


def del_timer(client, timer):
    """
    Helper to delete a timer, both from caches and data.
    """
    guild = timer.channel.guild
    tchan = client.objects["timer_channels"].get(guild.id, {}).get(timer.channel.id, None)

    if tchan is not None:
        tchan.timers.remove(timer)

    channels = client.config.guilds.get(channel.guild.id, "timers")
    channels.remove((timer.name, timer.role.id, timer.channel.id, timer.satuschannel.id))
    client.config.guilds.set(channel.guild.id, "timers", channels)

def get_tchan(ctx):
    """
    Gets the timer channel for the current channel, or None if it doesn't exist.
    """
    return ctx.client.objects["timer_channels"].get(ctx.guild.id, {}).get(ctx.ch.id, None)

def get_timer_for(ctx, user):
    """
    Get the timer this user is subscribed to (in the current guild), or None if it doesn't exist.
    """
    guild_tchans = ctx.client.objects["timer_channels"].get(ctx.guild.id, None)
    if guild_tchans is not None:
        return next((timer for tchan in guild_tchans.values() for timer in tchan.timers if user.id in timer), None)


async def timer_controlloop(client):
    """
    Global timer loop.
    Handles updating status messages across all active timer channels.
    """
    while True:
        for tchans in client.objects["timer_channels"].values():
            for tchan in tchans.values():
                if any(timer.state == TimerState.RUNNING for timer in tchan.timers):
                    asyncio.ensure_future(update_channel(client, tchan))
        await asyncio.sleep(2)


async def load_timers(client):
    # Get the guilds with active timers
    timed_guilds = client.config.guilds.find_not_empty("timers")
    for guildid in timed_guilds:
        guild_channels = {}

        guild = client.get_guild(guildid)
        if guild is None:
            continue

        # Get the corresponding timers
        raw_timers = client.config.guilds.get(guildid, "timers")
        for name, roleid, channelid, statuschannelid in raw_timers:
            # Get the objects corresponding to the ids
            role = guild.get_role(roleid)
            channel = guild.get_channel(channelid)
            statuschannel = guild.get_channel(statuschannelid)

            if role is None or channel is None or statuschannel is None:
                # This timer doesn't exist
                # TODO: Handle garbage collection
                continue

            # Create the new timer
            new_timer = Timer(name, role, channel, statuschannel)

            # Add it to the timer channel, creating if required
            tchan = guild_channels.get(channelid, None)
            if tchan is None:
                tchan = TimerChannel(channel)
                guild_channels[channelid] = tchan
            tchan.timers.append(new_timer)
        client.objects["timer_channels"][guildid] = guild_channels


async def activity_tracker_message(client, message):
    if message.guild.id in client.objects["timer_channels"]:
        if message.channel.id in client.objects["timer_channels"][message.guild.id]:
            client.objects["user_activity"][message.author.id] = time.time()


async def activity_tracker_reaction(client, reaction, user):
    message = reaction.message
    if message.guild.id in client.objects["timer_channels"]:
        if message.channel.id in client.objects["timer_channels"][message.guild.id]:
            client.objects["user_activity"][user.id] = time.time()


def initialise(client):
    # Ensure required config entries exist
    client.config.guilds.ensure_exists("timers")

    # Load timers from database
    client.objects["timer_channels"] = {}
    client.add_after_event("ready", load_timers)

    # Track user activity in timer channels
    client.objects["user_activity"] = {}
    client.add_after_event("message", activity_tracker_message)
    client.add_after_event("reaction_add", activity_tracker_reaction)

    # Start the loop
    client.add_after_event("ready", timer_controlloop, 10)

