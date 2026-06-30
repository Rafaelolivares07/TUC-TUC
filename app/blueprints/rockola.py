"""
Rockola Tuc Tuc: salas con cola persistente en PostgreSQL.

La UI usa polling HTTP, subida de archivos locales y descarga de audio desde
YouTube mediante cobalt.tools. El modulo no toca la BD al importarse para que
un fallo de Rockola no tumbe el arranque general de Tuc Tuc.
"""

import os
import threading
import uuid

from flask import Blueprint, jsonify, render_template, request, send_from_directory

from app.db import get_db_connection


bp = Blueprint('rockola', __name__, url_prefix='/rockola')

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
CREATE TABLE IF NOT EXISTS rockola_biblioteca (
    archivo_id TEXT PRIMARY KEY,
    sala_id    TEXT NOT NULL,
    nombre     TEXT NOT NULL,
    owner      TEXT NOT NULL DEFAULT 'anon',
    origen     TEXT NOT NULL DEFAULT 'archivo',
    creado_en  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_biblioteca_sala ON rockola_biblioteca(sala_id, creado_en DESC);
"""

_lock = threading.Lock()
_db_ready = False


def _row_dict(row):
    return {k: row[k] for k in row.keys()}


def _ensure_db():
    global _db_ready
    if _db_ready:
        return
    with _lock:
        if _db_ready:
            return
        conn = get_db_connection()
        try:
            conn.execute(INIT_SQL)
            conn.commit()
            _db_ready = True
        finally:
            conn.close()


def _connect():
    _ensure_db()
    return get_db_connection()


def _get_sala(conn, sala_id):
    row = conn.execute(
        "SELECT * FROM rockola_salas WHERE sala_id = %s",
        (sala_id,),
    ).fetchone()
    if row:
        return _row_dict(row)

    conn.execute(
        "INSERT INTO rockola_salas (sala_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (sala_id,),
    )
    conn.commit()
    return {'sala_id': sala_id, 'sync_estado': 'play', 'sync_pos': 0.0, 'sync_ts': 0.0}


def _get_cola(conn, sala_id):
    rows = conn.execute(
        """
        SELECT id, nombre, owner
        FROM rockola_cola
        WHERE sala_id = %s
        ORDER BY posicion ASC
        """,
        (sala_id,),
    ).fetchall()
    return [_row_dict(row) for row in rows]


def _max_pos(conn, sala_id):
    row = conn.execute(
        "SELECT COALESCE(MAX(posicion), -1) AS m FROM rockola_cola WHERE sala_id = %s",
        (sala_id,),
    ).fetchone()
    return row['m'] if row else -1


def _recordar_cancion(conn, sala_id, archivo_id, nombre, owner, origen):
    conn.execute(
        """
        INSERT INTO rockola_biblioteca (archivo_id, sala_id, nombre, owner, origen)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (archivo_id) DO UPDATE
        SET nombre = EXCLUDED.nombre,
            owner = EXCLUDED.owner,
            origen = EXCLUDED.origen
        """,
        (archivo_id, sala_id, nombre, owner, origen),
    )


def _agregar_a_cola(conn, sala_id, archivo_id, nombre, owner):
    pos_actual = _max_pos(conn, sala_id) + 1
    conn.execute(
        """
        INSERT INTO rockola_cola (id, sala_id, nombre, owner, posicion)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (archivo_id, sala_id, nombre, owner, pos_actual),
    )


def _upload_dir(sala_id):
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp')
    folder = os.path.join(base, sala_id)
    os.makedirs(folder, exist_ok=True)
    return folder


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


