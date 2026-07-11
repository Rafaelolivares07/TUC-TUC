"""
Rockola Tuc Tuc: salas con cola persistente en PostgreSQL.

La UI usa polling HTTP, subida de archivos locales y descarga de audio desde
YouTube mediante cobalt.tools. El modulo no toca la BD al importarse para que
un fallo de Rockola no tumbe el arranque general de Tuc Tuc.
"""

import json
import os
import threading
import uuid

from flask import Blueprint, Response, jsonify, render_template, request, send_from_directory, session
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
    lista_envio_posicion INTEGER
);
CREATE INDEX IF NOT EXISTS idx_cola_sala ON rockola_cola(sala_id, posicion);
CREATE TABLE IF NOT EXISTS rockola_biblioteca (
    archivo_id TEXT PRIMARY KEY,
    sala_id    TEXT NOT NULL,
    nombre     TEXT NOT NULL,
    tercero_id INTEGER REFERENCES terceros(id) ON DELETE SET NULL,
    origen     TEXT NOT NULL DEFAULT 'archivo',
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
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS admin_key TEXT;
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS volumen INTEGER NOT NULL DEFAULT 80;
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS dispositivo_reproductor_id TEXT;
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS dispositivo_reproductor_nombre TEXT;
ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS lista_envio_id TEXT;
ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS lista_envio_nombre TEXT;
ALTER TABLE rockola_cola ADD COLUMN IF NOT EXISTS lista_envio_posicion INTEGER;
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
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS fundido_cruzado BOOLEAN DEFAULT TRUE;")
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS fundido_segundos INTEGER DEFAULT 12;")
            conn.execute("ALTER TABLE rockola_salas ADD COLUMN IF NOT EXISTS fundido_duracion INTEGER DEFAULT 5;")
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
        SELECT c.id, c.nombre, c.tercero_id, t.nombre AS owner, c.lista_envio_id, c.lista_envio_nombre, c.lista_envio_posicion
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
        SELECT c.id, c.nombre, c.tercero_id, t.nombre AS owner
        FROM rockola_cola c
        LEFT JOIN terceros t ON c.tercero_id = t.id
        WHERE c.sala_id = %s AND c.id = %s
        """,
        (sala_id, archivo_id),
    ).fetchone()
    return _row_dict(row) if row else None


def _max_pos(conn, sala_id):
    row = conn.execute(
        "SELECT COALESCE(MAX(posicion), -1) AS m FROM rockola_cola WHERE sala_id = %s",
        (sala_id,),
    ).fetchone()
    return row['m'] if row else -1


def _recordar_cancion(conn, sala_id, archivo_id, nombre, tercero_id, origen):
    tid = int(tercero_id) if tercero_id else None
    conn.execute(
        """
        INSERT INTO rockola_biblioteca (archivo_id, sala_id, nombre, tercero_id, origen)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (archivo_id) DO UPDATE
        SET nombre = EXCLUDED.nombre,
            tercero_id = EXCLUDED.tercero_id,
            origen = EXCLUDED.origen
        """,
        (archivo_id, sala_id, nombre, tid, origen),
    )


def _agregar_a_cola(conn, sala_id, archivo_id, nombre, tercero_id, lista_envio=None):
    pos_actual = _max_pos(conn, sala_id) + 1
    lista_envio = lista_envio or {}
    tid = int(tercero_id) if tercero_id else None
    conn.execute(
        """
        INSERT INTO rockola_cola
            (id, sala_id, nombre, tercero_id, posicion, lista_envio_id, lista_envio_nombre, lista_envio_posicion)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
    manifest = {
        "name": "Tu Rockola",
        "short_name": "Rockola",
        "description": "Rockola Tuc Tuc con biblioteca local y modo offline",
        "start_url": "/rockola/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#060c18",
        "theme_color": "#00d4ff",
        "icons": [
            {"src": "/static/TUCTUC%20192X192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/TUCTUC%20512X512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    return Response(json.dumps(manifest), mimetype='application/manifest+json')


@bp.route('/pwa/sw.js')
def pwa_sw():
    js = """
const CACHE = 'rockola-pwa-v1';
const CORE = [
  '/rockola/',
  '/rockola/pwa/offline',
  '/rockola/pwa/manifest.json',
  '/static/TUCTUC%20192X192.png',
  '/static/TUCTUC%20512X512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)).then(() => self.skipWaiting()));
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
  if (url.origin !== self.location.origin) return;

  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(cache => cache.put(req, copy));
        return res;
      }).catch(() => caches.match(req).then(hit => hit || caches.match('/rockola/pwa/offline')))
    );
    return;
  }

  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/rockola/pwa/')) {
    event.respondWith(
      caches.match(req).then(hit => hit || fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(cache => cache.put(req, copy));
        return res;
      }))
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
    return render_template('rockola_offline.html')


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
    return render_template('rockola_reproductor.html', sala_id='default')


@bp.route('/<sala_id>/cliente')
def cliente_sala(sala_id):
    return render_template('rockola_cliente.html', sala_id=sala_id, modo='restaurante')


@bp.route('/<sala_id>/reproductor')
def reproductor_sala(sala_id):
    conn = _connect()
    try:
        sala = _get_sala(conn, sala_id)
    finally:
        conn.close()
    return render_template('rockola_reproductor.html', sala_id=sala_id, admin_key=sala.get('admin_key', ''))


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
        'https://api.cobalt.tools/,https://api.cobalt.liubquanti.click/'
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
                with urllib.request.urlopen(req, timeout=25) as response:
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
    except Exception:
        return None, 'yt-dlp no esta disponible en el servidor'

    outtmpl = os.path.join(upload_dir, nombre_id + '.%(ext)s')
    opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': outtmpl,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
    except Exception as error:
        return None, f'yt-dlp no pudo descargar el audio: {error}'

    if not os.path.exists(path):
        return None, 'yt-dlp no genero archivo de audio'

    title = info.get('title') or 'audio'
    ext = os.path.splitext(path)[1] or '.m4a'
    return {'path': path, 'nombre': title + ext}, None


@bp.route('/<sala_id>/youtube', methods=['POST'])
def youtube(sala_id):
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    tercero_id = session.get('usuario_id')
    owner_nombre = session.get('nombre', 'Anónimo')

    if not url or ('youtube.com' not in url and 'youtu.be' not in url):
        return jsonify(ok=False, error='URL de YouTube invalida'), 400

    upload_dir = _upload_dir(sala_id)
    nombre_id = str(uuid.uuid4())
    tmp_path = os.path.join(upload_dir, nombre_id + '.mp3')

    descarga, error_cobalt = _descargar_youtube_con_cobalt(url, tmp_path)
    if not descarga:
        descarga, error_ytdlp = _descargar_youtube_con_ytdlp(url, upload_dir, nombre_id)
        if not descarga:
            if 'api.auth.jwt.missing' in (error_cobalt or ''):
                return jsonify(ok=False, error='YouTube no esta disponible: Cobalt ahora exige token y yt-dlp no pudo resolver la descarga.'), 502
            return jsonify(ok=False, error=error_ytdlp or error_cobalt or 'No se pudo descargar el audio'), 502

    archivo_final = os.path.basename(descarga['path'])
    nombre_display = descarga['nombre']

    conn = _connect()
    try:
        with _lock:
            _agregar_a_cola(conn, sala_id, archivo_final, nombre_display, tercero_id)
            _recordar_cancion(conn, sala_id, archivo_final, nombre_display, tercero_id, 'youtube')
            _limpiar_archivos_antiguos(upload_dir)
            conn.commit()
    finally:
        conn.close()

    return jsonify(ok=True, agregadas=[{
        'id': archivo_final,
        'nombre': nombre_display,
        'owner': owner_nombre,
        'tercero_id': tercero_id,
    }])


@bp.route('/<sala_id>/local', methods=['POST'])
def agregar_local(sala_id):
    data = request.get_json(silent=True) or {}
    local_id = (data.get('local_id') or '').strip()
    nombre = (data.get('nombre') or 'Cancion local').strip()
    tercero_id = session.get('usuario_id')
    owner_nombre = session.get('nombre', 'Anónimo')
    if not local_id.startswith('local-'):
        return jsonify(ok=False, error='Cancion local invalida'), 400

    conn = _connect()
    try:
        with _lock:
            _agregar_a_cola(conn, sala_id, local_id, nombre, tercero_id)
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
    tercero_id = session.get('usuario_id')
    owner_nombre = session.get('nombre', 'Anónimo')

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

            _agregar_a_cola(conn, sala_id, nuevo_id, nombre, tercero_id)
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
                    if es_admin or modo == 'sync' or (
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


@bp.route('/debug/git-shallow')
def git_shallow():
    import os
    import subprocess
    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    git_path = '/usr/bin/git' if os.path.exists('/usr/bin/git') else 'git'
    
    # Clean git gc lock if exists
    gc_pid_path = os.path.join(app_dir, '.git', 'gc.pid')
    if os.path.exists(gc_pid_path):
        try:
            os.remove(gc_pid_path)
        except Exception:
            pass
            
    results = {}
    try:
        # Convert to shallow clone
        cmd1 = subprocess.run([git_path, 'fetch', '--depth=1', 'origin', 'v2'], cwd=app_dir, capture_output=True, text=True, timeout=90)
        results['fetch'] = f'stdout: {cmd1.stdout.strip()}, stderr: {cmd1.stderr.strip()}'
        
        cmd2 = subprocess.run([git_path, 'reflog', 'expire', '--expire=now', '--all'], cwd=app_dir, capture_output=True, text=True, timeout=60)
        results['reflog'] = f'stdout: {cmd2.stdout.strip()}, stderr: {cmd2.stderr.strip()}'
        
        cmd3 = subprocess.run([git_path, 'gc', '--prune=now'], cwd=app_dir, capture_output=True, text=True, timeout=120)
        results['gc'] = f'stdout: {cmd3.stdout.strip()}, stderr: {cmd3.stderr.strip()}'
    except Exception as e:
        results['error'] = str(e)
        
    return jsonify(results)


def register_events(socketio):
    return None
