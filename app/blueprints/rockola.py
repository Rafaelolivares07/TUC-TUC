"""
Rockola Tuc Tuc: salas con cola persistente en PostgreSQL.

La UI usa polling HTTP, subida de archivos locales y descarga de audio desde
YouTube mediante cobalt.tools. El modulo no toca la BD al importarse para que
un fallo de Rockola no tumbe el arranque general de Tuc Tuc.
"""

import json
import os
import re
import threading
import urllib.parse
import uuid

from flask import Blueprint, Response, jsonify, make_response, render_template, request, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash

from app.db import get_db_connection


bp = Blueprint('rockola', __name__, url_prefix='/rockola')

INIT_SQL = """
CREATE TABLE IF NOT EXISTS rockola_salas (
    sala_id      TEXT PRIMARY KEY,
    admin_key    TEXT,
    dispositivo_reproductor_id TEXT,
    dispositivo_reproductor_nombre TEXT,
    sync_estado  TEXT  NOT NULL DEFAULT 'play',
    sync_pos     FLOAT NOT NULL DEFAULT 0.0,
    sync_ts      FLOAT NOT NULL DEFAULT 0.0,
    volumen      INTEGER NOT NULL DEFAULT 80,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rockola_cola (
    id        TEXT PRIMARY KEY,
    sala_id   TEXT    NOT NULL,
    nombre    TEXT    NOT NULL,
    tercero_id INTEGER REFERENCES terceros(id) ON DELETE SET NULL,
    posicion  INTEGER NOT NULL DEFAULT 0,
    lista_envio_id TEXT,
    lista_envio_nombre TEXT,
    lista_envio_posicion INTEGER,
    youtube_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_cola_sala ON rockola_cola(sala_id, posicion);
CREATE TABLE IF NOT EXISTS rockola_biblioteca (
    archivo_id TEXT PRIMARY KEY,
    sala_id    TEXT NOT NULL,
    nombre     TEXT NOT NULL,
    tercero_id INTEGER REFERENCES terceros(id) ON DELETE SET NULL,
    origen     TEXT NOT NULL DEFAULT 'archivo',
    youtube_url TEXT,
    creado_en  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_biblioteca_sala ON rockola_biblioteca(sala_id, creado_en DESC);
CREATE TABLE IF NOT EXISTS rockola_dispositivos (
    dispositivo_id TEXT PRIMARY KEY,
    nombre         TEXT NOT NULL DEFAULT 'Dispositivo',
    user_agent     TEXT,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rockola_canciones (
    cancion_id     TEXT PRIMARY KEY,
    titulo         TEXT NOT NULL,
    archivo_nombre TEXT,
    tamano_bytes   BIGINT,
    mime           TEXT,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rockola_dispositivo_canciones (
    dispositivo_id TEXT NOT NULL REFERENCES rockola_dispositivos(dispositivo_id) ON DELETE CASCADE,
    cancion_id     TEXT NOT NULL REFERENCES rockola_canciones(cancion_id) ON DELETE CASCADE,
    local_id       TEXT NOT NULL,
    disponible     BOOLEAN NOT NULL DEFAULT TRUE,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (dispositivo_id, cancion_id)
);
CREATE INDEX IF NOT EXISTS idx_dispositivo_canciones_cancion ON rockola_dispositivo_canciones(cancion_id);
CREATE TABLE IF NOT EXISTS rockola_listas (
    lista_id       TEXT PRIMARY KEY,
    dispositivo_id TEXT NOT NULL REFERENCES rockola_dispositivos(dispositivo_id) ON DELETE CASCADE,
    nombre         TEXT NOT NULL,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rockola_lista_canciones (
    lista_id   TEXT NOT NULL REFERENCES rockola_listas(lista_id) ON DELETE CASCADE,
    cancion_id TEXT NOT NULL REFERENCES rockola_canciones(cancion_id) ON DELETE CASCADE,
    posicion   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (lista_id, cancion_id)
);
CREATE TABLE IF NOT EXISTS rockola_validaciones (
    id           BIGSERIAL PRIMARY KEY,
    sala_id      TEXT NOT NULL,
    query        TEXT NOT NULL DEFAULT '',
    cancion_id   TEXT NOT NULL DEFAULT '',
    sonando_id   TEXT NOT NULL DEFAULT '',
    nombre       TEXT NOT NULL DEFAULT '',
    youtube_url  TEXT NOT NULL DEFAULT '',
    evento       TEXT NOT NULL DEFAULT 'fin',
    duracion_seg DOUBLE PRECISION NOT NULL DEFAULT 0,
    sonados_seg  DOUBLE PRECISION NOT NULL DEFAULT 0,
    ratio        DOUBLE PRECISION NOT NULL DEFAULT 0,
    validado     BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_validaciones_query ON rockola_validaciones(query);
CREATE INDEX IF NOT EXISTS idx_validaciones_sala ON rockola_validaciones(sala_id);
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS admin_key TEXT;
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS volumen INTEGER NOT NULL DEFAULT 80;
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS dispositivo_reproductor_id TEXT;
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS dispositivo_reproductor_nombre TEXT;
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS lista_envio_id TEXT;
ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS lista_envio_nombre TEXT;
ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS lista_envio_posicion INTEGER;
ALTER TABLE rockola_biblioteca ADD COLUMN IF NOT EXISTS duracion TEXT NOT NULL DEFAULT '';
ALTER TABLE rockola_compartidos ADD COLUMN IF NOT EXISTS duracion TEXT NOT NULL DEFAULT '';
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
            # Asegurar migraciones
            conn.execute("ALTER TABLE terceros ADD COLUMN IF NOT EXISTS pin_seguridad VARCHAR(255);")
            conn.execute("ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS tercero_id INTEGER REFERENCES terceros(id) ON DELETE SET NULL;")
            conn.execute("ALTER TABLE rockola_biblioteca ADD COLUMN IF NOT EXISTS tercero_id INTEGER REFERENCES terceros(id) ON DELETE SET NULL;")
            conn.execute("ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS reproducida BOOLEAN DEFAULT FALSE;")
            conn.execute("ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS reproducida_en TIMESTAMP;")
            conn.execute("ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS youtube_url TEXT;")
            conn.execute("ALTER TABLE rockola_biblioteca ADD COLUMN IF NOT EXISTS youtube_url TEXT;")
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS fundido_cruzado BOOLEAN DEFAULT TRUE;")
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS fundido_segundos INTEGER DEFAULT 12;")
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS fundido_duracion INTEGER DEFAULT 5;")
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS modo_shuffle BOOLEAN DEFAULT FALSE;")
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS modo_repetir_cancion BOOLEAN DEFAULT FALSE;")
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS modo_repetir_lista BOOLEAN DEFAULT FALSE;")
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS modo_autoplay BOOLEAN DEFAULT FALSE;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rockola_compartidos (
                    token         TEXT PRIMARY KEY,
                    sala_id       TEXT NOT NULL,
                    nombre        TEXT NOT NULL,
                    origen        TEXT NOT NULL DEFAULT 'youtube',
                    youtube_url   TEXT,
                    archivo_id    TEXT,
                    tercero_id    INTEGER REFERENCES terceros(id) ON DELETE SET NULL,
                    creado_por    INTEGER REFERENCES terceros(id) ON DELETE SET NULL,
                    visitas       INTEGER NOT NULL DEFAULT 0,
                    creado_en     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_rockola_compartidos_token ON rockola_compartidos(token);

                CREATE TABLE IF NOT EXISTS rockola_peticiones (
                    id                    SERIAL PRIMARY KEY,
                    sala_id               TEXT NOT NULL,
                    token_origen          TEXT NOT NULL,
                    solicitante_nombre    TEXT,
                    solicitante_telefono  TEXT,
                    tercero_id           INTEGER REFERENCES terceros(id) ON DELETE SET NULL,
                    cancion_solicitada    TEXT NOT NULL,
                    estado                TEXT NOT NULL DEFAULT 'pendiente',
                    respuesta_nombre      TEXT,
                    respuesta_origen      TEXT,
                    respuesta_youtube_url TEXT,
                    respuesta_archivo_id  TEXT,
                    creado_en             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    despachado_en         TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_rockola_peticiones_token ON rockola_peticiones(token_origen);
                CREATE INDEX IF NOT EXISTS idx_rockola_peticiones_sala ON rockola_peticiones(sala_id, estado);
            """)
            try:
                conn.execute("ALTER TABLE rockola_cola DROP COLUMN IF EXISTS owner;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE rockola_biblioteca DROP COLUMN IF EXISTS owner;")
            except Exception:
                pass
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
        sala = _row_dict(row)
        if not sala.get('admin_key'):
            sala['admin_key'] = uuid.uuid4().hex
            conn.execute(
                "UPDATE rockola_salas SET admin_key = %s WHERE sala_id = %s",
                (sala['admin_key'], sala_id),
            )
            conn.commit()
        return sala

    admin_key = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO rockola_salas (sala_id, admin_key) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (sala_id, admin_key),
    )
    conn.commit()
    return {'sala_id': sala_id, 'admin_key': admin_key, 'sync_estado': 'play', 'sync_pos': 0.0, 'sync_ts': 0.0, 'volumen': 80}


def _get_cola(conn, sala_id):
    rows = conn.execute(
        """
        SELECT c.id, c.nombre, c.tercero_id, t.nombre AS owner, c.lista_envio_id, c.lista_envio_nombre, c.lista_envio_posicion, c.youtube_url
        FROM rockola_cola c
        LEFT JOIN terceros t ON c.tercero_id = t.id
        WHERE c.sala_id = %s AND c.reproducida = FALSE
        ORDER BY c.posicion ASC
        """,
        (sala_id,),
    ).fetchall()
    return [_row_dict(row) for row in rows]


def _get_item_cola(conn, sala_id, archivo_id):
    row = conn.execute(
        """
        SELECT c.id, c.nombre, c.tercero_id, t.nombre AS owner, c.youtube_url
        FROM rockola_cola c
        LEFT JOIN terceros t ON c.tercero_id = t.id
        WHERE c.sala_id = %s AND c.id = %s
        """,
        (sala_id, archivo_id),
    ).fetchone()
    return _row_dict(row) if row else None


def _max_pos(conn, sala_id):
    row = conn.execute(
        "SELECT COALESCE(MAX(posicion), -1) AS m FROM rockola_cola WHERE sala_id = %s AND reproducida = FALSE",
        (sala_id,),
    ).fetchone()
    return row['m'] if row else -1


def _validar_tercero_id(conn, tercero_id):
    if not tercero_id:
        return None
    try:
        tid = int(tercero_id)
        existe = conn.execute("SELECT 1 FROM terceros WHERE id = %s", (tid,)).fetchone()
        return tid if existe else None
    except Exception:
        return None


def _recordar_cancion(conn, sala_id, archivo_id, nombre, tercero_id, origen, youtube_url=None):
    tid = _validar_tercero_id(conn, tercero_id)
    conn.execute(
        """
        INSERT INTO rockola_biblioteca (archivo_id, sala_id, nombre, tercero_id, origen, youtube_url)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (archivo_id) DO UPDATE
        SET nombre = EXCLUDED.nombre,
            tercero_id = EXCLUDED.tercero_id,
            origen = EXCLUDED.origen,
            youtube_url = EXCLUDED.youtube_url
        """,
        (archivo_id, sala_id, nombre, tid, origen, youtube_url),
    )


