# Data migration from version 0 to version 1

## Summary
Version 1 represents a paradigm shift in how PomoBot's data is stored.
In particular, all user and guild properties are moving into appropriate tables, and the sessions database is merging with the properties database.
Timers now also have configuration properties, and Timer patterns are stored in the database, with presets referencing the central pattern table.
Several views are being added to simplify analysis of the data, both internally and via external programs or services.


## Instructions
Copy `sample-migration.conf` to `migration.conf` and edit the data paths as required. Then run `migration.py`.

## Object migration notes
### Guilds
Originally stored in the `guilds` and `guild_props` tables, guild properties have been split into appropriate tables.
- `timeradmin` property -> `guilds.timer_admin_roleid`
    - Straightforward transfer, integer type
- `globalgroups` property -> `guilds.globalgroups`
    - Straightforward transfer, boolean type
- `timers` property -> `timers` table
    - Originally a json-encoded list of timer data, with each timer encoded as a tuple `[name, roleid, channelid, clock_channelid]`.
    - Now each timer is encoded in its own row in `timers`, with each tuple-field given its own column.
    - Each new `timer` also holds considerably more data due to the new configuration.
- `timer_presets` property -> `guild_presets` table
    - Originally a json-encoded dictionary of the form `presetname: setupstring`.
    - Each preset is now given by a single row of `guild_presets`.
    - Setupstrings are stored in `patterns` as their associated patterns, and referred to by `patternid`.

### Users
Originally stored in the `users` and `user_props` tables, user properties have been split into appropriate tables.
- `notify_level` property -> `users.notify_level`
    - Straightforward transfer, integer (enum data) type.
- `timer_presets` property -> `user_presets` table
    - Originally a json-encoded dictionary of the form `presetname: setupstring`.
    - Each preset is now given by a single row of `user_presets`.
    - Setupstrings are stored in `patterns` as their associated patterns, and referred to by `patternid`.

### Sessions
The `sessions` table has been moved from the separate `registry` database into the central database.
Overall the format is the same, with the exception of the `starttime` column being renamed to `start_time`.
The `sessions` table now also tracks the `focused_duration`, `patternid`, and `stages` information for each session.
