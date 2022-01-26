from enum import IntEnum

from cmdClient.lib import SafeCancellation

from meta import client
from data import tables
from utils.lib import timestamp_utcnow as now  # noqa


join_emoji = '✅'
leave_emoji = '❌'


def parse_dur(diff, show_seconds=False):
    """
    Parse a duration given in seconds to a time string.
    """
    diff = max(diff, 0)
    if show_seconds:
        hours = diff // 3600
        minutes = (diff % 3600) // 60
        seconds = diff % 60
        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
    else:
        diff = int(60 * round(diff / 60))
        hours = diff // 3600
        minutes = (diff % 3600) // 60
        return "{:02d}:{:02d}".format(hours, minutes)


def best_prefix(guildid):
    if not guildid:
        return client.prefix
    else:
        return tables.guilds.fetch_or_create(guildid).prefix or client.prefix


class TimerState(IntEnum):
    """
    Enum representing the current running state of the timer.

    Values
    ------
    UNSET: The timer isn't set up.
    STOPPED: The timer is stopped.
    RUNNING: The timer is running.
    PAUSED: The timer has been paused.
    """

    UNSET = 0
    STOPPED = 1
    RUNNING = 2
    PAUSED = 3


class NotifyLevel(IntEnum):
    """
    Enum representing a subscriber's notification level.
    NONE: Never send direct messages.
    FINAL: Send a direct message when kicking for inactivity.
    WARNING: Send direct messages for unsubscription warnings.
    ALL: Send direct messages for all stage updates.
    """
    NEVER = 1
    FINAL = 2
    WARNING = 3
    ALL = 4


class InvalidPattern(SafeCancellation):
    """
    Exception raised when an invalid pattern format is encountered.
    Stores user-readable information about the pattern error.
    """
    pass
