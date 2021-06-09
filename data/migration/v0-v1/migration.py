import os
import json
import configparser as cfgp
import pickle

import sqlite3 as sq

import lib


CONFFILE = "migration.conf"
DATA_DIR = "../../"

# Read config file
print("Reading configuration file...", end='')
if not os.path.isfile(CONFFILE):
    raise Exception(
        "Couldn't find migration configuration file '{}'. "
        "Please copy 'sample-migration.conf' to 'migration.conf' and edit as required."
    )

config = cfgp.ConfigParser()
config.read(CONFFILE)

orig_settings_path = DATA_DIR + config['Original']['settings_db']
orig_session_path = DATA_DIR + config['Original']['session_db']
if config['Original']['savefile'].lower() != 'none':
    orig_savefile_path = DATA_DIR + config['Original']['savefile']
else:
    orig_savefile_path = None

target_database_path = DATA_DIR + config['Target']['database']
if config['Target']['savefile'] .lower() != 'none':
    target_savefile_path = DATA_DIR + config['Target']['savefile']
else:
    target_savefile_path = None

if not os.path.isfile(orig_session_path):
    raise Exception("Provided original sessions database not found.")
if not os.path.isfile(orig_settings_path):
    raise Exception("Provided original settings database not found.")
if orig_savefile_path is not None and not os.path.isfile(orig_savefile_path):
    raise Exception("Provided original savefile not found.")
if os.path.isfile(target_database_path):
    raise Exception("Target database file already exists! Refusing to overwrite.")

print("Done")

# Open databases
print("Opening databases...", end='')
orig_session_conn = sq.connect(orig_session_path)
orig_settings_conn = sq.connect(orig_settings_path)
target_database_conn = sq.connect(target_database_path)
print("Done")

# Initialise the new database
print("Initialising target database...", end='')
with target_database_conn as conn:
    with open("v1_schema.sql", 'r') as script:
        conn.executescript(script.read())
print("Done")


# ----------------------------------------------------
# Initial setup done, start migration
# ----------------------------------------------------
guilds = {}
timers = {}
users = {}


# Migrate guild properties
# First read properties
count = 0
with orig_settings_conn as conn:
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM guilds"
    )
    for guildid, prop, value in cursor.fetchall():
        count += 1
        if guildid not in guilds:
            guild = guilds[guildid] = lib.Guild(guildid=guildid, presets={})
        else:
            guild = guilds[guildid]

        if prop == 'timeradmin':
            guild.timer_admin_roleid = json.loads(value)
        elif prop == 'globalgroups':
            guild.globalgroups = json.loads(value)
        elif prop == 'timers':
            timer_list = json.loads(value)
            if timer_list:
                for name, roleid, channelid, vc_channelid in timer_list:
                    timer = lib.Timer(
                        roleid=roleid,
                        guildid=guildid,
                        name=name,
                        channelid=channelid,
                        voice_channelid=vc_channelid
                    )
                    timers[roleid] = timer
        elif prop == 'timer_presets':
            presets = json.loads(value)
            if presets:
                for name, setupstr in presets.items():
                    pattern = lib.Pattern.parse(setupstr)
                    while name.lower() in guild.presets:
                        name += '_'
                    guild.presets[name.lower()] = lib.Preset(name=name, patternid=pattern.patternid)
print("Read {} guild properties.".format(count))

# Insert the guild rows
with target_database_conn as conn:
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO guilds (guildid, timer_admin_roleid, globalgroups) VALUES (?, ?, ?)",
        (
            (guildid, guild.timer_admin_roleid, guild.globalgroups)
            for guildid, guild in guilds.items()
        )
    )
print("Inserted {} guilds.".format(len(guilds)))

# Insert the timer rows
with target_database_conn as conn:
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO timers (roleid, guildid, name, channelid, voice_channelid) VALUES (?, ?, ?, ?, ?)",
        (
            (timer.roleid, timer.guildid, timer.name, timer.channelid, timer.voice_channelid)
            for timer in timers.values()
        )
    )
print("Inserted {} timers.".format(len(timers)))


# Read user properties
count = 0
with orig_settings_conn as conn:
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM users"
    )
    for userid, prop, value in cursor.fetchall():
        count += 1
        if userid not in users:
            user = users[userid] = lib.User(userid=userid, presets={})
        else:
            user = users[userid]

        if prop == 'notify_level':
            user.notify_level = json.loads(value)
        elif prop == 'timer_presets':
            presets = json.loads(value)
            if presets:
                for name, setupstr in presets.items():
                    pattern = lib.Pattern.parse(setupstr)
                    while name.lower() in user.presets:
                        name += '_'
                    user.presets[name.lower()] = lib.Preset(name=name, patternid=pattern.patternid)