def _agregar_a_cola(conn, sala_id, archivo_id, nombre, tercero_id, lista_envio=None, modo='final', youtube_url=None):
    lista_envio = lista_envio or {}
    tid = _validar_tercero_id(conn, tercero_id)
    
    if modo == 'ya':
        row = conn.execute(
            "SELECT MIN(posicion) FROM rockola_cola WHERE sala_id = %s AND reproducida = FALSE",
            (sala_id,)
        ).fetchone()
        min_pos = row[0] if row and row[0] is not None else 0
        conn.execute(
            "UPDATE rockola_cola SET posicion = posicion + 1 WHERE sala_id = %s AND reproducida = FALSE",
            (sala_id,)
        )
        pos_actual = min_pos
    elif modo == 'siguiente':
        row = conn.execute(
            "SELECT MIN(posicion) FROM rockola_cola WHERE sala_id = %s AND reproducida = FALSE",
            (sala_id,)
        ).fetchone()
        current_pos = row[0] if row and row[0] is not None else -1
        
        if current_pos == -1:
            pos_actual = 0
        else:
            conn.execute(
                "UPDATE rockola_cola SET posicion = posicion + 1 WHERE sala_id = %s AND reproducida = FALSE AND posicion > %s",
                (sala_id, current_pos)
            )
            pos_actual = current_pos + 1
    else:
        # 'final'
        pos_actual = _max_pos(conn, sala_id) + 1

    conn.execute(
        """
        INSERT INTO rockola_cola
            (id, sala_id, nombre, tercero_id, posicion, lista_envio_id, lista_envio_nombre, lista_envio_posicion, youtube_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            archivo_id,
            sala_id,
            nombre,
            tid,
            pos_actual,
            lista_envio.get('id'),
            lista_envio.get('nombre'),
            lista_envio.get('posicion'),
            youtube_url,
        ),
    )


def _upload_dir(sala_id):
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp')
    folder = os.path.join(base, sala_id)
    os.makedirs(folder, exist_ok=True)
    return folder


def _limpiar_archivos_antiguos(upload_dir, max_archivos=10):
    try:
        archivos = []
        for f in os.listdir(upload_dir):
            path = os.path.join(upload_dir, f)
            if os.path.isfile(path):
                archivos.append((path, os.path.getmtime(path)))
        archivos.sort(key=lambda x: x[1])
        if len(archivos) > max_archivos:
            a_borrar = archivos[:len(archivos) - max_archivos]
            for path, _ in a_borrar:
                try:
                    os.remove(path)
                except Exception:
                    pass
    except Exception:
        pass


def _limpiar_salas_temporales_antiguas():
    try:
        import shutil
        import time
        base = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp')
        if os.path.exists(base):
            now = time.time()
            for name in os.listdir(base):
                path = os.path.join(base, name)
                if os.path.isdir(path):
                    if now - os.path.getmtime(path) > 86400:
                        shutil.rmtree(path)
    except Exception:
        pass


def _share_dir(share_id=None):
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_share')
    os.makedirs(base, exist_ok=True)
    if not share_id:
        return base
    folder = os.path.join(base, share_id)
    os.makedirs(folder, exist_ok=True)
    return folder


def _limpiar_compartidos_antiguos():
    try:
        import shutil
        import time
        base = _share_dir()
        now = time.time()
        for name in os.listdir(base):
            path = os.path.join(base, name)
            if os.path.isdir(path):
                if now - os.path.getmtime(path) > 3600:
                    shutil.rmtree(path)
    except Exception:
        pass


def _share_manifest_path(share_id):
    return os.path.join(_share_dir(share_id), 'manifest.json')


def _read_share_manifest(share_id):
    path = _share_manifest_path(share_id)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_share_manifest(share_id, manifest):
    with open(_share_manifest_path(share_id), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False)


def _build_share_manifest(share_id, metadata):
    canciones = []
    for cancion in metadata.get('canciones') or []:
        local_id = (cancion.get('local_id') or '').strip()
        if not local_id:
            continue
        canciones.append({
            'id': None,
            'local_id_origen': local_id,
            'nombre': cancion.get('archivo_nombre') or cancion.get('titulo') or 'Cancion',
            'titulo': cancion.get('titulo') or cancion.get('archivo_nombre') or 'Cancion',
            'tamano_bytes': int(cancion.get('tamano_bytes') or 0),
            'mime': cancion.get('mime') or 'audio/mpeg',
        })
    return {
        'share_id': share_id,
        'nombre': (metadata.get('nombre') or 'Biblioteca compartida')[:160],
        'dispositivo': metadata.get('dispositivo') or {},
        'canciones': canciones,
        'listas': metadata.get('listas') or [],
    }


def _share_url(share_id):
    return f'https://rockola.tuc-tuc.co/rockola/compartir/{share_id}'


def _attach_share_file(manifest, local_id, file, archivo_id):
    canciones = manifest.setdefault('canciones', [])
    meta = next((c for c in canciones if c.get('local_id_origen') == local_id), None)
    if not meta:
        meta = {'local_id_origen': local_id}
        canciones.append(meta)
    meta.update({
        'id': archivo_id,
        'nombre': meta.get('nombre') or file.filename or 'Cancion',
        'titulo': meta.get('titulo') or os.path.splitext(file.filename or 'Cancion')[0],
        'tamano_bytes': int(meta.get('tamano_bytes') or 0),
        'mime': meta.get('mime') or file.mimetype or 'audio/mpeg',
    })


def _es_admin_sala(conn, sala_id, data):
    if data.get('modo') == 'reproductor':
        return True
    admin_key = (data.get('admin_key') or request.headers.get('X-Rockola-Admin-Key') or '').strip()
    if not admin_key:
        return False
    sala = _get_sala(conn, sala_id)
    return admin_key == (sala.get('admin_key') or '')


def _reset_sync(conn, sala_id):
    conn.execute(
        """
        UPDATE rockola_salas
        SET sync_estado = 'play', sync_pos = 0.0, sync_ts = 0.0
        WHERE sala_id = %s
        """,
        (sala_id,),
    )


def _normalizar_volumen(valor):
    try:
        volumen = int(valor)
    except (TypeError, ValueError):
        volumen = 80
    return max(0, min(100, volumen))


def _sala_para_dispositivo(sala, dispositivo_id=None):
    owner_id = sala.get('dispositivo_reproductor_id') or ''
    sin_reproductor = not owner_id
    disponible = bool(dispositivo_id) and owner_id == dispositivo_id
    return {
        'sala_id': sala.get('sala_id'),
        'dispositivo_reproductor_id': owner_id,
        'dispositivo_reproductor_nombre': sala.get('dispositivo_reproductor_nombre') or '',
        'disponible_reproductor': disponible,
        'sin_reproductor': sin_reproductor,
        'puede_agregar': True,
    }


@bp.route('/verificar-telefono')
def verificar_telefono():
    telefono = (request.args.get('tel') or '').strip()
    tel_limpio = ''.join(c for c in telefono if c.isdigit())
    if not tel_limpio:
        return jsonify(ok=False, error='Teléfono inválido'), 400

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, nombre, pin_seguridad FROM terceros WHERE REGEXP_REPLACE(COALESCE(telefono, ''), '[^0-9]', '', 'g') = %s LIMIT 1",
            (tel_limpio,),
        ).fetchone()
        tiene_pin = bool(row and row['pin_seguridad'])
        return jsonify(ok=True, existe=bool(row), tiene_pin=tiene_pin, nombre=row['nombre'] if row else None)
    finally:
        conn.close()


@bp.route('/identificar', methods=['POST'])
def identificar():
    data = request.get_json() or {}
    telefono = (data.get('telefono') or '').strip()
    nombre = (data.get('nombre') or '').strip()
    pin = (data.get('pin') or '').strip()

    tel_limpio = ''.join(c for c in telefono if c.isdigit())
    if not tel_limpio:
        return jsonify(ok=False, error='Teléfono requerido'), 400

    if len(pin) != 4 or not pin.isdigit():
        return jsonify(ok=False, error='El PIN debe tener 4 números'), 400

    conn = _connect()
    try:
        tercero = conn.execute(
            "SELECT id, nombre, pin_seguridad FROM terceros WHERE REGEXP_REPLACE(COALESCE(telefono, ''), '[^0-9]', '', 'g') = %s LIMIT 1",
            (tel_limpio,),
        ).fetchone()

        if tercero:
            if tercero['pin_seguridad']:
                if not check_password_hash(tercero['pin_seguridad'], pin):
                    return jsonify(ok=False, error='PIN incorrecto'), 401
            else:
                pin_hash = generate_password_hash(pin)
                conn.execute(
                    "UPDATE terceros SET pin_seguridad = %s WHERE id = %s",
                    (pin_hash, tercero['id']),
                )
                conn.commit()
            
            tercero_id = tercero['id']
            nombre_final = tercero['nombre']
        else:
            if not nombre:
                return jsonify(ok=False, error='Nombre requerido para registro nuevo'), 400
            
            pin_hash = generate_password_hash(pin)
            cur = conn.execute(
                "INSERT INTO terceros (nombre, telefono, pin_seguridad, tipo_tercero) VALUES (%s, %s, %s, 'invitado') RETURNING id",
                (nombre, telefono, pin_hash),
            )
            tercero_id = cur.fetchone()['id']
            conn.commit()
            nombre_final = nombre

        session['usuario_id'] = tercero_id
        session['nombre'] = nombre_final
        session['telefono'] = telefono
        session['rol'] = 'Cliente'

        return jsonify(ok=True, tercero_id=tercero_id, nombre=nombre_final)
    finally:
        conn.close()


@bp.route('/actualizar-perfil', methods=['POST'])
def actualizar_perfil():
    tercero_id = session.get('usuario_id')
    if not tercero_id:
        return jsonify(ok=False, error='Sesión no iniciada'), 401

    data = request.get_json() or {}
    nombre = (data.get('nombre') or '').strip()
    pin_actual = (data.get('pin_actual') or '').strip()
    pin_nuevo = (data.get('pin_nuevo') or '').strip()

    if not nombre:
        return jsonify(ok=False, error='El nombre es requerido'), 400

    conn = get_db_connection()
    try:
        tercero = conn.execute(
            "SELECT pin_seguridad, telefono FROM terceros WHERE id = %s",
            (tercero_id,)
        ).fetchone()

        if not tercero:
            return jsonify(ok=False, error='Tercero no encontrado'), 404

        if tercero['pin_seguridad']:
            if not pin_actual:
                return jsonify(ok=False, error='PIN actual requerido para realizar cambios'), 400
            if not check_password_hash(tercero['pin_seguridad'], pin_actual):
                return jsonify(ok=False, error='PIN actual incorrecto'), 401

        if pin_nuevo:
            if len(pin_nuevo) != 4 or not pin_nuevo.isdigit():
                return jsonify(ok=False, error='El nuevo PIN debe tener 4 números'), 400
            new_hash = generate_password_hash(pin_nuevo)
            conn.execute(
                "UPDATE terceros SET nombre = %s, pin_seguridad = %s WHERE id = %s",
                (nombre, new_hash, tercero_id)
            )
        else:
            conn.execute(
                "UPDATE terceros SET nombre = %s WHERE id = %s",
                (nombre, tercero_id)
            )
        conn.commit()

        session['nombre'] = nombre
        return jsonify(ok=True, nombre=nombre, telefono=tercero['telefono'])
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
    finally:
        conn.close()


@bp.route('/')
def entrada():
    return render_template('rockola_entrada.html')


@bp.route('/pwa/manifest.json')
def pwa_manifest():
    host_limpio = (request.host or '').split(':')[0].strip().lower().rstrip('.')
    es_subdominio = (host_limpio == 'rockola.tuc-tuc.co')
    start_url = "/" if es_subdominio else "/rockola/"
    scope = "/" if es_subdominio else "/rockola/"

    manifest = {
        "id": "/rockola/",
        "name": "Mi Rockola",
        "short_name": "Rockola",
        "description": "Rockola Tuc Tuc con biblioteca local y modo offline",
        "start_url": start_url,
        "scope": scope,
        "display": "standalone",
        "background_color": "#060c18",
        "theme_color": "#00d4ff",
        "icons": [
            {"src": "/static/rockola-icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/rockola-icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/rockola-icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return Response(json.dumps(manifest), mimetype='application/manifest+json')


@bp.route('/pwa/sw.js')
def pwa_sw():
    js = """
const CACHE = 'rockola-pwa-v7';
const CORE = [
  '/rockola',
  '/rockola/',
  '/rockola/pwa/offline',
  '/rockola/pwa/manifest.json',
  '/static/rockola-icon-192.png',
  '/static/rockola-icon-512.png',
  '/static/rockola-icon-maskable-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE).then(async cache => {
      for (const url of CORE) {
        try {
          await cache.add(url);
        } catch (e) {
          console.warn('[SW] No se pudo precachear:', url, e);
        }
      }
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Fallback offline para navegación
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then(res => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE).then(cache => cache.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(async () => {
          const hit = await caches.match(req);
          if (hit) return hit;
          const offlinePage = await caches.match('/rockola/pwa/offline');
          if (offlinePage) return offlinePage;
          return caches.match('/rockola/');
        })
    );
    return;
  }

  // Caché de estáticos
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/rockola/pwa/')) {
    event.respondWith(
      caches.match(req).then(hit => {
        if (hit) return hit;
        return fetch(req).then(res => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE).then(cache => cache.put(req, copy)).catch(() => {});
          }
          return res;
        }).catch(() => null);
      })
    );
  }
});
"""
    resp = Response(js, mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@bp.route('/pwa/offline')
def pwa_offline():
    resp = make_response(render_template('rockola_reproductor.html', sala_id='local', admin_key=''))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@bp.route('/compartir/biblioteca', methods=['POST'])
def compartir_biblioteca():
    share_id = uuid.uuid4().hex[:12]
    folder = _share_dir(share_id)
    metadata_raw = request.form.get('metadata') or '{}'
    try:
        metadata = json.loads(metadata_raw)
    except Exception:
        metadata = {}

    manifest = _build_share_manifest(share_id, metadata)
    for file in request.files.getlist('archivo'):
        local_id = (file.filename or '').strip()
        ext = os.path.splitext(file.filename or 'audio.mp3')[1].lower() or '.mp3'
        archivo_id = uuid.uuid4().hex + ext
        file.save(os.path.join(folder, archivo_id))
        _attach_share_file(manifest, local_id, file, archivo_id)

    _write_share_manifest(share_id, manifest)

    return jsonify(ok=True, share_id=share_id, url=_share_url(share_id))


@bp.route('/compartir/biblioteca/iniciar', methods=['POST'])
def compartir_biblioteca_iniciar():
    _limpiar_compartidos_antiguos()
    data = request.get_json(silent=True) or {}
    metadata = data.get('metadata') or data
    share_id = uuid.uuid4().hex[:12]
    _share_dir(share_id)
    manifest = _build_share_manifest(share_id, metadata if isinstance(metadata, dict) else {})
    _write_share_manifest(share_id, manifest)
    return jsonify(ok=True, share_id=share_id, url=_share_url(share_id))


@bp.route('/compartir/<share_id>/archivo', methods=['POST'])
def compartir_biblioteca_subir_archivo(share_id):
    local_id = (request.form.get('local_id') or '').strip()
    file = request.files.get('archivo')
    if not local_id or not file:
        return jsonify(ok=False, error='Falta la cancion para compartir'), 400
    manifest = _read_share_manifest(share_id)
    if not manifest:
        return jsonify(ok=False, error='Biblioteca compartida no encontrada'), 404
    ext = os.path.splitext(file.filename or 'audio.mp3')[1].lower() or '.mp3'
    archivo_id = uuid.uuid4().hex + ext
    file.save(os.path.join(_share_dir(share_id), archivo_id))
    _attach_share_file(manifest, local_id, file, archivo_id)
    _write_share_manifest(share_id, manifest)
    return jsonify(ok=True, archivo_id=archivo_id)


@bp.route('/compartir/<share_id>')
def compartir_biblioteca_page(share_id):
    return render_template('rockola_compartir.html', share_id=share_id)


@bp.route('/compartir/<share_id>/eliminar', methods=['POST'])
def compartir_biblioteca_eliminar(share_id):
    try:
        import shutil
        folder = _share_dir(share_id)
        if os.path.exists(folder):
            shutil.rmtree(folder)
    except Exception:
        pass
    return jsonify(ok=True)


@bp.route('/compartir/<share_id>/manifest')
def compartir_biblioteca_manifest(share_id):
    manifest = _read_share_manifest(share_id)
    if not manifest:
        return jsonify(ok=False, error='Biblioteca compartida no encontrada'), 404
    return jsonify(ok=True, **manifest)


@bp.route('/compartir/<share_id>/archivo/<archivo_id>')
def compartir_biblioteca_archivo(share_id, archivo_id):
    return send_from_directory(_share_dir(share_id), archivo_id)


# Compartir canciones individuales (WhatsApp, enlaces publicos y captacion de terceros)

@bp.route('/<sala_id>/compartir-local', methods=['POST'])
def compartir_local(sala_id):
    """Guarda un archivo de audio local del reproductor en el servidor para poder compartirlo."""
    try:
        file = request.files.get('archivo')
        nombre = (request.form.get('nombre') or (file.filename if file else '')).strip()
        if not file or not nombre:
            return jsonify(ok=False, error='Archivo o nombre faltante'), 400
        upload_dir = _upload_dir(sala_id)
        ext = os.path.splitext(file.filename or 'audio.mp3')[1].lower() or '.mp3'
        archivo_id = uuid.uuid4().hex + ext
        file.save(os.path.join(upload_dir, archivo_id))
        return jsonify(ok=True, archivo_id=archivo_id, nombre=nombre)
    except Exception as e:
        return jsonify(ok=False, error=f"Error guardando audio local: {str(e)}"), 500


@bp.route('/compartir/generar', methods=['POST'])
def compartir_cancion_generar():
    """Genera token de cancion compartida, registra/vincula a terceros en BD y entrega link con WhatsApp."""
    data = request.get_json(silent=True) or {}
    sala_id = (data.get('sala_id') or 'default').strip()
    nombre = (data.get('nombre') or 'Canción').strip()
    origen = (data.get('origen') or 'youtube').strip()
    youtube_url = (data.get('youtube_url') or '').strip()
    archivo_id = (data.get('archivo_id') or '').strip()
    amigo_nombre = (data.get('amigo_nombre') or '').strip()
    amigo_telefono = (data.get('amigo_telefono') or '').strip()

    conn = _connect()
    try:
        # Si no se pasó archivo_id, verificar si la canción ya existe en el servidor para reutilizarla
        if origen == 'archivo' and not archivo_id:
            row_prev = conn.execute("""
                SELECT archivo_id FROM rockola_compartidos 
                WHERE sala_id = %s AND LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) 
                  AND archivo_id IS NOT NULL AND archivo_id != ''
                ORDER BY creado_en DESC LIMIT 1
            """, (sala_id, nombre)).fetchone()
            if not row_prev:
                row_prev = conn.execute("""
                    SELECT archivo_id FROM rockola_biblioteca 
                    WHERE sala_id = %s AND LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) 
                      AND archivo_id IS NOT NULL AND archivo_id != ''
                    ORDER BY creado_en DESC LIMIT 1
                """, (sala_id, nombre)).fetchone()
            if row_prev and row_prev['archivo_id']:
                archivo_id = row_prev['archivo_id']

        tercero_id = None
        tel_limpio = ''.join(c for c in amigo_telefono if c.isdigit())
        if tel_limpio:
            row = conn.execute(
                "SELECT id, nombre FROM terceros WHERE REGEXP_REPLACE(COALESCE(telefono, ''), '[^0-9]', '', 'g') = %s LIMIT 1",
                (tel_limpio,)
            ).fetchone()
            if row:
                tercero_id = row['id']
                if amigo_nombre and (not row['nombre'] or row['nombre'].lower() in ('invitado', 'cliente', 'amigo')):
                    conn.execute("UPDATE terceros SET nombre = %s WHERE id = %s", (amigo_nombre, tercero_id))
                    conn.commit()
            else:
                nom = amigo_nombre or 'Amigo'
                nuevo = conn.execute(
                    "INSERT INTO terceros (nombre, telefono, tipo_tercero) VALUES (%s, %s, 'invitado') RETURNING id",
                    (nom, tel_limpio)
                ).fetchone()
                tercero_id = nuevo['id']
                conn.commit()
        elif amigo_nombre:
            nuevo = conn.execute(
                "INSERT INTO terceros (nombre, tipo_tercero) VALUES (%s, 'invitado') RETURNING id",
                (amigo_nombre,)
            ).fetchone()
            tercero_id = nuevo['id']
            conn.commit()

        # Obtener o asegurar el tercero_id del emisor (tu usuario tercero)
        creado_por = session.get('chat_tercero_id') or session.get('tercero_id')
        if not creado_por and session.get('usuario_id'):
            try:
                uid = int(session.get('usuario_id'))
                if conn.execute("SELECT 1 FROM terceros WHERE id = %s", (uid,)).fetchone():
                    creado_por = uid
            except (ValueError, TypeError):
                pass

        if not creado_por and session.get('nombre'):
            nom_emisor = session.get('nombre').strip()
            r_emisor = conn.execute(
                "SELECT id FROM terceros WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) LIMIT 1",
                (nom_emisor,)
            ).fetchone()
            if r_emisor:
                creado_por = r_emisor['id']
            else:
                rol_emisor = (session.get('rol') or 'admin').lower()
                r_nuevo = conn.execute(
                    "INSERT INTO terceros (nombre, tipo_tercero) VALUES (%s, %s) RETURNING id",
                    (nom_emisor, rol_emisor)
                ).fetchone()
                conn.commit()
                creado_por = r_nuevo['id']
            session['chat_tercero_id'] = creado_por

        if tercero_id:
            try:
                tercero_id_int = int(tercero_id)
                val = conn.execute("SELECT id FROM terceros WHERE id = %s", (tercero_id_int,)).fetchone()
                tercero_id = tercero_id_int if val else None
            except (ValueError, TypeError):
                tercero_id = None

        if creado_por:
            try:
                cp_int = int(creado_por)
                val_cp = conn.execute("SELECT id FROM terceros WHERE id = %s", (cp_int,)).fetchone()
                creado_por = cp_int if val_cp else None
            except (ValueError, TypeError):
                creado_por = None

        token = uuid.uuid4().hex[:10]
        conn.execute("""
            INSERT INTO rockola_compartidos (token, sala_id, nombre, origen, youtube_url, archivo_id, tercero_id, creado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (token, sala_id, nombre, origen, youtube_url, archivo_id, tercero_id, creado_por))
        conn.commit()

        base_url = request.host_url.rstrip('/')
        url_compartir = f"{base_url}/rockola/c/{token}"

        if amigo_nombre:
            primer_nombre = amigo_nombre.strip().split(' ')[0]
            mensaje_wa = f"🎵 *{nombre}*\n\n¡Hola {primer_nombre}! ¡escúchala aquí en Mi Rockola! 👇\n{url_compartir}"
        else:
            mensaje_wa = f"🎵 *{nombre}*\n\n¡Escúchala aquí en Mi Rockola y pide la tuya! 👇\n{url_compartir}"

        wa_text_quoted = urllib.parse.quote(mensaje_wa)
        wa_url = f"https://api.whatsapp.com/send?text={wa_text_quoted}"
        if tel_limpio:
            tel_wa = tel_limpio if tel_limpio.startswith('57') else ('57' + tel_limpio if len(tel_limpio) == 10 else tel_limpio)
            wa_url = f"https://api.whatsapp.com/send?phone={tel_wa}&text={wa_text_quoted}"

        return jsonify(
            ok=True,
            token=token,
            url=url_compartir,
            mensaje_wa=mensaje_wa,
            wa_url=wa_url,
            tercero_id=tercero_id,
            amigo_nombre=amigo_nombre
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify(ok=False, error=f"Error generando enlace: {str(e)}"), 500
    finally:
        conn.close()


@bp.route('/c/<token>')
def escuchar_cancion_compartida(token):
    """Pagina de escucha publica ultraligera para WhatsApp y enlaces compartidos."""
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT rc.*, t.nombre AS destinatario_nombre, t.telefono AS destinatario_telefono
            FROM rockola_compartidos rc
            LEFT JOIN terceros t ON t.id = rc.tercero_id
            WHERE rc.token = %s
        """, (token,)).fetchone()
        if not row:
            return render_template('rockola_escuchar.html', no_encontrada=True), 404

        conn.execute("UPDATE rockola_compartidos SET visitas = visitas + 1 WHERE token = %s", (token,))
        conn.commit()

        destinatario = row['destinatario_nombre'] or ''
        if destinatario:
            primer_nombre = destinatario.strip().split(' ')[0]
            saludo = f"¡Hola {primer_nombre}! ¡escúchala!"
        else:
            saludo = "¡Escúchala!"

        base_url = request.host_url.rstrip('/')
        yt_id = _extraer_youtube_id(row['youtube_url']) if row['youtube_url'] else ''

        return render_template(
            'rockola_escuchar.html',
            token=token,
            cancion={
                'nombre': row['nombre'],
                'origen': row['origen'],
                'youtube_url': row['youtube_url'] or '',
                'youtube_id': yt_id,
                'archivo_id': row['archivo_id'] or '',
            },
            sala_id=row['sala_id'],
            destinatario_id=row['tercero_id'] or '',
            destinatario_nombre=row['destinatario_nombre'] or '',
            destinatario_telefono=row['destinatario_telefono'] or '',
            saludo=saludo,
            base_url=base_url
        )
    finally:
        conn.close()


@bp.route('/c/<token>/audio')
def audio_cancion_compartida(token):
    """Streaming de audio con soporte de HTTP Range y búsqueda flexible para la canción compartida."""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM rockola_compartidos WHERE token = %s", (token,)).fetchone()
        if not row:
            return jsonify(ok=False, error='No encontrada'), 404
        if row['origen'] == 'archivo' and row['archivo_id']:
            upload_dir = _upload_dir(row['sala_id'])
            target_dir = upload_dir
            target_file = row['archivo_id']
            if not os.path.exists(os.path.join(upload_dir, target_file)):
                # Buscar en toda la estructura de static/rockola_tmp
                base_tmp = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp')
                for root, _, files in os.walk(base_tmp):
                    if target_file in files:
                        target_dir = root
                        break
            return send_from_directory(target_dir, target_file, conditional=True, mimetype='audio/mpeg')
        return jsonify(ok=False, error='Audio no disponible'), 400
    finally:
        conn.close()


@bp.route('/registro-rapido', methods=['POST'])
def registro_rapido_rockola():
    """Registro rapido de oyentes en tabla terceros al pedir canciones."""
    data = request.get_json(silent=True) or {}
    nombre = (data.get('nombre') or '').strip()
    telefono = (data.get('telefono') or '').strip()
    if not nombre or not telefono:
        return jsonify(ok=False, error='Nombre y teléfono requeridos'), 400

    tel_limpio = ''.join(c for c in telefono if c.isdigit())
    if len(tel_limpio) < 7:
        return jsonify(ok=False, error='Teléfono inválido (mínimo 7 dígitos)'), 400

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, nombre, pin_seguridad FROM terceros WHERE REGEXP_REPLACE(COALESCE(telefono, ''), '[^0-9]', '', 'g') = %s LIMIT 1",
            (tel_limpio,)
        ).fetchone()
        if row:
            tercero_id = row['id']
            if nombre and (not row['nombre'] or row['nombre'].lower() in ('invitado', 'cliente', 'amigo')):
                conn.execute("UPDATE terceros SET nombre = %s WHERE id = %s", (nombre, tercero_id))
                conn.commit()
            nombre_final = row['nombre'] or nombre
        else:
            cur = conn.execute(
                "INSERT INTO terceros (nombre, telefono, tipo_tercero) VALUES (%s, %s, 'invitado') RETURNING id",
                (nombre, tel_limpio)
            )
            tercero_id = cur.fetchone()['id']
            conn.commit()
            nombre_final = nombre

        session['usuario_id'] = tercero_id
        session['nombre'] = nombre_final
        session['telefono'] = tel_limpio
        session['rol'] = 'Cliente'

        return jsonify(ok=True, tercero_id=tercero_id, nombre=nombre_final, telefono=tel_limpio)
    finally:
        conn.close()


def _asegurar_conversacion_chat_peticion(conn, dj_id, oyente_id, nombre_oyente):
    if not dj_id or not oyente_id or dj_id == oyente_id:
        return None
    try:
        conv = conn.execute("""
            SELECT id, token FROM conversaciones
            WHERE (creador_id = %s AND invitado_id = %s)
               OR (creador_id = %s AND invitado_id = %s)
            ORDER BY id ASC LIMIT 1
        """, (dj_id, oyente_id, oyente_id, dj_id)).fetchone()
        if conv:
            return conv
        import secrets
        token_conv = secrets.token_urlsafe(12)
        conv = conn.execute("""
            INSERT INTO conversaciones (creador_id, invitado_id, token, nombre_invitado, origen, activa)
            VALUES (%s, %s, %s, %s, 'rockola', TRUE)
            RETURNING id, token
        """, (dj_id, oyente_id, token_conv, nombre_oyente or 'Oyente')).fetchone()
        conn.commit()
        return conv
    except Exception as e:
        print(f"[chat_peticion] Warning asegurando conversación: {e}")
        return None


def _enviar_mensaje_chat_peticion(conn, dj_id, oyente_id, oyente_nombre, cancion, autodespachada=False):
    try:
        conv = _asegurar_conversacion_chat_peticion(conn, dj_id, oyente_id, oyente_nombre)
        if not conv:
            return
        if autodespachada:
            msg_texto = f'⚡ ¡Pedí "{cancion}" en la Rockola y se reprodujo automáticamente!'
        else:
            msg_texto = f'🎧 Hola DJ, ¿puedes poner esta canción en la Rockola? 👉 "{cancion}"'

        conn.execute("""
            INSERT INTO mensajes (remitente_id, destinatario_id, mensaje, tipo, conversacion_id, estado, fecha)
            VALUES (%s, %s, %s, 'cancion', %s, 'pendiente', CURRENT_TIMESTAMP)
        """, (oyente_id, dj_id, msg_texto, conv['id']))
        conn.commit()

        # Push notification al DJ
        try:
            from .crm import _despachar_push_asincrono
            _despachar_push_asincrono(
                dj_id,
                f"🎧 Petición Rockola · {oyente_nombre or 'Oyente'}",
                msg_texto,
                token=conv['token'],
                url=f"/chat2?open_token={conv['token']}"
            )
        except Exception:
            pass
    except Exception as e:
        print(f"[chat_peticion] Warning enviando mensaje: {e}")


@bp.route('/c/<token>/sugerencias')
def sugerencias_canciones_compartidas(token):
    """Buscador del vinilo WhatsApp: MISMO núcleo y shape que buscar-global (un solo buscador)."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify(ok=True, servidor=[], usuarios=[], youtube=[])

    conn = _connect()
    try:
        row_comp = conn.execute("SELECT sala_id FROM rockola_compartidos WHERE token = %s", (token,)).fetchone()
        if not row_comp:
            return jsonify(ok=False, error='Token no válido'), 404
        servidor_items, usuarios_items, youtube_items = _nucleo_busqueda_rockola(conn, q)
        return jsonify(
            ok=True,
            servidor=servidor_items,
            usuarios=usuarios_items,
            youtube=youtube_items
        )
    finally:
        conn.close()


def _fmt_dur_seg(seg):
    """Segundos -> 'm:ss' ('' si no hay dato)."""
    try:
        total = int(float(seg or 0))
    except (TypeError, ValueError):
        return ''
    if total <= 0:
        return ''
    return f"{total // 60}:{total % 60:02d}"


def _duracion_video_youtube(url):
    """Duración 'm:ss' de un video vía yt_dlp ('' si falla)."""
    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noplaylist': True,
            'no_warnings': True,
            'socket_timeout': 8,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return _fmt_dur_seg((info or {}).get('duration'))
    except Exception as e:
        print(f"[yt_duracion] Warning {url}: {e}")
        return ''


def _buscar_youtube_en_vivo(query, max_results=5):
    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'skip_download': True,
            'noplaylist': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            items = []
            for e in (res.get('entries') or []):
                if not e:
                    continue
                dur_str = _fmt_dur_seg(e.get('duration'))
                vid_id = e.get('id')
                if not vid_id:
                    continue
                items.append({
                    'id': vid_id,
                    'nombre': e.get('title') or 'Video de YouTube',
                    'canal': e.get('uploader') or '',
                    'duracion': dur_str,
                    'youtube_url': f"https://www.youtube.com/watch?v={vid_id}",
                    'origen': 'youtube'
                })
            return items
    except Exception as e:
        print(f"[buscar_youtube_en_vivo] Warning buscando YouTube: {e}")
        return []


@bp.route('/yt-duracion')
def duracion_youtube_guardada():
    """Duración de un enlace YouTube guardado: caché en biblioteca/compartidos, si no probea y guarda."""
    url = (request.args.get('url') or '').strip()
    vid = _extraer_youtube_id(url)
    if not vid:
        return jsonify(ok=False, error='URL inválida'), 400
    conn = _connect()
    try:
        with _lock:
            for tabla in ('rockola_biblioteca', 'rockola_compartidos'):
                rows = conn.execute(
                    "SELECT youtube_url, duracion FROM %s WHERE youtube_url ILIKE %%s" % tabla,
                    (f"%{vid}%",),
                ).fetchall()
                for r in rows:
                    if _extraer_youtube_id(r['youtube_url']) == vid and (r['duracion'] or '').strip():
                        return jsonify(ok=True, duracion=r['duracion'].strip(), cache=True)
            dur = _duracion_video_youtube(url)
            if dur:
                for tabla in ('rockola_biblioteca', 'rockola_compartidos'):
                    conn.execute(
                        "UPDATE %s SET duracion = %%s WHERE youtube_url ILIKE %%s AND (duracion IS NULL OR duracion = '')" % tabla,
                        (dur, f"%{vid}%"),
                    )
                conn.commit()
            return jsonify(ok=True, duracion=dur, cache=False)
    finally:
        conn.close()


def _filtrar_youtube_guardados(youtube_items, servidor_items):
    """Saca de YouTube-en-vivo los videos cuyo ID ya está guardado en servidor/biblioteca."""
    guardados = set()
    for s in (servidor_items or []):
        yt = _extraer_youtube_id(s.get('youtube_url'))
        if yt:
            guardados.add(yt)
    if not guardados:
        return list(youtube_items or [])
    return [y for y in (youtube_items or [])
            if (_extraer_youtube_id(y.get('youtube_url')) or y.get('id')) not in guardados]


def _evaluar_validacion(sonados_seg, duracion_seg, evento):
    """Regla Rafa: sono >= 30% de la duracion => era lo que queria. Repetir/guardar/compartir validan directo."""
    try:
        sonados = float(sonados_seg or 0)
    except (TypeError, ValueError):
        sonados = 0.0
    try:
        duracion = float(duracion_seg or 0)
    except (TypeError, ValueError):
        duracion = 0.0
    ratio = round(sonados / duracion, 4) if duracion > 0 else 0.0
    if evento in ('repetir', 'guardar', 'compartir'):
        return ratio, True
    return ratio, ratio >= 0.30


def _nucleo_busqueda_rockola(conn, q):
    """Núcleo ÚNICO del buscador rockola: Servidor + Catálogo + YouTube con dedupe.

    Lo usan buscar-global (reproductor) y sugerencias (vinilo WhatsApp).
    Retorna (servidor_items, usuarios_items, youtube_items)."""
    q_like = f"%{q}%"

    # 1. Servidor (Canciones listas con audio o youtube)
    rows_servidor = conn.execute("""
        SELECT DISTINCT ON (LOWER(TRIM(nombre))) nombre, origen, archivo_id, youtube_url FROM (
            SELECT nombre, origen, archivo_id, youtube_url FROM rockola_compartidos
            WHERE (archivo_id IS NOT NULL AND archivo_id != '') OR (youtube_url IS NOT NULL AND youtube_url != '')
            UNION
            SELECT nombre, origen, archivo_id, youtube_url FROM rockola_biblioteca
            WHERE (archivo_id IS NOT NULL AND archivo_id != '') OR (youtube_url IS NOT NULL AND youtube_url != '')
        ) s
        WHERE nombre ILIKE %s
        LIMIT 6
    """, (q_like,)).fetchall()

    servidor_items = []
    for r in rows_servidor:
        servidor_items.append({
            'nombre': r['nombre'],
            'origen': r['origen'],
            'archivo_id': r['archivo_id'] or '',
            'youtube_url': r['youtube_url'] or ''
        })

    # 2. Catálogo de otros usuarios indexados (sin repetir servidor)
    rows_usuarios = conn.execute("""
        SELECT cancion_id, titulo as nombre FROM rockola_canciones
        WHERE titulo ILIKE %s OR archivo_nombre ILIKE %s
        ORDER BY titulo ASC
        LIMIT 6
    """, (q_like, q_like)).fetchall()

    usuarios_items = []
    for r in rows_usuarios:
        nom_norm = r['nombre'].lower().strip()
        if not any(s['nombre'].lower().strip() == nom_norm for s in servidor_items):
            usuarios_items.append({
                'id': r['cancion_id'],
                'nombre': r['nombre'],
                'origen': 'usuarios'
            })

    # 3. YouTube en vivo nativo (sin repetir enlaces ya guardados en biblioteca)
    youtube_items = _buscar_youtube_en_vivo(q, max_results=5)
    youtube_items = _filtrar_youtube_guardados(youtube_items, servidor_items)

    return servidor_items, usuarios_items, youtube_items


@bp.route('/<sala_id>/buscar-global')
def buscar_global(sala_id):
    """Buscador global multifuente: Servidor, Catálogo de usuarios y YouTube en vivo."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify(ok=True, servidor=[], usuarios=[], youtube=[])

    conn = _connect()
    try:
        servidor_items, usuarios_items, youtube_items = _nucleo_busqueda_rockola(conn, q)

        return jsonify(
            ok=True,
            servidor=servidor_items,
            usuarios=usuarios_items,
            youtube=youtube_items
        )
    finally:
        conn.close()


@bp.route('/c/<token>/pedir', methods=['POST'])
def peticion_cancion_compartida(token):
    """El oyente remoto pide una cancion al DJ en vivo desde el vinilo web con auto-despacho inteligente."""
    data = request.get_json(silent=True) or {}
    cancion = (data.get('cancion') or '').strip()
    nombre = (data.get('nombre') or '').strip()
    telefono = (data.get('telefono') or '').strip()

    if not cancion:
        return jsonify(ok=False, error='Escribe el nombre de la canción o artista'), 400

    conn = _connect()
    try:
        # Obtener sala y datos del token original
        row_comp = conn.execute("SELECT * FROM rockola_compartidos WHERE token = %s", (token,)).fetchone()
        if not row_comp:
            return jsonify(ok=False, error='Token no válido'), 404

        sala_id = row_comp['sala_id']
        tercero_id = row_comp['tercero_id']
        dj_id = row_comp['creado_por']

        if not dj_id:
            r_adm = conn.execute("SELECT id FROM terceros WHERE tipo_tercero IN ('admin', 'vendedor') ORDER BY id ASC LIMIT 1").fetchone()
            dj_id = r_adm['id'] if r_adm else None

        tel_limpio = ''.join(c for c in telefono if c.isdigit())
        if tel_limpio and len(tel_limpio) >= 7:
            row_t = conn.execute(
                "SELECT id, nombre FROM terceros WHERE REGEXP_REPLACE(COALESCE(telefono, ''), '[^0-9]', '', 'g') = %s LIMIT 1",
                (tel_limpio,)
            ).fetchone()
            if row_t:
                tercero_id = row_t['id']
                if nombre and (not row_t['nombre'] or row_t['nombre'].lower() in ('invitado', 'cliente', 'amigo')):
                    conn.execute("UPDATE terceros SET nombre = %s WHERE id = %s", (nombre, tercero_id))
                nombre = row_t['nombre'] or nombre
            else:
                cur = conn.execute(
                    "INSERT INTO terceros (nombre, telefono, tipo_tercero) VALUES (%s, %s, 'invitado') RETURNING id",
                    (nombre or 'Oyente Remoto', tel_limpio)
                )
                tercero_id = cur.fetchone()['id']
        elif not nombre and tercero_id:
            row_t = conn.execute("SELECT nombre, telefono FROM terceros WHERE id = %s", (tercero_id,)).fetchone()
            if row_t:
                nombre = row_t['nombre'] or 'Oyente'
                tel_limpio = row_t['telefono'] or ''

        # 1. Comprobar si la canción ya existe en el servidor para auto-despacho inmediato
        row_servidor = conn.execute("""
            SELECT nombre, origen, archivo_id, youtube_url FROM rockola_compartidos
            WHERE sala_id = %s AND LOWER(TRIM(nombre)) = LOWER(TRIM(%s))
              AND (
                  (origen = 'archivo' AND archivo_id IS NOT NULL AND archivo_id != '')
                  OR (origen = 'youtube' AND youtube_url IS NOT NULL AND youtube_url != '')
              )
            ORDER BY creado_en DESC LIMIT 1
        """, (sala_id, cancion)).fetchone()
        if not row_servidor:
            row_servidor = conn.execute("""
                SELECT nombre, origen, archivo_id, youtube_url FROM rockola_biblioteca
                WHERE sala_id = %s AND LOWER(TRIM(nombre)) = LOWER(TRIM(%s))
                  AND (
                      (origen = 'archivo' AND archivo_id IS NOT NULL AND archivo_id != '')
                      OR (origen = 'youtube' AND youtube_url IS NOT NULL AND youtube_url != '')
                  )
                ORDER BY creado_en DESC LIMIT 1
            """, (sala_id, cancion)).fetchone()

        if row_servidor:
            # ¡AUTO-DESPACHO INMEDIATO!
            nombre_final = row_servidor['nombre']
            origen_final = row_servidor['origen']
            archivo_id_final = row_servidor['archivo_id'] or ''
            youtube_url_final = row_servidor['youtube_url'] or ''
            yt_id = _extraer_youtube_id(youtube_url_final) if youtube_url_final else ''

            cur_p = conn.execute("""
                INSERT INTO rockola_peticiones (
                    sala_id, token_origen, solicitante_nombre, solicitante_telefono,
                    tercero_id, cancion_solicitada, estado,
                    respuesta_nombre, respuesta_origen, respuesta_youtube_url, respuesta_archivo_id,
                    despachado_en
                ) VALUES (%s, %s, %s, %s, %s, %s, 'despachada', %s, %s, %s, %s, CURRENT_TIMESTAMP)
                RETURNING id
            """, (sala_id, token, nombre or 'Oyente', tel_limpio or '', tercero_id, cancion,
                  nombre_final, origen_final, youtube_url_final, archivo_id_final))
            peticion_id = cur_p.fetchone()['id']

            # Actualizar rockola_compartidos de este token
            conn.execute("""
                UPDATE rockola_compartidos
                SET nombre = %s, origen = %s, youtube_url = %s, archivo_id = %s
                WHERE token = %s
            """, (nombre_final, origen_final, youtube_url_final, archivo_id_final, token))
            conn.commit()

            # Notificar chat 1 a 1 al DJ
            if dj_id and tercero_id:
                _enviar_mensaje_chat_peticion(conn, dj_id, tercero_id, nombre, cancion, autodespachada=True)

            return jsonify(
                ok=True,
                autodespachada=True,
                peticion_id=peticion_id,
                cancion={
                    'nombre': nombre_final,
                    'origen': origen_final,
                    'youtube_url': youtube_url_final,
                    'youtube_id': yt_id,
                    'archivo_id': archivo_id_final
                }
            )

        # Si NO está en el servidor: queda pendiente para el DJ
        cur_p = conn.execute("""
            INSERT INTO rockola_peticiones (
                sala_id, token_origen, solicitante_nombre, solicitante_telefono,
                tercero_id, cancion_solicitada, estado
            ) VALUES (%s, %s, %s, %s, %s, %s, 'pendiente')
            RETURNING id
        """, (sala_id, token, nombre or 'Oyente', tel_limpio or '', tercero_id, cancion))
        peticion_id = cur_p.fetchone()['id']
        conn.commit()

        # Notificar chat 1 a 1 al DJ
        if dj_id and tercero_id:
            _enviar_mensaje_chat_peticion(conn, dj_id, tercero_id, nombre, cancion, autodespachada=False)

        return jsonify(ok=True, autodespachada=False, peticion_id=peticion_id, mensaje='Petición enviada al DJ')
    finally:
        conn.close()


@bp.route('/c/<token>/estado-peticion')
def estado_peticion_compartida(token):
    """Consulta en tiempo real para el oyente remoto sobre si su peticion fue despachada."""
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT * FROM rockola_peticiones
            WHERE token_origen = %s
            ORDER BY id DESC LIMIT 1
        """, (token,)).fetchone()

        if not row:
            return jsonify(ok=True, tiene_peticion=False)

        if row['estado'] == 'pendiente':
            return jsonify(ok=True, tiene_peticion=True, estado='pendiente', cancion_solicitada=row['cancion_solicitada'])

        if row['estado'] == 'despachada':
            yt_id = _extraer_youtube_id(row['respuesta_youtube_url']) if row['respuesta_youtube_url'] else ''
            return jsonify(
                ok=True,
                tiene_peticion=True,
                estado='despachada',
                cancion={
                    'nombre': row['respuesta_nombre'],
                    'origen': row['respuesta_origen'],
                    'youtube_url': row['respuesta_youtube_url'] or '',
                    'youtube_id': yt_id,
                    'archivo_id': row['respuesta_archivo_id'] or ''
                }
            )

        return jsonify(ok=True, tiene_peticion=True, estado=row['estado'])
    finally:
        conn.close()


