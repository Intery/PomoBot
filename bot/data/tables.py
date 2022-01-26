from .data import RowTable, Table

from cachetools import LFUCache
from weakref import WeakValueDictionary


guilds = RowTable(
    'guilds',
    ('guildid', 'timer_admin_roleid', 'show_tips',
     'autoclean', 'timezone', 'prefix', 'globalgroups', 'studyrole_roleid'),
    'guildid',
    cache_size=2500
)

users = RowTable(
    'users',
    ('userid', 'notify_level', 'timezone', 'name'),
    'userid',
    cache_size=2000
)

patterns = RowTable(
    'patterns',
    ('patternid', 'short_repr', 'stage_str', 'created_at'),
    'patternid',
    cache=LFUCache(1000)
)

timers = RowTable(
    'timers',
    ('roleid', 'guildid', 'name', 'channelid', 'patternid',
     'voice_channelid', 'voice_alert', 'track_voice_join', 'track_voice_leave',
     'auto_reset', 'admin_locked', 'track_role', 'compact',
     'voice_channel_name',
     ),
    # 'default_work_name', 'default_work_message',
    # 'default_break_name', 'default_break_message'),
    'roleid',
    cache=WeakValueDictionary()
)
sessions = Table('sessions')
session_patterns = Table('session_patterns')
timer_pattern_history = Table('timer_pattern_history')

user_presets = Table('user_presets')
guild_presets = Table('guild_presets')
