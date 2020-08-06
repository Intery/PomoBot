import sqlite3 as sq


class TimerRegistry(object):
    session_keys = (
        'userid',
        'guildid',
        'roleid',
        'starttime',
        'duration',
        'participation'
    )

    def __init__(self, db_file):
        self.conn = sq.connect(db_file, timeout=20)
        self.conn.row_factory = sq.Row

        self.ensure_table()

    def ensure_table(self):
        """
        Ensure the session table exists, otherwise create it.
        """
        cursor = self.conn.cursor()
        columns = ("userid INTEGER NOT NULL, "
                   "guildid INTEGER NOT NULL, "
                   "roleid INTEGER NOT NULL, "
                   "starttime INTEGER NOT NULL, "
                   "duration INTEGER NOT NULL, "
                   "participation STRING")


        cursor.execute("CREATE TABLE IF NOT EXISTS sessions ({})".format(columns))
        self.conn.commit()

    def close(self):
        self.conn.commit()
        self.conn.close()

    def get_sessions_where(self, **kwargs):
        keys = [(key, kwargs[key]) for key in kwargs if key in self.session_keys]

        if keys:
            keystr = "WHERE " + " AND ".join("{} = ?".format(key) for key, val in keys)
        else:
            keystr = ""

        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM sessions {}'.format(keystr), tuple(value for key, value in keys))
        return cursor.fetchall()

    def new_session(self, *args):
        if len(args) != len(self.session_keys):
            raise ValueError("Improper number of session keys passed for storage.")

        cursor = self.conn.cursor()
        value_str = ", ".join('?' for key in args)

        cursor.execute('INSERT INTO sessions VALUES ({})'.format(value_str), tuple(args))
        self.conn.commit()
