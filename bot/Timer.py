import time
import asyncio
import datetime
import discord
from enum import Enum


class Timer(object):
    def __init__(self, ctx, channel, group_name, group_role, stages, statuschannel=None):
        self.ctx = ctx
        self.channel = channel
        self.statuschannel = statuschannel
        self.group_role = group_role
        self.group_name = group_name

        self.start_time = int(time.time())  # Session start time
        self.current_stage_start = 0  # Time at which the current stage started
        self.remaining = stages[0].duration  # Amount of time until the next stage starts
        self.state = TimerState.STOPPED  # Current state of the timer

        self.stages = stages  # List of stages in this timer
        self.current_stage = 0  # Index of current stage

        self.subscribed = []  # List of subscribed members

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
        diff = self.remaining
        hours = diff // 3600
        minutes = (diff % 3600) // 60
        seconds = diff % 60

        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

    def pretty_pinstatus(self):
        """
        Return a formatted status string for use in the pinned status message.
        """
        # Collect the component strings and data
        current_stage_name = self.stages[self.current_stage].name
        remaining = self.pretty_remaining()

        subbed_names = [m.name for m in self.subscribed]
        subbed_str = "```{}```".format(", ".join(subbed_names)) if subbed_names else "No subscribers!"

        # Create a list of lines for the stage string
        longest_stage_len = max(len(stage.name) for stage in self.stages)
        stage_format = "`{{prefix}}{{name:>{}}}:` {{dur}} min  {{current}}".format(longest_stage_len)

        stage_str_lines = [
            stage_format.format(
                prefix="▶️" if i == self.current_stage else "-",
                name=stage.name,
                dur=stage.duration,
                current="(**{}**)".format(remaining) if i == self.current_stage else ""
            ) for i, stage in enumerate(self.stages)
        ]
        # Create the stage string itself
        stage_str = "\n".join(stage_str_lines)

        # Create the final formatted status string
        status_str = ("**{group_name}** ({current_stage_name})\n"
                      "{stage_str}\n"
                      "{subbed_str}").format(group_name=self.group_name,
                                             current_stage_name=current_stage_name,
                                             stage_str=stage_str,
                                             subbed_str=subbed_str)
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
        # Handle notifications
        if notify:
            old_stage_str = "**{}** finished! ".format(self.stages[self.current_stage].name)
            out_msg = await self.channel.send(
                ("{}\n{}Starting **{}** ({} minutes).\n"
                 "Please react to this message to register your presence!").format(
                     self.group_role.mention,
                     old_stage_str,
                     self.stages[stage_index].name,
                     self.stages[stage_index].duration
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
            await asyncio.sleep(3)


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
    focus_mode: bool
        Whether the `focus mode` modifier is set for this stage.
    modifiers: Dict(str, bool)
        An unspecified collection of stage modifiers, stored for external user.
    """
    __slots__ = ('name', 'duration', 'focus_mode', 'modifiers')

    def __init__(self, name, duration, **modifiers):
        self.name = name
        self.duration = duration

        self.focus_mode = modifiers.get("focus_mode", False)
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
        Must have a current `msg` in order to update, this will not be generated.
    """
    messages = [timer.pretty_pinstatus() for timer in tchan.timers if timer.state == TimerState.RUNNING]
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


async def timer_controlloop(client):
    """
    Global timer loop.
    Handles updating status messages across all active timer channels.
    """
    # Dictionary of timer channels, {chanid: TimerChannel}
    client.objects["timer_channels"] = {}

    while True:
        for _, tchan in client.objects["timer_channels"].items():
            asyncio.ensure_future(update_channel(client, tchan))

        await asyncio.sleep(2)
