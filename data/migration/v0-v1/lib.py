from collections import namedtuple
import datetime
import json
import pytz


class Base:
    __slots__ = ()

    def __init__(self, **kwargs):
        for prop in self.__slots__:
            setattr(self, prop, kwargs.get(prop, None))


class Guild(Base):
    __slots__ = (
        'guildid',
        'timer_admin_roleid',
        'globalgroups',
        'presets',
    )


class Timer(Base):
    __slots__ = (
        'roleid',
        'guildid',
        'name',
        'channelid',
        'voice_channelid'
    )


Stage = namedtuple('Stage', ('name', 'duration', 'message', 'focus'))


class Pattern(Base):
    __slots__ = (
        'stages',
        'patternid',
        'stage_str'
    )

    pattern_cache = {}  # pattern_str -> id
    lastid = 0

    @classmethod
    def parse(cls, string):
        """
        Parse a setup string into a pattern
        """
        # Accepts stages as 'name, length' or 'name, length, message'
        stage_blocks = string.strip(';').split(';')
        stages = []
        for block in stage_blocks:
            # Extract stage components
            parts = block.split(',', maxsplit=2)
            if len(parts) == 2:
                name, dur = parts
                message = None
            else:
                name, dur, message = parts

            # Parse duration
            dur = dur.strip()
            focus = dur.startswith('*') or dur.endswith('*')
            if focus:
                dur = dur.strip('* ')

            # Build and add stage
            stages.append(Stage(name.strip(), int(dur), (message or '').strip(), focus))

        stage_str = json.dumps(stages)
        if stage_str in cls.pattern_cache:
            pattern = cls.pattern_cache[stage_str]
        else:
            cls.lastid += 1
            pattern = cls(stages=stages, patternid=cls.lastid, stage_str=stage_str)
            cls.pattern_cache[stage_str] = pattern

        return pattern


class Preset(Base):
    __slots__ = (
        'name',
        'patternid',
    )


class User(Base):
    __slots__ = (
        'userid',
        'notify_level',
        'presets'
    )


time_diff = (
    int(datetime.datetime.now(tz=pytz.utc).timestamp())
    - int(datetime.datetime.timestamp(datetime.datetime.utcnow()))
)
def adjust_timestamp(ts):
    return ts + time_diff