print("Read {} user properties.".format(count))


# Insert the user rows
with target_database_conn as conn:
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO users (userid, notify_level) VALUES (?, ?)",
        (
            (userid, user.notify_level)
            for userid, user in users.items()
        )
    )
print("Inserted {} users.".format(len(users)))


# Migrate savedata
save_data = {}
if orig_savefile_path:
    with open(orig_savefile_path) as f:
        old_data = json.load(f)
        flat_timers = old_data['timers']
        flat_subscribers = old_data['subscribers']
        flat_channels = old_data['timer_channels']

    channels = {}
    for channel in flat_channels:
        channel_data = {}
        channel_data['channelid'] = channel['id']
        channel_data['pinned_msg_id'] = channel['msgid']
        channel_data['timers'] = []
        channels[channel['id']] = channel_data

    for timer in flat_timers:
        timer_data = {}

        if timer['stages']:
            stages = [
                lib.Stage(stage['name'], stage['duration'], stage['message'], False)
                for stage in timer['stages']
            ]
            stage_str = json.dumps(stages)
            if stage_str in lib.Pattern.pattern_cache:
                pattern = lib.Pattern.pattern_cache[stage_str]
            else:
                lib.Pattern.lastid += 1
                pattern = lib.Pattern(stages=stages, patternid=lib.Pattern.lastid, stage_str=stage_str)
                lib.Pattern.pattern_cache[stage_str] = pattern
            patternid = pattern.patternid
        else:
            patternid = 0
        timer_data['roleid'] = timer['roleid']
        timer_data['state'] = timer['state']
        timer_data['patternid'] = patternid
        timer_data['stage_index'] = timer['current_stage'] or 0
        timer_data['stage_start'] = lib.adjust_timestamp(timer['current_stage_start'] or 0)
        timer_data['message_ids'] = timer['messages']
        timer_data['subscribers'] = []
        timer_data['last_voice_update'] = 0

        _timer = timers[timer['roleid']]
        if _timer:
            timer_data['guildid'] = _timer.guildid
            if _timer.channelid not in channels:
                channels[_timer.channelid] = {
                    'channelid': _timer.channelid,
                    'pinned_msg_id': None,
                    'timers': [],
                }
            channels[_timer.channelid]['timers'].append(timer_data)

        for channelid, channel in channels.items():
            if channel['timers']:
                guildid = channel['timers'][0]['guildid']
                if guildid not in save_data:
                    guild_channels = save_data[guildid] = []
                else:
                    guild_channels = save_data[guildid]
                guild_channels.append(channel)
print("Read and parsed old savefile.")


# Write patterns
with target_database_conn as conn:
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO patterns (patternid, short_repr, stage_str) VALUES (?, ?, ?)",
        (
            (pattern.patternid, False, pattern.stage_str)
            for pattern in lib.Pattern.pattern_cache.values()
        )
    )
print("Created {} patterns.".format(len(lib.Pattern.pattern_cache)))


# Write user presets
with target_database_conn as conn:
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO user_presets (userid, patternid, preset_name) VALUES (?, ?, ?)",
        (
            (userid, preset.patternid, preset.name)
            for userid, user in users.items()
            for preset in user.presets.values()
        )
    )
print("Transferred user presets.")


# Write guild presets
with target_database_conn as conn:
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO guild_presets (guildid, patternid, preset_name, created_by) VALUES (?, ?, ?, ?)",
        (
            (guildid, preset.patternid, preset.name, 0)
            for guildid, guild in guilds.items()
            for preset in guild.presets.values()
        )
    )
print("Transferred guild presets.")


# Write new save file, if required
if target_savefile_path:
    with open(target_savefile_path, 'wb') as savefile:
        pickle.dump(save_data, savefile, pickle.HIGHEST_PROTOCOL)
    print("Written new save file.")


# Transfer the session data
print("Migrating session data....", end='')
with orig_session_conn as conn:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sessions"
    )
    with target_database_conn as tconn:
        tcursor = tconn.cursor()
        tcursor.executemany(
            "INSERT INTO sessions (guildid, userid, roleid, start_time, duration) VALUES (?, ?, ?, ?, ?)",
            (
                (row[1], row[0], row[2], lib.adjust_timestamp(row[3]), row[4])
                for row in cursor.fetchall()
                if row[4] > 60
            )
        )
print("Done")

print("Data migration v0 -> v1 complete!")