@bp.route('/api/<sala_id>/peticiones')
@bp.route('/peticiones/<sala_id>')
def listar_peticiones_dj(sala_id):
    """El reproductor consulta las peticiones en vivo hechas por oyentes remotos."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT id, sala_id, token_origen, solicitante_nombre, solicitante_telefono,
                   cancion_solicitada, estado, creado_en
            FROM rockola_peticiones
            WHERE sala_id = %s AND estado = 'pendiente'
            ORDER BY creado_en ASC
        """, (sala_id,)).fetchall()
        peticiones = []
        for r in rows:
            peticiones.append({
                'id': r['id'],
                'sala_id': r['sala_id'],
                'token_origen': r['token_origen'],
                'solicitante_nombre': r['solicitante_nombre'] or 'Oyente',
                'solicitante_telefono': r['solicitante_telefono'] or '',
                'cancion_solicitada': r['cancion_solicitada'],
                'creado_en': r['creado_en'].strftime('%H:%M') if r['creado_en'] else ''
            })
        return jsonify(ok=True, peticiones=peticiones)
    finally:
        conn.close()


@bp.route('/api/peticiones/<int:peticion_id>/despachar', methods=['POST'])
def despachar_peticion_dj(peticion_id):
    """El DJ despacha la peticion asignandole una cancion de YouTube o archivo del servidor."""
    data = request.get_json(silent=True) or {}
    nombre = (data.get('nombre') or '').strip()
    origen = data.get('origen', 'youtube')
    youtube_url = data.get('youtube_url', '')
    archivo_id = data.get('archivo_id', '')

    if not nombre:
        return jsonify(ok=False, error='Nombre de la canción requerido'), 400

    conn = _connect()
    try:
        # Si no se pasó archivo_id para una canción local, verificar si ya existe en el servidor
        if origen == 'archivo' and not archivo_id:
            row_prev = conn.execute("""
                SELECT archivo_id FROM rockola_compartidos 
                WHERE sala_id = (SELECT sala_id FROM rockola_peticiones WHERE id = %s)
                  AND LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) 
                  AND archivo_id IS NOT NULL AND archivo_id != ''
                ORDER BY creado_en DESC LIMIT 1
            """, (peticion_id, nombre)).fetchone()
            if not row_prev:
                row_prev = conn.execute("""
                    SELECT archivo_id FROM rockola_biblioteca 
                    WHERE sala_id = (SELECT sala_id FROM rockola_peticiones WHERE id = %s)
                      AND LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) 
                      AND archivo_id IS NOT NULL AND archivo_id != ''
                    ORDER BY creado_en DESC LIMIT 1
                """, (peticion_id, nombre)).fetchone()
            if row_prev and row_prev['archivo_id']:
                archivo_id = row_prev['archivo_id']

        row = conn.execute("SELECT * FROM rockola_peticiones WHERE id = %s", (peticion_id,)).fetchone()
        if not row:
            return jsonify(ok=False, error='Petición no encontrada'), 404

        conn.execute("""
            UPDATE rockola_peticiones
            SET estado = 'despachada',
                respuesta_nombre = %s,
                respuesta_origen = %s,
                respuesta_youtube_url = %s,
                respuesta_archivo_id = %s,
                despachado_en = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (nombre, origen, youtube_url, archivo_id, peticion_id))

        # Actualizar la entrada de rockola_compartidos para este token de modo que si recarga escuche la nueva
        conn.execute("""
            UPDATE rockola_compartidos
            SET nombre = %s,
                origen = %s,
                youtube_url = %s,
                archivo_id = %s
            WHERE token = %s
        """, (nombre, origen, youtube_url, archivo_id, row['token_origen']))
        conn.commit()

        return jsonify(ok=True, mensaje='Petición despachada exitosamente')
    finally:
        conn.close()


@bp.route('/api/peticiones/<int:peticion_id>/descartar', methods=['POST'])
def descartar_peticion_dj(peticion_id):
    """El DJ descarta una peticion."""
    conn = _connect()
    try:
        conn.execute("UPDATE rockola_peticiones SET estado = 'descartada' WHERE id = %s", (peticion_id,))
        conn.commit()
        return jsonify(ok=True)
    finally:
        conn.close()



@bp.route('/buscar-terceros')
def buscar_terceros_rockola():
    """Autocompletado de contactos desde la tabla terceros (nombre o telefono)."""
    q = (request.args.get('q') or '').strip()
    conn = _connect()
    try:
        if len(q) >= 2:
            q_digits = ''.join(c for c in q if c.isdigit())
            if q_digits:
                rows = conn.execute("""
                    SELECT id, nombre, telefono
                    FROM terceros
                    WHERE nombre ILIKE %s
                       OR REGEXP_REPLACE(COALESCE(telefono, ''), '[^0-9]', '', 'g') ILIKE %s
                    ORDER BY nombre
                    LIMIT 15
                """, ('%' + q + '%', '%' + q_digits + '%')).fetchall()
            else:
                rows = conn.execute("""
                    SELECT id, nombre, telefono
                    FROM terceros
                    WHERE nombre ILIKE %s
                    ORDER BY nombre
                    LIMIT 15
                """, ('%' + q + '%',)).fetchall()
        else:
            rows = conn.execute("""
                SELECT id, nombre, telefono
                FROM terceros
                WHERE nombre IS NOT NULL 
                  AND TRIM(nombre) != '' 
                  AND LOWER(TRIM(nombre)) NOT IN ('invitado', 'cliente', 'amigo')
                ORDER BY id DESC
                LIMIT 15
            """).fetchall()

        contactos = [{'id': r['id'], 'nombre': r['nombre'] or '', 'telefono': r['telefono'] or ''} for r in rows]
        return jsonify(ok=True, contactos=contactos)
    finally:
        conn.close()


# Mensajeria musical: compartir cancion al chat


_YT_ID_PATTERNS = (
    re.compile(r'[?&]v=([\w-]{6,})'),
    re.compile(r'youtu\.be/([\w-]{6,})'),
    re.compile(r'/embed/([\w-]{6,})'),
    re.compile(r'/shorts/([\w-]{6,})'),
    re.compile(r'/live/([\w-]{6,})'),
)


def _extraer_youtube_id(url):
    url = (url or '').strip()
    for rx in _YT_ID_PATTERNS:
        m = rx.search(url)
        if m:
            return m.group(1)
    return None


def _sala_personal_id(tercero_id):
    return 'u%d' % int(tercero_id)


def _payload_cancion_chat(origen, nombre, youtube_url=None, sala_origen=None, archivo_id=None):
    """Valida y construye (url_archivo, card_payload) para mensaje tipo cancion."""
    nombre = (nombre or '').strip() or 'Cancion'
    if origen == 'youtube':
        yt = (youtube_url or '').strip()
        if not yt or ('youtube.com' not in yt and 'youtu.be' not in yt):
            raise ValueError('youtube_url invalida')
        return '', {'origen': 'youtube', 'nombre': nombre, 'youtube_url': yt,
                    'youtube_id': _extraer_youtube_id(yt)}
    if origen == 'archivo':
        if not sala_origen or not archivo_id:
            raise ValueError('Faltan sala_origen/archivo_id')
        aid = (archivo_id or '').strip().replace('/', '').replace(chr(92), '')
        if not aid or aid != (archivo_id or '').strip():
            raise ValueError('archivo_id invalido')
        ruta = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp',
                            sala_origen, aid)
        if not os.path.isfile(ruta):
            raise ValueError('El archivo ya no esta en el servidor')
        return ('/rockola/%s/archivo/%s' % (sala_origen, aid),
                {'origen': 'archivo', 'nombre': nombre, 'sala_origen': sala_origen,
                 'archivo_id': aid})
    raise ValueError('origen debe ser youtube|archivo')


def _conv_por_token(conn, token):
    return conn.execute(
        'SELECT * FROM conversaciones WHERE token = %s AND activa = TRUE', (token,)).fetchone()


@bp.route('/chat/compartir', methods=['POST'])
def chat_compartir_cancion():
    data = request.get_json() or {}
    token = (data.get('token') or '').strip()
    sala_id = (data.get('sala_id') or '').strip()
    item_id = (data.get('item_id') or '').strip()
    if not token or not sala_id or not item_id:
        return jsonify(ok=False, error='Faltan token/sala_id/item_id'), 400
    if item_id.startswith('local-'):
        return jsonify(ok=False, error='Cancion local del reproductor: aun no se puede compartir'), 400
    conn = _connect()
    try:
        conv = _conv_por_token(conn, token)
        if not conv:
            return jsonify(ok=False, error='Conversacion no valida'), 404
        remitente = session.get('usuario_id')
        try:
            remitente = int(remitente) if remitente else None
        except (TypeError, ValueError):
            remitente = None
        if remitente == conv['creador_id']:
            destinatario = conv['invitado_id']
        elif remitente == conv['invitado_id']:
            destinatario = conv['creador_id']
        else:
            return jsonify(ok=False, error='No participas en esta conversacion'), 403
        item = conn.execute(
            'SELECT id, nombre, youtube_url FROM rockola_cola WHERE sala_id = %s AND id = %s',
            (sala_id, item_id)).fetchone()
        if not item:
            item = conn.execute(
                'SELECT archivo_id AS id, nombre, youtube_url FROM rockola_biblioteca '
                'WHERE sala_id = %s AND archivo_id = %s',
                (sala_id, item_id)).fetchone()
        if not item:
            return jsonify(ok=False, error='Cancion no encontrada en la sala'), 404
        yt = (item.get('youtube_url') or '').strip()
        try:
            if yt:
                url_archivo, payload = _payload_cancion_chat('youtube', item['nombre'], youtube_url=yt)
            else:
                url_archivo, payload = _payload_cancion_chat(
                    'archivo', item['nombre'], sala_origen=sala_id, archivo_id=item['id'])
        except ValueError as e:
            return jsonify(ok=False, error=str(e)), 400
        nuevo = conn.execute('''
            INSERT INTO mensajes (remitente_id, destinatario_id, mensaje, tipo, url_archivo,
                                  card_payload, conversacion_id, estado, fecha)
            VALUES (%s, %s, %s, 'cancion', %s, %s, %s, 'pendiente', CURRENT_TIMESTAMP)
            RETURNING id
        ''', (remitente, destinatario, payload['nombre'], url_archivo,
              json.dumps(payload), conv['id'])).fetchone()
        conn.commit()

        try:
            from .crm import _despachar_push_asincrono
            row_rem = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (remitente,)).fetchone()
            nom_rem = row_rem['nombre'] if row_rem and row_rem['nombre'] else 'Alguien'
            _despachar_push_asincrono(
                destinatario,
                f"🎵 {nom_rem} en TUC TUC",
                f"Te ha compartido: {payload['nombre']}",
                token=conv['token'],
                url=f"/chat2?open_token={conv['token']}"
            )
        except Exception:
            pass

        return jsonify(ok=True, id=nuevo['id'])
    finally:
        conn.close()


@bp.route('/chat/cancion/<int:msg_id>')
def chat_cancion(msg_id):
    conn = _connect()
    try:
        m = conn.execute(
            "SELECT id, mensaje, url_archivo, card_payload FROM mensajes WHERE id = %s AND tipo = 'cancion'",
            (msg_id,)).fetchone()
        if not m:
            return jsonify(ok=False, error='Cancion no encontrada'), 404
        cp = m.get('card_payload') or {}
        if isinstance(cp, str):
            try:
                cp = json.loads(cp)
            except Exception:
                cp = {}
        return jsonify(ok=True, cancion={
            'id': m['id'],
            'nombre': m.get('mensaje') or cp.get('nombre') or 'Cancion',
            'origen': cp.get('origen'),
            'url_archivo': m.get('url_archivo') or '',
            'youtube_url': cp.get('youtube_url') or '',
            'youtube_id': cp.get('youtube_id') or '',
            'sala_origen': cp.get('sala_origen') or '',
            'archivo_id': cp.get('archivo_id') or '',
        })
    finally:
        conn.close()


def _encolar_cancion_chat(conn, sala_id, tercero_id, cp):
    origen = (cp or {}).get('origen')
    nombre = (cp or {}).get('nombre') or 'Cancion'
    if origen == 'youtube':
        yt = ((cp or {}).get('youtube_url') or '').strip()
        if not yt:
            return None
        dup = conn.execute(
            'SELECT id FROM rockola_cola WHERE sala_id = %s AND reproducida = FALSE AND youtube_url = %s LIMIT 1',
            (sala_id, yt)).fetchone()
        if dup:
            return dup['id']
        item_id = 'yt-' + uuid.uuid4().hex[:12]
        _agregar_a_cola(conn, sala_id, item_id, nombre, tercero_id, youtube_url=yt)
        _recordar_cancion(conn, sala_id, item_id, nombre, tercero_id, 'youtube-link', youtube_url=yt)
        return item_id
    if origen == 'archivo':
        so, aid = ((cp or {}).get('sala_origen') or ''), ((cp or {}).get('archivo_id') or '')
        if not so or not aid or '/' in aid or chr(92) in aid:
            return None
        src = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp', so, aid)
        if not os.path.isfile(src):
            return None
        dup = conn.execute(
            'SELECT id FROM rockola_cola WHERE sala_id = %s AND reproducida = FALSE AND nombre = %s LIMIT 1',
            (sala_id, nombre)).fetchone()
        if dup:
            return dup['id']
        import shutil
        ext = os.path.splitext(aid)[1].lower()[:8]
        item_id = uuid.uuid4().hex + ext
        dest_dir = _upload_dir(sala_id)
        shutil.copyfile(src, os.path.join(dest_dir, item_id))
        _limpiar_archivos_antiguos(dest_dir)
        _agregar_a_cola(conn, sala_id, item_id, nombre, tercero_id)
        _recordar_cancion(conn, sala_id, item_id, nombre, tercero_id, 'archivo')
        return item_id
    return None

@bp.route('/chat/mi-rockola', methods=['POST'])
def chat_mi_rockola():
    data = request.get_json() or {}
    token = (data.get('token_conv') or '').strip()
    msg_id = data.get('msg_id')
    es_invitado = bool(data.get('es_invitado'))
    if not token:
        return jsonify(ok=False, error='Falta token_conv'), 400
    conn = _connect()
    try:
        conv = _conv_por_token(conn, token)
        if not conv:
            return jsonify(ok=False, error='Conversacion no valida'), 404
        viewer = session.get('usuario_id')
        try:
            viewer = int(viewer) if viewer else None
        except (TypeError, ValueError):
            viewer = None
        if viewer in (conv['creador_id'], conv['invitado_id']):
            tercero_id = viewer
        elif es_invitado:
            tercero_id = conv['invitado_id']
        else:
            tercero_id = conv['creador_id']
        sala_id = _sala_personal_id(tercero_id)
        _get_sala(conn, sala_id)
        encolado = None
        if msg_id:
            m = conn.execute(
                "SELECT card_payload FROM mensajes WHERE id = %s AND tipo = 'cancion'",
                (int(msg_id),)).fetchone()
            if m:
                cp = m.get('card_payload') or {}
                if isinstance(cp, str):
                    try:
                        cp = json.loads(cp)
                    except Exception:
                        cp = {}
                encolado = _encolar_cancion_chat(conn, sala_id, tercero_id, cp)
                conn.commit()
        return jsonify(ok=True, sala_id=sala_id, encolado=encolado,
                       reproductor_url='/rockola/%s/reproductor' % sala_id,
                       cliente_url='/rockola/%s/cliente' % sala_id)
    finally:
        conn.close()

@bp.route('/salas')
def salas():
    _limpiar_compartidos_antiguos()
    _limpiar_salas_temporales_antiguas()
    dispositivo_id = (request.args.get('device_id') or '').strip()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT sala_id, dispositivo_reproductor_id, dispositivo_reproductor_nombre, actualizado_en
            FROM rockola_salas
            ORDER BY actualizado_en DESC
            LIMIT 80
            """
        ).fetchall()
        lista = [_sala_para_dispositivo(_row_dict(row), dispositivo_id) for row in rows]
    finally:
        conn.close()
    return jsonify(ok=True, salas=lista)


