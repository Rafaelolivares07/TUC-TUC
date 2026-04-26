import os
import psycopg2
import psycopg2.extras

_db_url = None


class PostgreSQLRow:
    def __init__(self, cursor, row):
        self._data = {}
        if row and cursor.description:
            for i, col in enumerate(cursor.description):
                self._data[col.name] = row[i]

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def __iter__(self):
        return iter(self._data)

    def items(self):
        return self._data.items()

    def __repr__(self):
        return f'PostgreSQLRow({self._data})'


class PostgreSQLCursor:
    def __init__(self, cursor):
        self._cur = cursor

    @property
    def description(self):
        return self._cur.description

    @property
    def rowcount(self):
        return self._cur.rowcount

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return PostgreSQLRow(self._cur, row)

    def fetchall(self):
        rows = self._cur.fetchall()
        return [PostgreSQLRow(self._cur, r) for r in rows]

    def __iter__(self):
        for row in self._cur:
            yield PostgreSQLRow(self._cur, row)


class PostgreSQLConnection:
    def __init__(self, raw_conn):
        self._conn = raw_conn
        self._closed = False

    def execute(self, query, params=None):
        cur = self._conn.cursor()
        cur.execute(query, params or ())
        return PostgreSQLCursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self._conn.rollback()
            except Exception:
                pass
            try:
                self._conn.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        self.close()


def init_db(app):
    global _db_url
    _db_url = os.environ.get('DATABASE_URL', '')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)


def get_db_connection():
    raw = psycopg2.connect(
        _db_url,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=20,
        keepalives_interval=5,
        keepalives_count=3,
    )
    cur = raw.cursor()
    cur.execute("SET statement_timeout = 30000")
    cur.close()
    raw.commit()
    return PostgreSQLConnection(raw)
