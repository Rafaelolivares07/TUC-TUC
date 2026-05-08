from flask import Blueprint, render_template, request, jsonify, session
from ..db import get_db_connection

bp = Blueprint('watch', __name__)


def _asegurar_tabla(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watch_salas (
            sala        VARCHAR(60) PRIMARY KEY,
            youtube_url TEXT,
            updated_at  TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()


@bp.route('/watch/<sala>/')
def watch_compartir(sala):
    return render_template('watch_compartir.html', sala=sala)


@bp.route('/watch/<sala>/ver')
def watch_ver(sala):
    return render_template('watch_ver.html', sala=sala)


@bp.route('/api/watch/<sala>/set', methods=['POST'])
def watch_set(sala):
    url = (request.get_json(force=True) or {}).get('url', '').strip()
    try:
        conn = get_db_connection()
        _asegurar_tabla(conn)
        conn.execute("""
            INSERT INTO watch_salas (sala, youtube_url, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (sala) DO UPDATE SET youtube_url=EXCLUDED.youtube_url, updated_at=NOW()
        """, (sala, url))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@bp.route('/api/watch/<sala>/estado')
def watch_estado(sala):
    try:
        conn = get_db_connection()
        _asegurar_tabla(conn)
        row = conn.execute(
            "SELECT youtube_url, updated_at FROM watch_salas WHERE sala=%s", (sala,)
        ).fetchone()
        conn.close()
        if not row:
            return jsonify({'ok': True, 'url': None, 'ts': None})
        ts = row['updated_at'].isoformat() if row['updated_at'] else None
        return jsonify({'ok': True, 'url': row['youtube_url'], 'ts': ts})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
