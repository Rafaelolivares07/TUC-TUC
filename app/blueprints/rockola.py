"""
rockola.py — Blueprint con cola persistente en PostgreSQL + YouTube via yt-dlp
Drop-in replacement del blueprint original.
"""

from flask import Blueprint, render_template, request, jsonify, send_from_directory
from sqlalchemy import create_engine, text
import os, uuid, threading

bp = Blueprint('rockola', __name__, url_prefix='/rockola')

# ── Base de datos ─────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"connect_timeout": 10}
)

INIT_SQL = """
CREATE TABLE IF NOT EXISTS rockola_salas (
    sala_id      TEXT PRIMARY KEY,
    sync_estado  TEXT  NOT NULL DEFAULT 'play',
    sync_pos     FLOAT NOT NULL DEFAULT 0.0,
    sync_ts      FLOAT NOT NULL DEFAULT 0.0
);
CREATE TABLE IF NOT EXISTS rockola_cola (
    id        TEXT PRIMARY KEY,
    sala_id   TEXT    NOT NULL,
    nombre    TEXT    NOT NULL,
    owner     TEXT    NOT NULL DEFAULT 'anon',
    posicion  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cola_sala ON rockola_cola(sala_id, posicion);
"""

def init_db():
    with engine.connect() as conn:
        conn.execute(text(INIT_SQL))
        conn.commit()

try:
    init_db()
except Exception as e:
    print(f'[rockola] Aviso: no se pudo inicializar DB: {e}')

# ── Helpers DB ────────────────────────────────────────────────────────────────
_lock = threading.Lock()

def _get_sala(conn, sala_id):
    row = conn.execute(
        text("SELECT * FROM rockola_salas WHERE sala_id = :sid"),
        {'sid': sala_id}
    ).fetchone()
    if not row:
        conn.execute(
            text("INSERT INTO rockola_salas (sala_id) VALUES (:sid) ON CONFLICT DO NOTHING"),
            {'sid': sala_id}
        )
        conn.commit()
        return {'sala_id': sala_id, 'sync_estado': 'play', 'sync_pos': 0.0, 'sync_ts': 0.0}
    return dict(row._mapping)

def _get_cola(conn, sala_id):
    rows = conn.execute(
        text("SELECT id, nombre, owner FROM rockola_cola WHERE sala_id = :sid ORDER BY posicion ASC"),
        {'sid': sala_id}
    ).fetchall()
    return [dict(r._mapping) for r in rows]

def _max_pos(conn, sala_id):
    row = conn.execute(
        text("SELECT COALESCE(MAX(posicion), -1) as m FROM rockola_cola WHERE sala_id = :sid"),
        {'sid': sala_id}
    ).fetchone()
    return row.m if row else -1

def _upload_dir(sala_id):
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp')
    d = os.path.join(base, sala_id)
    os.makedirs(d, exist_ok=True)
    return d


# ── Páginas ───────────────────────────────────────────────────────────────────

@bp.route('/')
def entrada():
    return render_template('rockola_entrada.html')

@bp.route('/cliente')
def cliente():
    return render_template('rockola_cliente.html', sala_id='default', modo='restaurante')

@bp.route('/reproductor')
def reproductor():
    return render_template('rockola_reproductor.html', sala_id='default')

@bp.route('/<sala_id>/cliente')
def cliente_sala(sala_id):
    return render_template('rockola_cliente.html', sala_id=sala_id, modo='restaurante')

@bp.route('/<sala_id>/reproductor')
def reproductor_sala(sala_id):
    return render_template('rockola_reproductor.html', sala_id=sala_id)

@bp.route('/sync/<sala_id>')
def sync(sala_id):
    return render_template('rockola_sync.html', sala_id=sala_id)


# ── API: subir archivo ────────────────────────────────────────────────────────

@bp.route('/<sala_id>/subir', methods=['POST'])
def subir(sala_id):
    owner = request.form.get('owner', 'anon')
    files = request.files.getlist('archivo')
    if not files:
        return jsonify(ok=False, error='sin archivo'), 400

    agregadas  = []
    upload_dir = _upload_dir(sala_id)

    with _lock, engine.connect() as conn:
        pos_actual = _max_pos(conn, sala_id)
        for f in files:
            ext       = os.path.splitext(f.filename)[1].lower()
            nombre_id = str(uuid.uuid4()) + ext
            f.save(os.path.join(upload_dir, nombre_id))
            pos_actual += 1
            conn.execute(text("""
                INSERT INTO rockola_cola (id, sala_id, nombre, owner, posicion)
                VALUES (:id, :sala_id, :nombre, :owner, :pos)
            """), {'id': nombre_id, 'sala_id': sala_id, 'nombre': f.filename,
                   'owner': owner, 'pos': pos_actual})
            agregadas.append({'id': nombre_id, 'nombre': f.filename, 'owner': owner})
        conn.commit()

    return jsonify(ok=True, agregadas=agregadas)


# ── API: YouTube → cola ───────────────────────────────────────────────────────

