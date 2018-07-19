import os.path
import logging
from .base import Cache


logger = logging.getLogger(__name__)


class SqliteCache(Cache):
    SCHEMA_VERSION = 1

    def __init__(self, dbpath, config):
        self.path = dbpath
        self.config = config

        import sqlite3
        logger.debug("Opening SQL DB: %s" % dbpath)
        self.conn = sqlite3.connect(dbpath,
                                    detect_types=sqlite3.PARSE_DECLTYPES)

        if (not os.path.exists(dbpath) or
                self._getSchemaVersion() != self.SCHEMA_VERSION):
            self._initDb()

    def _getSchemaVersion(self):
        import sqlite3
        try:
            return self.getCustomValue('schema_version', valtype=int)
        except sqlite3.Error:
            return None

    def _initDb(self):
        c = self.conn.cursor()
        c.execute('''DROP TABLE IF EXISTS info''')
        c.execute(
            '''CREATE TABLE info (
                name text PRIMARY KEY NOT NULL,
                str_val text,
                real_val real,
                int_val int
            )''')
        c.execute(
            '''INSERT INTO info (name, int_val)
                VALUES ('schema_version', ?)''',
            (self.SCHEMA_VERSION,))

        c.execute('''DROP TABLE IF EXISTS posted''')
        c.execute(
            '''CREATE TABLE posted (
                id integer PRIMARY KEY,
                silo text NOT NULL,
                uri text NOT NULL,
                posted_on timestamp
            )''')
        c.execute(
            '''CREATE INDEX index_silo ON posted(silo)''')
        c.execute(
            '''CREATE INDEX index_uri ON posted(uri)''')
        self.conn.commit()
        c.close()

    def getCustomValue(self, name, valtype=str):
        c = self.conn.cursor()
        if valtype is str:
            c.execute(
                '''SELECT str_val FROM info WHERE (name = ?)''', (name,))
        elif valtype is float:
            c.execute(
                '''SELECT real_val FROM info WHERE (name = ?)''', (name,))
        elif valtype in (int, bool):
            c.execute(
                '''SELECT int_val FROM info WHERE (name = ?)''', (name,))
        else:
            raise Exception("Unsupported value type: %s" % valtype)
        row = c.fetchone()
        if row is None:
            return None

        return valtype(row[0])

    def setCustomValue(self, name, val):
        c = self.conn.cursor()
        if isinstance(val, str):
            c.execute(
                '''INSERT OR REPLACE INTO info (name, str_val)
                    VALUES (?, ?)''',
                (name, val))
        elif isinstance(val, float):
            c.execute(
                '''INSERT OR REPLACE INTO info (name, real_val)
                    VALUES (?, ?)''',
                (name, str(val)))
        elif isinstance(val, (int, bool)):
            c.execute(
                '''INSERT OR REPLACE INTO info (name, int_val)
                    VALUES (?, ?)''',
                (name, str(int(val))))
        else:
            raise Exception("Unsupported value type: %s" % type(val))

        self.conn.commit()
        c.close()

    def wasPosted(self, silo_name, entry_uri):
        c = self.conn.cursor()
        c.execute(
            '''SELECT id, silo, uri
                FROM posted
                WHERE (silo = ? AND uri = ?)''',
            (silo_name, entry_uri))
        if c.fetchone():
            return True
        return False

    def addPost(self, silo_name, entry_uri):
        c = self.conn.cursor()
        c.execute(
            '''INSERT INTO posted (silo, uri)
                VALUES (?, ?)''',
            (silo_name, entry_uri))
        self.conn.commit()
        c.close()
