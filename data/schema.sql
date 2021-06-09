PRAGMA foreign_keys = 1;

--Meta
CREATE TABLE VersionHistory (
  version INTEGER NOT NULL,
  time INTEGER NOT NULL,
  author TEXT
);

INSERT INTO VersionHistory VALUES (1, strftime('%s', 'now'), 'Initial Creation');


-- Guild configuration
CREATE TABLE guilds (
  guildid INTEGER NOT NULL PRIMARY KEY,
  timer_admin_roleid INTEGER,
  show_tips BOOLEAN,
  globalgroups BOOLEAN,
  autoclean INTEGER,
  studyrole_roleid INTEGER,
  timezone TEXT,
  prefix TEXT
);


-- User configuration
CREATE TABLE users (
  userid INTEGER NOT NULL PRIMARY KEY,
  notify_level INTEGER,
  timezone TEXT,
  name TEXT
);


-- Timer patterns
CREATE TABLE patterns (
  patternid INTEGER PRIMARY KEY AUTOINCREMENT,
  short_repr BOOL NOT NULL,
  stage_str TEXT NOT NULL,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);
CREATE UNIQUE INDEX pattern_strings ON patterns(stage_str);
INSERT INTO patterns(patternid, short_repr, stage_str)
  VALUES (0, 1, '[["Study \ud83d\udd25", 25, "Good luck!", false], ["Break\ud83c\udf1b", 5, "Have a rest.", false], ["Study \ud83d\udd25", 25, "Good luck!", false], ["Break \ud83c\udf1c", 5, "Have a rest.", false], ["Study \ud83d\udd25", 25, "Good luck!", false], ["Long Break \ud83c\udf1d", 10, "Have a rest.", false]]');



-- Timer pattern presets
CREATE TABLE user_presets (
  userid INTEGER NOT NULL,
  preset_name TEXT NOT NULL COLLATE NOCASE,
  patternid INTEGER NOT NULL,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
  FOREIGN KEY (patternid) REFERENCES patterns (patternid) ON DELETE CASCADE
);
CREATE UNIQUE INDEX user_preset_names ON user_presets(userid, preset_name);

CREATE TABLE guild_presets (
  guildid INTEGER NOT NULL,
  preset_name TEXT NOT NULL COLLATE NOCASE,
  created_by INTEGER NOT NULL,
  patternid INTEGER NOT NULL,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
  FOREIGN KEY (patternid) REFERENCES patterns (patternid) ON DELETE CASCADE
);
CREATE UNIQUE INDEX guild_preset_names ON guild_presets(guildid, preset_name);

CREATE VIEW user_preset_patterns AS
  SELECT
    userid,
    preset_name,
    patternid,
    patterns.stage_str AS preset_string
  FROM user_presets
  INNER JOIN patterns USING (patternid);

CREATE VIEW guild_preset_patterns AS
  SELECT
    guildid,
    preset_name,
    created_by,
    patternid,
    patterns.stage_str AS preset_string
  FROM guild_presets
  INNER JOIN patterns USING (patternid);


-- Timers
CREATE TABLE timers (
  roleid INTEGER NOT NULL PRIMARY KEY,
  guildid INTEGER NOT NULL,
  name TEXT NOT NULL,
  channelid INTEGER NOT NULL,
  patternid INTEGER NOT NULL DEFAULT 0,
  brief BOOLEAN,
  voice_channelid INTEGER,
  voice_alert BOOLEAN,
  track_voice_join BOOLEAN,
  track_voice_leave BOOLEAN,
  auto_reset BOOLEAN,
  admin_locked BOOLEAN,
  track_role BOOLEAN,
  compact BOOLEAN,
  voice_channel_name TEXT,
  FOREIGN KEY (patternid) REFERENCES patterns (patternid) ON DELETE SET NULL
);


CREATE TABLE timer_pattern_history (
  timerid INTEGER NOT NULL,
  patternid INTEGER NOT NULL,
  modified_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
  modified_by INTEGER,
  FOREIGN KEY (patternid) REFERENCES patterns (patternid) ON DELETE CASCADE,
  FOREIGN KEY (timerid) REFERENCES timers (roleid) ON DELETE CASCADE
);

CREATE INDEX idx_timerid_modified_at on timer_pattern_history (timerid, modified_at);


CREATE VIEW timer_patterns AS
  SELECT *
  FROM patterns
  INNER JOIN timers USING (patternid);


CREATE VIEW current_timer_patterns AS
  SELECT
    timerid,
    patternid,
    max(modified_at)
  FROM timer_pattern_history
  GROUP BY timerid;


-- Session storage
CREATE TABLE sessions (
  guildid INTEGER NOT NULL,
  userid INTEGER NOT NULL,
  roleid INTEGER NOT NULL,
  start_time INTEGER NOT NULL,
  duration INTEGER NOT NULL,
  focused_duration INTEGER,
  patternid INTEGER,
  stages TEXT,
  FOREIGN KEY (patternid) REFERENCES patterns (patternid) ON DELETE SET NULL
);
CREATE INDEX idx_sessions_guildid_userid on sessions (guildid, userid);

CREATE VIEW session_patterns AS
  SELECT
    *,
    patterns.stage_str AS stage_str,
    users.name AS user_name
  FROM sessions
  LEFT JOIN patterns USING (patternid)
  LEFT JOIN users USING (userid);