@bp.route('/<sala_id>/info')
def sala_info(sala_id):
    dispositivo_id = (request.args.get('device_id') or '').strip()
    conn = _connect()
    try:
        sala = _get_sala(conn, sala_id)
    finally:
        conn.close()
    return jsonify(ok=True, sala=_sala_para_dispositivo(sala, dispositivo_id))


@bp.route('/<sala_id>/vincular-reproductor', methods=['POST'])
def vincular_reproductor(sala_id):
    data = request.get_json(silent=True) or {}
    dispositivo_id = (data.get('device_id') or '').strip()
    dispositivo_nombre = (data.get('device_name') or 'Este dispositivo').strip()[:80]
    tomar_control = bool(data.get('tomar_control'))
    if not dispositivo_id:
        return jsonify(ok=False, error='Falta dispositivo'), 400

    conn = _connect()
    try:
        with _lock:
            sala = _get_sala(conn, sala_id)
            owner_id = sala.get('dispositivo_reproductor_id') or ''
            if owner_id and owner_id != dispositivo_id and not tomar_control:
                return jsonify(
                    ok=False,
                    error='Sala asociada a otro reproductor',
                    sala=_sala_para_dispositivo(sala, dispositivo_id),
                ), 409

            conn.execute(
                """
                UPDATE rockola_salas
                SET dispositivo_reproductor_id = %s,
                    dispositivo_reproductor_nombre = %s,
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE sala_id = %s
                """,
                (dispositivo_id, dispositivo_nombre, sala_id),
            )
            conn.commit()
            sala = _get_sala(conn, sala_id)
    finally:
        conn.close()
    return jsonify(ok=True, sala=_sala_para_dispositivo(sala, dispositivo_id))


