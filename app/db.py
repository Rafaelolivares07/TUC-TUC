import os
import psycopg2
import psycopg2.extras
from psycopg2 import pool


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
    def __init__(self, raw_conn, pool_ref):
        self._conn = raw_conn
        self._pool = pool_ref
        self._returned = False

    def execute(self, query, params=None):
        cur = self._conn.cursor()
        cur.execute(query, params or ())
        return PostgreSQLCursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self._returned:
            self._returned = True
            try:
                self._conn.rollback()  # limpiar transacción pendiente antes de devolver
            except Exception:
                pass
            self._pool.putconn(self._conn)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        if exc_type:
            try:
                self._conn.rollback()
            except Exception:
                pass
        self.close()


_pool = None
_db_url = None


def init_db(app):
    global _db_url
    _db_url = os.environ.get('DATABASE_URL', '')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)


def _get_pool():
    global _pool
    if _pool is None:
        print(f'[DB] Creando pool — db_url starts: {_db_url[:30] if _db_url else "VACIO"}')
        _pool = pool.ThreadedConnectionPool(1, 3, _db_url, connect_timeout=10)
        print('[DB] Connection pool inicializado (min=1, max=3)')
    return _pool


def get_db_connection():
    import time
    t0 = time.time()
    print(f'[DB] get_db_connection solicitada')
    p = _get_pool()
    raw = p.getconn()
    print(f'[DB] conexion obtenida en {time.time()-t0:.2f}s')
    return PostgreSQLConnection(raw, p)