@bp.route('/<sala_id>/subir', methods=['POST'])
def subir(sala_id):
    owner = request.form.get('owner', 'anon')
    files = request.files.getlist('archivo')
    if not files:
        return jsonify(ok=False, error='sin archivo'), 400

    agregadas = []
    upload_dir = _upload_dir(sala_id)

    conn = _connect()
    try:
        with _lock:
            for file in files:
                ext = os.path.splitext(file.filename)[1].lower()
                nombre_id = str(uuid.uuid4()) + ext
                file.save(os.path.join(upload_dir, nombre_id))
                _agregar_a_cola(conn, sala_id, nombre_id, file.filename, owner)
                _recordar_cancion(conn, sala_id, nombre_id, file.filename, owner, 'archivo')
                agregadas.append({'id': nombre_id, 'nombre': file.filename, 'owner': owner})
            conn.commit()
    finally:
        conn.close()

    return jsonify(ok=True, agregadas=agregadas)


COBALT_API = 'https://api.cobalt.tools/'
COBALT_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Origin': 'https://cobalt.tools',
    'Referer': 'https://cobalt.tools/',
}


@bp.route('/<sala_id>/youtube', methods=['POST'])
def youtube(sala_id):
    import json as _json
    import urllib.error
    import urllib.request

    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    owner = data.get('owner', 'anon')

    if not url or ('youtube.com' not in url and 'youtu.be' not in url):
        return jsonify(ok=False, error='URL de YouTube invalida'), 400

    try:
        payload = _json.dumps({
            'url': url,
            'downloadMode': 'audio',
            'audioFormat': 'mp3',
        }).encode()
        req = urllib.request.Request(
            COBALT_API,
            data=payload,
            headers=COBALT_HEADERS,
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                cobalt = _json.loads(response.read())
        except urllib.error.HTTPError as error:
            body = error.read().decode('utf-8', errors='ignore')[:300]
            return jsonify(ok=False, error=f'Cobalt HTTP {error.code}: {body}'), 502
    except Exception as error:
        return jsonify(ok=False, error=f'Cobalt no respondio: {error}'), 502

    status = cobalt.get('status')
    if status == 'error':
        msg = cobalt.get('error', {}).get('code', 'error desconocido')
        return jsonify(ok=False, error=f'Cobalt: {msg}'), 400
    if status not in ('stream', 'tunnel', 'redirect'):
        return jsonify(ok=False, error=f'Cobalt estado inesperado: {status}'), 502

    download_url = cobalt.get('url') or cobalt.get('audio')
    if not download_url:
        return jsonify(ok=False, error='Cobalt no entrego URL de descarga'), 502

    title = cobalt.get('filename', 'audio').rsplit('.', 1)[0]
    upload_dir = _upload_dir(sala_id)
    nombre_id = str(uuid.uuid4())
    tmp_path = os.path.join(upload_dir, nombre_id + '.mp3')

    try:
        dl_req = urllib.request.Request(download_url, headers={
            'User-Agent': COBALT_HEADERS['User-Agent'],
        })
        with urllib.request.urlopen(dl_req, timeout=120) as response, open(tmp_path, 'wb') as file:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                file.write(chunk)
    except Exception as error:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return jsonify(ok=False, error=f'Error descargando audio: {error}'), 502

    archivo_final = nombre_id + '.mp3'
    nombre_display = title + '.mp3'

    conn = _connect()
    try:
        with _lock:
            _agregar_a_cola(conn, sala_id, archivo_final, nombre_display, owner)
            _recordar_cancion(conn, sala_id, archivo_final, nombre_display, owner, 'youtube')
            conn.commit()
    finally:
        conn.close()

    return jsonify(ok=True, agregadas=[{
        'id': archivo_final,
        'nombre': nombre_display,
        'owner': owner,
    }])


@bp.route('/<sala_id>/cola')
def cola(sala_id):
    conn = _connect()
    try:
        sala = _get_sala(conn, sala_id)
        items = _get_cola(conn, sala_id)
    finally:
        conn.close()

    return jsonify(
        ok=True,
        cola=items,
        sync_estado=sala['sync_estado'],
        sync_pos=sala['sync_pos'],
        sync_ts=sala['sync_ts'],
    )


@bp.route('/<sala_id>/biblioteca')
def biblioteca(sala_id):
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT archivo_id AS id, nombre, owner, origen, creado_en
            FROM rockola_biblioteca
            WHERE sala_id = %s
            ORDER BY creado_en DESC
            LIMIT 80
            """,
            (sala_id,),
        ).fetchall()
        canciones = [_row_dict(row) for row in rows]
    finally:
        conn.close()
    return jsonify(ok=True, canciones=canciones)


@bp.route('/<sala_id>/biblioteca/<archivo_id>/poner', methods=['POST'])
def poner_desde_biblioteca(sala_id, archivo_id):
    data = request.get_json(silent=True) or {}
    owner = data.get('owner', 'anon')

    conn = _connect()
    try:
        with _lock:
            row = conn.execute(
                """
                SELECT archivo_id, nombre
                FROM rockola_biblioteca
                WHERE sala_id = %s AND archivo_id = %s
                """,
                (sala_id, archivo_id),
            ).fetchone()
            if not row:
                return jsonify(ok=False, error='Cancion no encontrada'), 404

            nombre = row['nombre']
            nuevo_id = str(uuid.uuid4()) + os.path.splitext(archivo_id)[1]
            origen = os.path.join(_upload_dir(sala_id), archivo_id)
            destino = os.path.join(_upload_dir(sala_id), nuevo_id)
            if not os.path.exists(origen):
                return jsonify(ok=False, error='Archivo no disponible en el servidor'), 404

            with open(origen, 'rb') as src, open(destino, 'wb') as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)

            _agregar_a_cola(conn, sala_id, nuevo_id, nombre, owner)
            conn.commit()
    finally:
        conn.close()

    return jsonify(ok=True, agregadas=[{'id': nuevo_id, 'nombre': nombre, 'owner': owner}])


@bp.route('/<sala_id>/sync_control', methods=['POST'])
def sync_control(sala_id):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        with _lock:
            _get_sala(conn, sala_id)
            conn.execute(
                """
                UPDATE rockola_salas
                SET sync_estado = %s, sync_pos = %s, sync_ts = %s
                WHERE sala_id = %s
                """,
                (data.get('estado', 'play'), data.get('pos', 0.0), data.get('ts', 0.0), sala_id),
            )
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/siguiente', methods=['POST'])
def siguiente(sala_id):
    data = request.get_json(silent=True) or {}
    cancion_id = data.get('id')
    conn = _connect()
    try:
        with _lock:
            items = _get_cola(conn, sala_id)
            if items and (not cancion_id or items[0]['id'] == cancion_id):
                conn.execute(
                    "DELETE FROM rockola_cola WHERE id = %s AND sala_id = %s",
                    (items[0]['id'], sala_id),
                )
                conn.execute(
                    """
                    UPDATE rockola_salas
                    SET sync_estado = 'play', sync_pos = 0.0, sync_ts = 0.0
                    WHERE sala_id = %s
                    """,
                    (sala_id,),
                )
                conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/reordenar', methods=['POST'])
def reordenar(sala_id):
    data = request.get_json(silent=True) or {}
    nuevo_orden = data.get('orden', [])
    owner = data.get('owner')
    modo = data.get('modo', 'restaurante')

    conn = _connect()
    try:
        with _lock:
            items = _get_cola(conn, sala_id)
            por_id = {item['id']: item for item in items}
            nueva_cola = []
            for id_ in nuevo_orden:
                if id_ in por_id:
                    item = por_id[id_]
                    if modo == 'sync' or item['owner'] == owner:
                        nueva_cola.append(item)
            ids_nuevos = {item['id'] for item in nueva_cola}
            for item in items:
                if item['id'] not in ids_nuevos:
                    nueva_cola.append(item)
            for index, item in enumerate(nueva_cola):
                conn.execute(
                    """
                    UPDATE rockola_cola
                    SET posicion = %s
                    WHERE id = %s AND sala_id = %s
                    """,
                    (index, item['id'], sala_id),
                )
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/archivo/<nombre_id>')
def archivo(sala_id, nombre_id):
    return send_from_directory(_upload_dir(sala_id), nombre_id)


def register_events(socketio):
    return None