@bp.route('/<sala_id>/eliminar', methods=['POST'])
def eliminar_sala(sala_id):
    data = request.get_json(silent=True) or {}
    dispositivo_id = (data.get('device_id') or '').strip()
    confirmar = (data.get('confirmar') or '').strip().lower()
    if confirmar != sala_id.lower():
        return jsonify(ok=False, error='Confirmacion invalida'), 400

    conn = _connect()
    try:
        with _lock:
            sala = _get_sala(conn, sala_id)
            owner_id = sala.get('dispositivo_reproductor_id') or ''
            if owner_id and dispositivo_id and owner_id != dispositivo_id:
                return jsonify(ok=False, error='Esta sala pertenece a otro dispositivo'), 403
            conn.execute("DELETE FROM rockola_cola WHERE sala_id = %s", (sala_id,))
            conn.execute("DELETE FROM rockola_biblioteca WHERE sala_id = %s", (sala_id,))
            conn.execute("DELETE FROM rockola_salas WHERE sala_id = %s", (sala_id,))
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/cliente')
def cliente():
    return render_template('rockola_cliente.html', sala_id='default', modo='restaurante')


@bp.route('/reproductor')
def reproductor():
    resp = make_response(render_template('rockola_reproductor.html', sala_id='default', admin_key=''))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@bp.route('/<sala_id>/cliente')