@bp.route('/<sala_id>/youtube_resolve', methods=['POST'])
def youtube_resolve(sala_id):
    """
    Resuelve la URL del stream de audio de YouTube sin descargar.
    El cliente descarga desde su propia IP residencial para evitar bot-check.
    """
    try:
        import yt_dlp
    except ImportError:
        return jsonify(ok=False, error='yt-dlp no instalado en el servidor'), 500

    data = request.get_json(silent=True) or {}
    url  = data.get('url', '').strip()

    if not url or ('youtube.com' not in url and 'youtu.be' not in url):
        return jsonify(ok=False, error='URL de YouTube inválida'), 400

    cookies_path = os.path.join(os.path.dirname(__file__), '..', '..', 'cookies.txt')
    if not os.path.exists(cookies_path):
        cookies_path = os.path.join(os.getcwd(), 'cookies.txt')

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {'youtube': {'player_client': ['tv_embedded', 'ios']}},
    }
    if os.path.exists(cookies_path):
        ydl_opts['cookiefile'] = cookies_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            titulo   = info.get('title', 'audio')
            duracion = info.get('duration', 0)
            if duracion > 900:
                return jsonify(ok=False, error='La canción es muy larga (máx. 15 min)'), 400

            formats = info.get('formats', [])
            audio_fmts = [f for f in formats
                          if f.get('acodec') != 'none' and f.get('vcodec') in (None, 'none')]
            if not audio_fmts:
                audio_fmts = formats
            audio_fmts.sort(key=lambda f: f.get('abr') or 0, reverse=True)
            best = audio_fmts[0]

            return jsonify(ok=True,
                           stream_url=best.get('url'),
                           titulo=titulo,
                           ext=best.get('ext', 'webm'))
    except Exception as e:
        return jsonify(ok=False, error=f'No se pudo resolver: {str(e)[:200]}'), 500


# ── API: cola, sync, siguiente, reordenar, archivo ───────────────────────────

@bp.route('/<sala_id>/cola')
def cola(sala_id):
    with engine.connect() as conn:
        sala  = _get_sala(conn, sala_id)
        items = _get_cola(conn, sala_id)
    return jsonify(
        ok=True, cola=items,
        sync_estado=sala['sync_estado'],
        sync_pos=sala['sync_pos'],
        sync_ts=sala['sync_ts']
    )


@bp.route('/<sala_id>/sync_control', methods=['POST'])
def sync_control(sala_id):
    data = request.get_json()
    with _lock, engine.connect() as conn:
        _get_sala(conn, sala_id)
        conn.execute(text("""
            UPDATE rockola_salas
            SET sync_estado = :estado, sync_pos = :pos, sync_ts = :ts
            WHERE sala_id = :sid
        """), {'estado': data.get('estado','play'), 'pos': data.get('pos',0.0),
               'ts': data.get('ts',0.0), 'sid': sala_id})
        conn.commit()
    return jsonify(ok=True)


@bp.route('/<sala_id>/siguiente', methods=['POST'])
def siguiente(sala_id):
    data       = request.get_json(silent=True) or {}
    cancion_id = data.get('id')
    with _lock, engine.connect() as conn:
        items = _get_cola(conn, sala_id)
        if items and (not cancion_id or items[0]['id'] == cancion_id):
            conn.execute(
                text("DELETE FROM rockola_cola WHERE id = :id AND sala_id = :sid"),
                {'id': items[0]['id'], 'sid': sala_id}
            )
            conn.execute(text("""
                UPDATE rockola_salas
                SET sync_estado='play', sync_pos=0.0, sync_ts=0.0
                WHERE sala_id = :sid
            """), {'sid': sala_id})
            conn.commit()
    return jsonify(ok=True)


@bp.route('/<sala_id>/reordenar', methods=['POST'])
def reordenar(sala_id):
    data        = request.get_json()
    nuevo_orden = data.get('orden', [])
    owner       = data.get('owner')
    modo        = data.get('modo', 'restaurante')

    with _lock, engine.connect() as conn:
        items  = _get_cola(conn, sala_id)
        por_id = {item['id']: item for item in items}
        nueva_cola = []
        for id_ in nuevo_orden:
            if id_ in por_id:
                item = por_id[id_]
                if modo == 'sync' or item['owner'] == owner:
                    nueva_cola.append(item)
        ids_nuevos = {i['id'] for i in nueva_cola}
        for item in items:
            if item['id'] not in ids_nuevos:
                nueva_cola.append(item)
        for i, item in enumerate(nueva_cola):
            conn.execute(text("""
                UPDATE rockola_cola SET posicion = :pos
                WHERE id = :id AND sala_id = :sid
            """), {'pos': i, 'id': item['id'], 'sid': sala_id})
        conn.commit()
    return jsonify(ok=True)


@bp.route('/<sala_id>/archivo/<nombre_id>')
def archivo(sala_id, nombre_id):
    return send_from_directory(_upload_dir(sala_id), nombre_id)


def register_events(socketio):
    pass
