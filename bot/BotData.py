import sqlite3 as sq
import json

prop_table_info = [
        ("users", "users", ["userid"]),
        ("guilds", "guilds", ["guildid"]),
]


class BotData:
    def __init__(self, app="", data_file="data.db"):
        self.conn = sq.connect(data_file, timeout=20)
        for name, table_name, keys in prop_table_info:
            manipulator = _propTableManipulator(table_name, keys, self.conn, app)
            self.__setattr__(name, manipulator)

    def close(self):
        self.conn.commit()
        self.conn.close()


class _propTableManipulator:
    def __init__(self, table, keys, conn, app):
        self.table = table
        self.keys = keys
        self.conn = conn
        self.app = app

        self.ensure_tables()
        self.propmap = self.get_propmap()

    def ensure_tables(self):
        cursor = self.conn.cursor()
        keys = "{},".format(", ".join("{} INTEGER NOT NULL".format(key) for key in self.keys)) if self.keys else ""
        key_list = "{},".format(", ".join(self.keys)) if self.keys else ""
        columns = "{} property TEXT NOT NULL, value TEXT, PRIMARY KEY ({} property)".format(keys, key_list)
        cursor.execute('CREATE TABLE IF NOT EXISTS {} ({})'.format(self.table, columns))
        cursor.execute('CREATE TABLE IF NOT EXISTS {}_props (property TEXT NOT NULL,\
                       shared BOOLEAN NOT NULL,\
                       PRIMARY KEY (property))'.format(self.table))
        self.conn.commit()

    def get_propmap(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * from {}_props'.format(self.table))
        propmap = {}
        for prop in cursor.fetchall():
            propmap[prop[0]] = prop[1]
        return propmap

    def map_prop(self, prop):
        return "{}_{}".format(self.app, prop) if (prop in self.propmap and not self.propmap[prop] and self.app) else prop

    def ensure_exists(self, *props, shared=True):
        for prop in props:
            if prop in self.propmap:
                if self.propmap[prop] != shared:
                    cursor = self.conn.cursor()
                    cursor.execute('UPDATE {}_props SET shared = ? WHERE property = ?'.format(self.table), (shared, prop))
                    self.propmap[prop] = shared
                    self.conn.commit()
            else:
                cursor = self.conn.cursor()
                cursor.execute('INSERT INTO {}_props VALUES (?, ?)'.format(self.table), (prop, shared))
                self.propmap = self.get_propmap()
                self.conn.commit()

    def get(self, *args, default=None):
        if len(args) != len(self.keys) + 1:
            raise Exception("Improper number of keys passed to get.")
        prop = self.map_prop(args[-1])
        criteria = " AND ".join("{} = ?" for key in args)

        cursor = self.conn.cursor()
        cursor.execute('SELECT value from {} where {}'.format(self.table, criteria).format(*self.keys, 'property'), tuple([*args[:-1], prop]))
        value = cursor.fetchone()
        return json.loads(value[0]) if (value and value[0]) else default

    def set(self, *args):
        if len(args) != len(self.keys) + 2:
            raise Exception("Improper number of keys passed to set.")
        prop = self.map_prop(args[-2])
        value = json.dumps(args[-1])
        criteria = " AND ".join("{} = ?" for key in args[:-1])
        values = ", ".join("?" for key in args)

        cursor = self.conn.cursor()
        cursor.execute('SELECT EXISTS(SELECT 1 from {} where {})'.format(self.table, criteria).format(*self.keys, 'property'), tuple([*args[:-2], prop]))
        exists = cursor.fetchone()

        if not exists[0]:
            cursor.execute('INSERT INTO {} VALUES ({})'.format(self.table, values), tuple([*args[:-2], prop, value]))
        else:
            cursor.execute('UPDATE {} SET value = ? WHERE {}'.format(self.table, criteria).format(*self.keys, 'property'), tuple([value, *args[:-2], prop]))
        self.conn.commit()

    def find(self, prop, value, read=False):
        if len(self.keys) > 1:
            raise Exception("This method cannot currently be used when there are multiple keys")
        prop = self.map_prop(prop)
        if read:
            value = json.dumps(value)

        cursor = self.conn.cursor()
        cursor.execute('SELECT {} FROM {} WHERE property = ? AND value = ?'.format(self.keys[0], self.table), (prop, value))
        return [value[0] for value in cursor.fetchall()]

    def find_not_empty(self, prop):
        if len(self.keys) > 1:
            raise Exception("This method cannot currently be used when there are multiple keys")
        prop = self.map_prop(prop)

        cursor = self.conn.cursor()
        cursor.execute('SELECT {} FROM {} WHERE property = ? AND value IS NOT NULL AND value != \'\''.format(self.keys[0], self.table), (prop,))
        return [value[0] for value in cursor.fetchall()]