def cliente_sala(sala_id):
    return render_template('rockola_cliente.html', sala_id=sala_id, modo='restaurante')


@bp.route('/<sala_id>/reproductor')
@bp.route('/reproductor/<sala_id>')
def reproductor_sala(sala_id):
    conn = _connect()
    try:
        sala = _get_sala(conn, sala_id)
    finally:
        conn.close()
    resp = make_response(render_template('rockola_reproductor.html', sala_id=sala_id, admin_key=sala.get('admin_key', '')))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@bp.route('/<sala_id>/control')
def control_sala(sala_id):
    key = (request.args.get('key') or '').strip()
    conn = _connect()
    try:
        sala = _get_sala(conn, sala_id)
    finally:
        conn.close()
    admin_key = sala.get('admin_key', '') if key and key == sala.get('admin_key') else ''
    return render_template('rockola_control.html', sala_id=sala_id, admin_key=admin_key)


@bp.route('/sync/<sala_id>')
def sync(sala_id):
    return render_template('rockola_sync.html', sala_id=sala_id)


@bp.route('/<sala_id>/subir', methods=['POST'])
def subir(sala_id):
    tercero_id = session.get('usuario_id')
    owner_nombre = session.get('nombre', 'Anónimo')
    lista_envio_id = (request.form.get('lista_id') or '').strip() or None
    lista_envio_nombre = (request.form.get('lista_nombre') or '').strip() or None
    lista_envio_posicion_raw = (request.form.get('lista_posicion') or '').strip()
    try:
        lista_envio_posicion = int(lista_envio_posicion_raw) if lista_envio_posicion_raw != '' else None
    except ValueError:
        lista_envio_posicion = None
    lista_envio = None
    if lista_envio_id and lista_envio_nombre:
        lista_envio = {
            'id': lista_envio_id[:120],
            'nombre': lista_envio_nombre[:180],
            'posicion': lista_envio_posicion,
        }
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
                _agregar_a_cola(conn, sala_id, nombre_id, file.filename, tercero_id, lista_envio)
                _recordar_cancion(conn, sala_id, nombre_id, file.filename, tercero_id, 'archivo')
                agregadas.append({'id': nombre_id, 'nombre': file.filename, 'owner': owner_nombre, 'tercero_id': tercero_id})
            _limpiar_archivos_antiguos(upload_dir)
            conn.commit()
    finally:
        conn.close()

    return jsonify(ok=True, agregadas=agregadas)


