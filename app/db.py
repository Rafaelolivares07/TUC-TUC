import psycopg2
import psycopg2.extras
import os


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


class PostgreSQLConnection:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, params=None):
        cur = self._conn.cursor()
        cur.execute(query, params or ())
        return PostgreSQLCursor(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


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


def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(database_url)
    return PostgreSQLConnection(conn)


def init_db(app):
    pass