COBALT_APIS = [
    api.strip()
    for api in os.environ.get(
        'COBALT_API_URLS',
        'https://api.cobalt.liubquanti.click/,https://melon.clxxped.lol/,https://api-cobalt.eversiege.network/,https://cobalt.alpha.wolfy.love/,https://api.qwkuns.me/,https://subito-c.meowing.de/,https://grapefruit.clxxped.lol/'
    ).split(',')
    if api.strip()
]
COBALT_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def _cobalt_headers():
    headers = dict(COBALT_HEADERS)
    token = os.environ.get('COBALT_API_KEY') or os.environ.get('COBALT_JWT')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def _descargar_youtube_con_cobalt(url, tmp_path):
    import json as _json
    import urllib.error
    import urllib.request

    payload = _json.dumps({
        'url': url,
        'downloadMode': 'audio',
        'audioFormat': 'mp3',
    }).encode()
    errores = []
    for api_url in COBALT_APIS:
        try:
            req = urllib.request.Request(
                api_url,
                data=payload,
                headers=_cobalt_headers(),
                method='POST',
            )
            try:
                with urllib.request.urlopen(req, timeout=6) as response:
                    cobalt = _json.loads(response.read())
            except urllib.error.HTTPError as error:
                body = error.read().decode('utf-8', errors='ignore')[:300]
                errores.append(f'{api_url}: HTTP {error.code}: {body}')
                continue
        except Exception as error:
            errores.append(f'{api_url}: {error}')
            continue

        status = cobalt.get('status')
        if status == 'error':
            msg = cobalt.get('error', {}).get('code', 'error desconocido')
            errores.append(f'{api_url}: {msg}')
            continue
        if status not in ('stream', 'tunnel', 'redirect'):
            errores.append(f'{api_url}: estado inesperado {status}')
            continue

        download_url = cobalt.get('url') or cobalt.get('audio')
        if not download_url:
            errores.append(f'{api_url}: sin URL de descarga')
            continue

        title = cobalt.get('filename', 'audio').rsplit('.', 1)[0]
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
            errores.append(f'{api_url}: error descargando audio: {error}')
            continue

        return {'path': tmp_path, 'nombre': title + '.mp3'}, None

    return None, ' | '.join(errores) or 'Cobalt no respondio'


def _descargar_youtube_con_ytdlp(url, upload_dir, nombre_id):
    try:
        import yt_dlp
    except Exception as e:
        return None, f'yt-dlp no esta disponible: {e}'

    outtmpl = os.path.join(upload_dir, nombre_id + '.%(ext)s')
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    cookie_path = os.environ.get('YOUTUBE_COOKIES_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cookies.txt')
    if os.path.exists(cookie_path):
        opts['cookiefile'] = cookie_path
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
    except Exception as error:
        return None, f'yt-dlp: {error}'

    if not path or not os.path.exists(path):
        return None, 'yt-dlp no genero archivo de audio'

    title = info.get('title') or 'audio'
    ext = os.path.splitext(path)[1] or '.webm'
    return {'path': path, 'nombre': title + ext}, None


def _descargar_youtube_con_pytubefix(url, upload_dir, nombre_id):
    try:
        from pytubefix import YouTube
    except Exception:
        return None, 'pytubefix no esta instalado'

    errores = []
    # MWEB evade la proteccion SABR PoToken de YouTube en IPs de centros de datos
    for client_name in ['MWEB', 'WEB']:
        try:
            yt = YouTube(url, client=client_name)
            audio = yt.streams.get_audio_only()
            if not audio:
                errores.append(f"{client_name}: sin audio")
                continue
            ext = '.m4a' if 'mp4' in (audio.mime_type or '') else '.webm'
            filename = nombre_id + ext
            out_path = audio.download(output_path=upload_dir, filename=filename)
            title = yt.title or 'audio'
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                return {'path': out_path, 'nombre': title + ext}, None
            else:
                errores.append(f"{client_name}: archivo vacio o no existe")
        except Exception as e:
            errores.append(f"{client_name}: {e}")
            continue

    return None, f'pytubefix: {" | ".join(errores)}'


@bp.route('/<sala_id>/youtube', methods=['POST'])
def youtube(sala_id):
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or '').strip()
    tercero_id = session.get('usuario_id')
    owner_nombre = session.get('nombre', 'Anónimo')

    if not url or ('youtube.com' not in url and 'youtu.be' not in url):
        return jsonify(ok=False, error='URL de YouTube invalida'), 400

    modo = (data.get('modo') or 'final').strip().lower()
    nombre_display = _titulo_youtube(url)
    item_id = 'yt-' + uuid.uuid4().hex[:12]
    conn = _connect()
    try:
        with _lock:
            _agregar_a_cola(conn, sala_id, item_id, nombre_display, tercero_id, youtube_url=url, modo=modo)
            _recordar_cancion(conn, sala_id, item_id, nombre_display, tercero_id, 'youtube-link', youtube_url=url)
            conn.commit()
    finally:
        conn.close()

    return jsonify(ok=True, agregadas=[{
        'id': item_id,
        'nombre': nombre_display,
        'owner': owner_nombre,
        'tercero_id': tercero_id,
        'youtube_url': url,
        'origen': 'youtube-link',
    }])


def _titulo_youtube(url):
    import urllib.parse
    import urllib.request
    import json as _json
    try:
        oembed = 'https://www.youtube.com/oembed?url=' + urllib.parse.quote(url, safe='') + '&format=json'
        req = urllib.request.Request(oembed, headers={'User-Agent': COBALT_HEADERS['User-Agent']})
        with urllib.request.urlopen(req, timeout=8) as response:
            return _json.loads(response.read()).get('title') or 'Video de YouTube'
    except Exception:
        return 'Video de YouTube'


@bp.route('/<sala_id>/resolver', methods=['POST'])
def resolver(sala_id):
    data = request.get_json(silent=True) or {}
    item_id = (data.get('id') or '').strip()
    target_url = (data.get('url') or '').strip()
    if not item_id or '/' in item_id or '\\' in item_id:
        return jsonify(ok=False, error='Id invalido'), 400
    upload_dir = _upload_dir(sala_id)
    for candidato in (item_id, item_id + '.mp3', item_id + '.m4a', item_id + '.webm'):
        if os.path.isfile(os.path.join(upload_dir, candidato)):
            return jsonify(ok=True, url=f'/rockola/{sala_id}/archivo/{candidato}', cache=True)
    conn = _connect()
    try:
        item = _get_item_cola(conn, sala_id, item_id)
        if not item:
            row = conn.execute(
                """
                SELECT archivo_id AS id, nombre, youtube_url
                FROM rockola_biblioteca
                WHERE sala_id = %s AND archivo_id = %s
                """,
                (sala_id, item_id),
            ).fetchone()
            if row:
                item = _row_dict(row)
    finally:
        conn.close()

    if not target_url and item:
        target_url = (item.get('youtube_url') or '').strip()

    if not target_url:
        return jsonify(ok=False, error='Sin audio disponible para este item'), 404

    destino = os.path.join(upload_dir, item_id + '.mp3')
    try:
        # 1. Intentar primero con pytubefix MWEB (probado que evade el SABR PoToken de YouTube en servidores AWS)
        descarga, error_pytube = _descargar_youtube_con_pytubefix(target_url, upload_dir, item_id)
        
        # 2. Si falla pytubefix, intentar con yt-dlp
        error_ytdlp = None
        if not descarga:
            descarga, error_ytdlp = _descargar_youtube_con_ytdlp(target_url, upload_dir, item_id)

        # 3. Fallback adicional con cobalt
        if not descarga:
            descarga, error_cobalt = _descargar_youtube_con_cobalt(target_url, destino)
            if not descarga:
                err_final = 'YouTube bloqueó la descarga automatizada en la IP del servidor en la nube (Sign in to confirm you are not a bot). La canción sonará normalmente en vivo cuando llegue su turno en la cola.'
                return jsonify(ok=False, error=err_final), 200
        _limpiar_archivos_antiguos(upload_dir)
    except Exception as error:
        return jsonify(ok=False, error=f'No se pudo resolver el audio: {error}'), 502
    return jsonify(ok=True, url=f'/rockola/{sala_id}/archivo/{os.path.basename(descarga["path"])}')


@bp.route('/<sala_id>/local', methods=['POST'])
def agregar_local(sala_id):
    data = request.get_json(silent=True) or {}
    local_id = (data.get('local_id') or '').strip()
    nombre = (data.get('nombre') or 'Cancion local').strip()
    modo = (data.get('modo') or 'final').strip().lower()
    owner_nombre = data.get('owner') or 'Anónimo'
    device_id = (data.get('device_id') or '').strip()
    tercero_id = None
    if not local_id.startswith('local-'):
        return jsonify(ok=False, error='Cancion local invalida'), 400

    conn = _connect()
    try:
        with _lock:
            _agregar_a_cola(conn, sala_id, local_id, nombre, tercero_id, modo=modo)
            _recordar_cancion(conn, sala_id, local_id, nombre, tercero_id, 'local')
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True, agregadas=[{'id': local_id, 'nombre': nombre, 'owner': owner_nombre, 'tercero_id': tercero_id}])


@bp.route('/catalogo/local', methods=['POST'])
def sincronizar_catalogo_local():
    data = request.get_json(silent=True) or {}
    dispositivo = data.get('dispositivo') or {}
    dispositivo_id = (dispositivo.get('id') or '').strip()
    if not dispositivo_id:
        return jsonify(ok=False, error='dispositivo requerido'), 400

    nombre_dispositivo = (dispositivo.get('nombre') or 'Dispositivo').strip()[:120]
    user_agent = (dispositivo.get('user_agent') or request.headers.get('User-Agent') or '')[:300]
    canciones = data.get('canciones') or []
    listas = data.get('listas') or []

    conn = _connect()
    try:
        with _lock:
            conn.execute(
                """
                INSERT INTO rockola_dispositivos (dispositivo_id, nombre, user_agent, actualizado_en)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (dispositivo_id) DO UPDATE
                SET nombre = EXCLUDED.nombre,
                    user_agent = EXCLUDED.user_agent,
                    actualizado_en = CURRENT_TIMESTAMP
                """,
                (dispositivo_id, nombre_dispositivo, user_agent),
            )

            canciones_validas = {}
            for cancion in canciones[:1000]:
                cancion_id = (cancion.get('cancion_id') or '').strip()
                local_id = (cancion.get('local_id') or '').strip()
                titulo = (cancion.get('titulo') or cancion.get('nombre') or 'Cancion').strip()[:240]
                if not cancion_id or not local_id:
                    continue
                canciones_validas[local_id] = cancion_id
                conn.execute(
                    """
                    INSERT INTO rockola_canciones (cancion_id, titulo, archivo_nombre, tamano_bytes, mime, actualizado_en)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (cancion_id) DO UPDATE
                    SET titulo = EXCLUDED.titulo,
                        archivo_nombre = EXCLUDED.archivo_nombre,
                        tamano_bytes = EXCLUDED.tamano_bytes,
                        mime = EXCLUDED.mime,
                        actualizado_en = CURRENT_TIMESTAMP
                    """,
                    (
                        cancion_id,
                        titulo,
                        (cancion.get('archivo_nombre') or titulo)[:260],
                        int(cancion.get('tamano_bytes') or 0),
                        (cancion.get('mime') or '')[:120],
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO rockola_dispositivo_canciones
                        (dispositivo_id, cancion_id, local_id, disponible, actualizado_en)
                    VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (dispositivo_id, cancion_id) DO UPDATE
                    SET local_id = EXCLUDED.local_id,
                        disponible = TRUE,
                        actualizado_en = CURRENT_TIMESTAMP
                    """,
                    (dispositivo_id, cancion_id, local_id),
                )

            for lista in listas[:200]:
                lista_id = (lista.get('lista_id') or '').strip()
                nombre = (lista.get('nombre') or 'Lista').strip()[:180]
                if not lista_id:
                    continue
                conn.execute(
                    """
                    INSERT INTO rockola_listas (lista_id, dispositivo_id, nombre, actualizado_en)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (lista_id) DO UPDATE
                    SET nombre = EXCLUDED.nombre,
                        actualizado_en = CURRENT_TIMESTAMP
                    """,
                    (lista_id, dispositivo_id, nombre),
                )
                conn.execute("DELETE FROM rockola_lista_canciones WHERE lista_id = %s", (lista_id,))
                for posicion, local_id in enumerate(lista.get('canciones') or []):
                    cancion_id = canciones_validas.get(local_id)
                    if not cancion_id:
                        continue
                    conn.execute(
                        """
                        INSERT INTO rockola_lista_canciones (lista_id, cancion_id, posicion)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (lista_id, cancion_id) DO UPDATE
                        SET posicion = EXCLUDED.posicion
                        """,
                        (lista_id, cancion_id, posicion),
                    )

            conn.commit()
    finally:
        conn.close()

    return jsonify(ok=True, canciones=len(canciones), listas=len(listas))


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
        volumen=_normalizar_volumen(sala.get('volumen')),
        fundido_cruzado=bool(sala.get('fundido_cruzado') if sala.get('fundido_cruzado') is not None else True),
        fundido_segundos=int(sala.get('fundido_segundos') if sala.get('fundido_segundos') is not None else 12),
        fundido_duracion=int(sala.get('fundido_duracion') if sala.get('fundido_duracion') is not None else 5),
        modo_shuffle=bool(sala.get('modo_shuffle') or False),
        modo_repetir_cancion=bool(sala.get('modo_repetir_cancion') or False),
        modo_repetir_lista=bool(sala.get('modo_repetir_lista') or False),
        modo_autoplay=bool(sala.get('modo_autoplay') or False),
    )


@bp.route('/<sala_id>/admin-info')
def admin_info(sala_id):
    key = (request.args.get('key') or '').strip()
    conn = _connect()
    try:
        sala = _get_sala(conn, sala_id)
        autorizado = bool(key and key == (sala.get('admin_key') or ''))
    finally:
        conn.close()
    return jsonify(
        ok=True,
        autorizado=autorizado,
        cliente_url=f'https://rockola.tuc-tuc.co/rockola/{sala_id}',
        control_url=f'https://rockola.tuc-tuc.co/control/{sala_id}?key={key}' if key else '',
        reproductor_url=f'https://rockola.tuc-tuc.co/reproductor/{sala_id}',
    )


@bp.route('/<sala_id>/volumen', methods=['POST'])
def volumen(sala_id):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        with _lock:
            if not _es_admin_sala(conn, sala_id, data):
                return jsonify(ok=False, error='No autorizado'), 403
            volumen_nuevo = _normalizar_volumen(data.get('volumen'))
            conn.execute(
                """
                UPDATE rockola_salas
                SET volumen = %s
                WHERE sala_id = %s
                """,
                (volumen_nuevo, sala_id),
            )
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True, volumen=volumen_nuevo)


@bp.route('/<sala_id>/fundido', methods=['POST'])
def fundido(sala_id):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        with _lock:
            if not _es_admin_sala(conn, sala_id, data):
                return jsonify(ok=False, error='No autorizado'), 403
            
            cruzado = data.get('fundido_cruzado')
            segundos = data.get('fundido_segundos')
            duracion = data.get('fundido_duracion')
            
            if cruzado is not None:
                conn.execute(
                    "UPDATE rockola_salas SET fundido_cruzado = %s WHERE sala_id = %s",
                    (bool(cruzado), sala_id)
                )
            if segundos is not None:
                segundos = max(2, min(60, int(segundos)))
                conn.execute(
                    "UPDATE rockola_salas SET fundido_segundos = %s WHERE sala_id = %s",
                    (segundos, sala_id)
                )
            if duracion is not None:
                duracion = max(1, min(20, int(duracion)))
                conn.execute(
                    "UPDATE rockola_salas SET fundido_duracion = %s WHERE sala_id = %s",
                    (duracion, sala_id)
                )
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/modos', methods=['POST'])
def modos(sala_id):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        with _lock:
            if not _es_admin_sala(conn, sala_id, data):
                return jsonify(ok=False, error='No autorizado'), 403

            for campo in ('modo_shuffle', 'modo_repetir_cancion', 'modo_repetir_lista', 'modo_autoplay'):
                if data.get(campo) is not None:
                    conn.execute(
                        "UPDATE rockola_salas SET {} = %s WHERE sala_id = %s".format(campo),
                        (bool(data.get(campo)), sala_id)
                    )
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/biblioteca')
def biblioteca(sala_id):
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT b.archivo_id AS id, b.nombre, COALESCE(t.nombre, 'Anónimo') AS owner, b.origen, b.youtube_url, b.creado_en
            FROM rockola_biblioteca b
            LEFT JOIN terceros t ON b.tercero_id = t.id
            WHERE b.sala_id = %s
            ORDER BY b.creado_en DESC
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
    modo = (data.get('modo') or 'final').strip().lower()
    tercero_id = session.get('usuario_id')
    owner_nombre = session.get('nombre', 'Anónimo')

    conn = _connect()
    try:
        with _lock:
            row = conn.execute(
                """
                SELECT archivo_id, nombre, youtube_url, origen
                FROM rockola_biblioteca
                WHERE sala_id = %s AND archivo_id = %s
                """,
                (sala_id, archivo_id),
            ).fetchone()
            if not row:
                return jsonify(ok=False, error='Cancion no encontrada'), 404

            nombre = row['nombre']
            yt_url = row.get('youtube_url')
            upload = _upload_dir(sala_id)
            candidatos = [archivo_id, archivo_id + '.mp3', archivo_id + '.m4a']
            origen = None
            for cand in candidatos:
                p = os.path.join(upload, cand)
                if os.path.isfile(p):
                    origen = p
                    break
            if origen:
                nuevo_id = str(uuid.uuid4()) + os.path.splitext(origen)[1]
                destino = os.path.join(upload, nuevo_id)
                with open(origen, 'rb') as src, open(destino, 'wb') as dst:
                    while True:
                        chunk = src.read(65536)
                        if not chunk:
                            break
                        dst.write(chunk)
                _agregar_a_cola(conn, sala_id, nuevo_id, nombre, tercero_id, modo=modo)
            elif yt_url:
                nuevo_id = 'yt-' + uuid.uuid4().hex[:12]
                _agregar_a_cola(conn, sala_id, nuevo_id, nombre, tercero_id, youtube_url=yt_url, modo=modo)
            else:
                return jsonify(ok=False, error='Archivo no disponible en el servidor'), 404
            conn.commit()
    finally:
        conn.close()

    return jsonify(ok=True, agregadas=[{'id': nuevo_id, 'nombre': nombre, 'owner': owner_nombre, 'tercero_id': tercero_id}])


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
                    "UPDATE rockola_cola SET reproducida = TRUE, reproducida_en = NOW() WHERE id = %s AND sala_id = %s",
                    (items[0]['id'], sala_id),
                )
                _reset_sync(conn, sala_id)
                conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/saltar', methods=['POST'])
def saltar(sala_id):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        with _lock:
            if not _es_admin_sala(conn, sala_id, data):
                return jsonify(ok=False, error='No autorizado'), 403
            items = _get_cola(conn, sala_id)
            if items:
                conn.execute(
                    "UPDATE rockola_cola SET reproducida = TRUE, reproducida_en = NOW() WHERE id = %s AND sala_id = %s",
                    (items[0]['id'], sala_id),
                )
                _reset_sync(conn, sala_id)
                conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/validar', methods=['POST'])
def validar_seleccion(sala_id):
    """Beacon fire-and-forget: el reproductor reporta cuánto sonó lo elegido del buscador."""
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        with _lock:
            if not _es_admin_sala(conn, sala_id, data):
                return jsonify(ok=False, error='No autorizado'), 403
            evento = (data.get('evento') or 'fin')[:20]
            ratio, validado = _evaluar_validacion(
                data.get('sonados_seg'), data.get('duracion_seg'), evento)
            conn.execute(
                """
                INSERT INTO rockola_validaciones
                    (sala_id, query, cancion_id, sonando_id, nombre, youtube_url,
                     evento, duracion_seg, sonados_seg, ratio, validado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (sala_id,
                 (data.get('query') or '')[:240],
                 (data.get('cancion_id') or '')[:260],
                 (data.get('sonando_id') or '')[:260],
                 (data.get('nombre') or '')[:240],
                 (data.get('youtube_url') or '')[:500],
                 evento,
                 float(data.get('duracion_seg') or 0),
                 float(data.get('sonados_seg') or 0),
                 ratio,
                 validado),
            )
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True, validado=validado, ratio=ratio)


@bp.route('/<sala_id>/anterior', methods=['POST'])
def anterior(sala_id):
    data = request.get_json(silent=True) or {}
    conn = _connect()
    try:
        with _lock:
            if not _es_admin_sala(conn, sala_id, data):
                return jsonify(ok=False, error='No autorizado'), 403
            
            # Obtener el último tema reproducido para esta sala
            row = conn.execute(
                """
                SELECT id, posicion FROM rockola_cola
                WHERE sala_id = %s AND reproducida = TRUE
                ORDER BY reproducida_en DESC
                LIMIT 1
                """,
                (sala_id,)
            ).fetchone()
            
            if row:
                # Encontrar la menor posición de los pendientes para colocar este antes
                min_pos_row = conn.execute(
                    "SELECT MIN(posicion) FROM rockola_cola WHERE sala_id = %s AND reproducida = FALSE",
                    (sala_id,)
                ).fetchone()
                
                new_pos = 0
                if min_pos_row and min_pos_row[0] is not None:
                    new_pos = min_pos_row[0] - 1
                else:
                    new_pos = row['posicion']

                # Desmarcar el tema como reproducido y reubicado
                conn.execute(
                    """
                    UPDATE rockola_cola 
                    SET reproducida = FALSE, reproducida_en = NULL, posicion = %s
                    WHERE id = %s AND sala_id = %s
                    """,
                    (new_pos, row['id'], sala_id),
                )
                _reset_sync(conn, sala_id)
                conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/quitar', methods=['POST'])
def quitar(sala_id):
    data = request.get_json(silent=True) or {}
    archivo_id = data.get('id')
    modo = data.get('modo', 'cliente')
    if not archivo_id:
        return jsonify(ok=False, error='Falta cancion'), 400

    session_tercero_id = session.get('usuario_id')

    conn = _connect()
    try:
        with _lock:
            items = _get_cola(conn, sala_id)
            if not items:
                return jsonify(ok=True)
            item = _get_item_cola(conn, sala_id, archivo_id)
            if not item:
                return jsonify(ok=True)

            es_actual = items[0]['id'] == archivo_id
            es_admin = _es_admin_sala(conn, sala_id, data)
            autorizado = es_admin or modo == 'sync' or (
                session_tercero_id is not None and item.get('tercero_id') == session_tercero_id and not es_actual
            )
            if not autorizado:
                return jsonify(ok=False, error='No autorizado'), 403

            conn.execute(
                "DELETE FROM rockola_cola WHERE id = %s AND sala_id = %s",
                (archivo_id, sala_id),
            )
            if es_actual:
                _reset_sync(conn, sala_id)
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/vaciar', methods=['POST'])
def vaciar_cola(sala_id):
    conn = _connect()
    try:
        with _lock:
            conn.execute("DELETE FROM rockola_cola WHERE sala_id = %s", (sala_id,))
            _reset_sync(conn, sala_id)
            conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/<sala_id>/reordenar', methods=['POST'])
def reordenar(sala_id):
    data = request.get_json(silent=True) or {}
    nuevo_orden = data.get('orden', [])
    modo = data.get('modo', 'restaurante')
    session_tercero_id = session.get('usuario_id')

    conn = _connect()
    try:
        with _lock:
            items = _get_cola(conn, sala_id)
            es_admin = _es_admin_sala(conn, sala_id, data)
            por_id = {item['id']: item for item in items}
            nueva_cola = []
            for id_ in nuevo_orden:
                if id_ in por_id:
                    item = por_id[id_]
                    if es_admin or modo in ('sync', 'reproductor') or (
                        session_tercero_id is not None and item.get('tercero_id') == session_tercero_id
                    ):
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


@bp.route('/admin/blanquear-pin', methods=['POST'])
def blanquear_pin():
    if not (session.get('rol') in ('Administrador', 'ClienteVFP', 'Tienda', 'Restaurante') and session.get('usuario_id')):
        return jsonify(ok=False, error='No autorizado'), 403

    data = request.get_json() or {}
    tercero_id = data.get('tercero_id')
    if not tercero_id:
        return jsonify(ok=False, error='Falta tercero_id'), 400

    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE terceros SET pin_seguridad = NULL WHERE id = %s",
            (tercero_id,)
        )
        conn.commit()
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
    finally:
        conn.close()

    return jsonify(ok=True)


def register_events(socketio):
    return None
