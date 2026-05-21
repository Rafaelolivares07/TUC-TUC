import os
import tempfile
import secrets as _sec
from flask import Blueprint, render_template, request, session, redirect, jsonify
from ..db import get_db_connection

import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

bp = Blueprint('crm', __name__)

_AUDIO_TMP = os.path.join(tempfile.gettempdir(), 'tuctuc_audio_chunks')
os.makedirs(_AUDIO_TMP, exist_ok=True)

_schema_chat_listo = False


def job_verificar_recordatorios():
    """Tarea APScheduler — verifica recordatorios pendientes"""
    pass


def get_chat_tercero_id():
    return session.get('chat_tercero_id') or session.get('usuario_id') or None


# ── Páginas ────────────────────────────────────────────────────────────────

@bp.route('/chat')
def chat_panel():
    if 'usuario_id' not in session:
        return redirect('/login')
    mi_id = session.get('chat_tercero_id') or session.get('usuario_id')
    return render_template('chat.html',
                           mi_tercero_id=mi_id,
                           es_invitado=False,
                           token_inicial='')


@bp.route('/chat2')
def chat_panel_v2():
    if 'usuario_id' not in session:
        return redirect('/login')
    mi_id = session.get('chat_tercero_id') or session.get('usuario_id')
    return render_template('chat_v3.html',
                           mi_tercero_id=mi_id,
                           es_invitado=False,
                           token_inicial='')



@bp.route('/chat/<token>')
def chat_invitado(token):
    try:
        conn = get_db_connection()
        conv = conn.execute(
            'SELECT invitado_id, activa FROM conversaciones WHERE token = %s', (token,)
        ).fetchone()
        conn.close()
    except Exception:
        conv = None

    if not conv or not conv['activa']:
        return "Conversación no encontrada", 404

    if 'usuario_id' not in session:
        session['chat_tercero_id'] = conv['invitado_id']
        session['chat_token'] = token

    mi_id = session.get('usuario_id') or conv['invitado_id']
    es_inv = 'usuario_id' not in session

    return render_template('chat.html',
                           mi_tercero_id=mi_id,
                           es_invitado=es_inv,
                           token_inicial=token)


# ── Helpers de schema ─────────────────────────────────────────────────────

def _asegurar_schema_chat(conn):
    global _schema_chat_listo
    if _schema_chat_listo:
        return
    _schema_chat_listo = True
    for sql in [
        """CREATE TABLE IF NOT EXISTS conversaciones (
            id SERIAL PRIMARY KEY,
            creador_id INTEGER NOT NULL,
            invitado_id INTEGER NOT NULL,
            token VARCHAR(100) UNIQUE NOT NULL,
            nombre_invitado VARCHAR(200),
            origen TEXT,
            activa BOOLEAN DEFAULT TRUE,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            invitacion_usada BOOLEAN DEFAULT FALSE,
            invitacion_usada_en TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS mensajes (
            id SERIAL PRIMARY KEY,
            remitente_id INTEGER NOT NULL,
            destinatario_id INTEGER NOT NULL,
            mensaje TEXT DEFAULT '',
            tipo VARCHAR(20) DEFAULT 'texto',
            url_archivo TEXT,
            card_payload JSONB,
            conversacion_id INTEGER,
            estado VARCHAR(20) DEFAULT 'pendiente',
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "ALTER TABLE mensajes ADD COLUMN IF NOT EXISTS url_archivo TEXT",
        "ALTER TABLE mensajes ADD COLUMN IF NOT EXISTS conversacion_id INTEGER",
        "ALTER TABLE mensajes ADD COLUMN IF NOT EXISTS card_payload JSONB",
        "ALTER TABLE terceros ADD COLUMN IF NOT EXISTS foto_perfil TEXT",
        "ALTER TABLE terceros ADD COLUMN IF NOT EXISTS token_chat VARCHAR(100)",
        "ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS origen TEXT",
        "ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS activa BOOLEAN DEFAULT TRUE",
        "ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS nombre_invitado VARCHAR(200)",
        "ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS invitacion_usada BOOLEAN DEFAULT FALSE",
        "ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS invitacion_usada_en TIMESTAMP",
        # Fix secuencias SERIAL rotas (tabla preexistente sin DEFAULT en id)
        "CREATE SEQUENCE IF NOT EXISTS mensajes_id_seq",
        "ALTER TABLE mensajes ALTER COLUMN id SET DEFAULT nextval('mensajes_id_seq')",
        "SELECT setval('mensajes_id_seq', COALESCE((SELECT MAX(id) FROM mensajes), 0) + 1, false)",
        "CREATE SEQUENCE IF NOT EXISTS conversaciones_id_seq",
        "ALTER TABLE conversaciones ALTER COLUMN id SET DEFAULT nextval('conversaciones_id_seq')",
        "SELECT setval('conversaciones_id_seq', COALESCE((SELECT MAX(id) FROM conversaciones), 0) + 1, false)",
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass


def _crear_tabla_fotos(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS fotos_tercero (
            id SERIAL PRIMARY KEY,
            tercero_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            orden INTEGER DEFAULT 0,
            subida_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def _asegurar_tabla_apuntes(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS apuntes (
            id          SERIAL PRIMARY KEY,
            autor_id    INTEGER NOT NULL,
            token_conv  VARCHAR(100) NOT NULL,
            contenido   TEXT,
            tipo        VARCHAR(20) DEFAULT 'texto',
            url_archivo TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


# ── API chat ──────────────────────────────────────────────────────────────

@bp.route('/api/chat/invitar', methods=['POST'])
def api_chat_invitar():
    usuario_id = get_chat_tercero_id()
    if not usuario_id:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json()
    nombre = (data.get('nombre') or 'Invitado').strip()
    origen = (data.get('origen') or '').strip()
    try:
        token = _sec.token_urlsafe(12)
        conn = get_db_connection()
        invitado = conn.execute('''
            INSERT INTO terceros (nombre, token_chat, tipo_tercero)
            VALUES (%s, %s, 'invitado') RETURNING id
        ''', (nombre, token)).fetchone()
        conv = conn.execute('''
            INSERT INTO conversaciones (creador_id, invitado_id, token, nombre_invitado, origen)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        ''', (usuario_id, invitado['id'], token, nombre, origen)).fetchone()
        conn.commit()
        conn.close()
        host = request.host_url.rstrip('/')
        return jsonify({'ok': True, 'token': token, 'link': f'{host}/chat/{token}',
                        'nombre': nombre, 'conv_id': conv['id']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/invitado/invitar', methods=['POST'])
def api_chat_invitado_invitar():
    data = request.get_json()
    token_inv = (data.get('token_invitado') or '').strip()
    nombre_nuevo = (data.get('nombre') or 'Invitado').strip()
    origen = (data.get('origen') or '').strip()
    if not token_inv:
        return jsonify({'ok': False, 'error': 'token_invitado requerido'}), 400
    try:
        conn = get_db_connection()
        invitador = conn.execute(
            "SELECT id, nombre FROM terceros WHERE token_chat = %s AND tipo_tercero = 'invitado'",
            (token_inv,)
        ).fetchone()
        if not invitador:
            conn.close()
            return jsonify({'ok': False, 'error': 'Token inválido'}), 404
        nuevo_token = _sec.token_urlsafe(12)
        nuevo = conn.execute('''
            INSERT INTO terceros (nombre, token_chat, tipo_tercero)
            VALUES (%s, %s, 'invitado') RETURNING id
        ''', (nombre_nuevo, nuevo_token)).fetchone()
        conn.execute('''
            INSERT INTO conversaciones (creador_id, invitado_id, token, nombre_invitado, origen)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        ''', (invitador['id'], nuevo['id'], nuevo_token, nombre_nuevo, origen))
        conn.commit()
        conn.close()
        host = request.host_url.rstrip('/')
        return jsonify({'ok': True, 'token': nuevo_token,
                        'link': f'{host}/chat/{nuevo_token}', 'nombre': nombre_nuevo})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/reclamar/<token>', methods=['POST'])
def api_chat_reclamar(token):
    try:
        conn = get_db_connection()
        conn.execute('ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS invitacion_usada BOOLEAN DEFAULT FALSE')
        conn.execute('ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS invitacion_usada_en TIMESTAMP')
        conn.commit()
        row = conn.execute(
            'SELECT id, invitacion_usada FROM conversaciones WHERE token = %s', (token,)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({'ok': False, 'error': 'no_existe'}), 404
        if row['invitacion_usada']:
            conn.close()
            return jsonify({'ok': False, 'error': 'ya_usado'})
        conn.execute(
            'UPDATE conversaciones SET invitacion_usada = TRUE, invitacion_usada_en = NOW() WHERE id = %s',
            (row['id'],)
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/invitado/mensajes/<token>', methods=['GET'])
def api_chat_invitado_mensajes(token):
    try:
        conn = get_db_connection()
        _asegurar_schema_chat(conn)
        conv = conn.execute('''
            SELECT c.*, t_inv.nombre as nombre_invitado, t_cre.nombre as nombre_creador
            FROM conversaciones c
            JOIN terceros t_inv ON c.invitado_id = t_inv.id
            JOIN terceros t_cre ON c.creador_id = t_cre.id
            WHERE c.token = %s AND c.activa = TRUE
        ''', (token,)).fetchone()
        if not conv:
            conn.close()
            return jsonify({'ok': False, 'error': 'Conversación no encontrada'}), 404
        desde_id = request.args.get('desde', 0, type=int)
        mensajes = conn.execute('''
            SELECT m.id, m.remitente_id, m.mensaje, m.tipo, m.url_archivo, m.estado, m.fecha,
                   m.card_payload,
                   t.nombre as remitente_nombre, t.tipo_tercero as remitente_tipo
            FROM mensajes m
            JOIN terceros t ON m.remitente_id = t.id
            WHERE m.conversacion_id = %s AND m.id > %s
            ORDER BY m.fecha ASC
        ''', (conv['id'], desde_id)).fetchall()
        viewer_id = get_chat_tercero_id()
        if viewer_id:
            otro_id = conv['creador_id'] if viewer_id == conv['invitado_id'] else conv['invitado_id']
        else:
            otro_id = conv['invitado_id']
        conn.execute('''
            UPDATE mensajes SET estado = 'leido'
            WHERE conversacion_id = %s AND remitente_id = %s AND estado = 'pendiente'
        ''', (conv['id'], otro_id))
        conn.commit()
        conn.close()

        def _ser_msg(m):
            from zoneinfo import ZoneInfo
            _bogota = ZoneInfo('America/Bogota')
            d = dict(m)
            if d.get('fecha') and hasattr(d['fecha'], 'replace'):
                d['fecha'] = d['fecha'].replace(tzinfo=_bogota).isoformat()
            return d

        return jsonify({'ok': True, 'conv': dict(conv),
                        'mensajes': [_ser_msg(m) for m in mensajes]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/invitado/enviar', methods=['POST'])
def api_chat_invitado_enviar():
    data = request.get_json()
    token = data.get('token', '').strip()
    mensaje = (data.get('mensaje') or '').strip()
    tipo = data.get('tipo', 'texto')
    url_archivo = data.get('url_archivo', '')
    card_payload = data.get('card_payload') or None
    es_creador = data.get('es_creador', False)
    if not token or (not mensaje and not url_archivo and not card_payload):
        return jsonify({'ok': False, 'error': 'Faltan datos'}), 400
    try:
        import json as _json
        conn = get_db_connection()
        _asegurar_schema_chat(conn)
        conv = conn.execute(
            'SELECT * FROM conversaciones WHERE token = %s AND activa = TRUE', (token,)
        ).fetchone()
        if not conv:
            conn.close()
            return jsonify({'ok': False, 'error': 'Conversación no válida'}), 404
        if es_creador:
            sender = get_chat_tercero_id()
            if not sender or sender != conv['creador_id']:
                conn.close()
                return jsonify({'ok': False, 'error': 'No autorizado'}), 401
            remitente_id = conv['creador_id']
            destinatario_id = conv['invitado_id']
        else:
            remitente_id = conv['invitado_id']
            destinatario_id = conv['creador_id']
        nuevo = conn.execute('''
            INSERT INTO mensajes (remitente_id, destinatario_id, mensaje, tipo, url_archivo,
                                  card_payload, conversacion_id, estado, fecha)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pendiente', CURRENT_TIMESTAMP)
            RETURNING id, fecha
        ''', (remitente_id, destinatario_id, mensaje or '', tipo, url_archivo,
              _json.dumps(card_payload) if card_payload else None, conv['id'])).fetchone()
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'id': nuevo['id'], 'fecha': str(nuevo['fecha'])})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/invitado/audio', methods=['POST'])
def api_chat_invitado_audio():
    if 'audio' not in request.files:
        return jsonify({'ok': False, 'error': 'No se recibió audio'}), 400
    try:
        result = cloudinary.uploader.upload(
            request.files['audio'],
            resource_type='video',
            folder='tuctuc_chat_audio',
            format='mp3'
        )
        return jsonify({'ok': True, 'url': result['secure_url']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/audio/chunk', methods=['POST'])
def api_chat_audio_chunk():
    upload_id = request.form.get('upload_id', '').strip()
    upload_id = ''.join(c for c in upload_id if c.isalnum() or c == '-')
    if not upload_id or len(upload_id) > 64:
        return jsonify({'ok': False, 'error': 'upload_id inválido'}), 400
    if 'chunk' not in request.files:
        return jsonify({'ok': False, 'error': 'Sin chunk'}), 400
    try:
        chunk_path = os.path.join(_AUDIO_TMP, f'{upload_id}.webm')
        data = request.files['chunk'].read()
        with open(chunk_path, 'ab') as f:
            f.write(data)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/audio/finalizar', methods=['POST'])
def api_chat_audio_finalizar():
    import time as _time
    upload_id = request.form.get('upload_id', '').strip()
    upload_id = ''.join(c for c in upload_id if c.isalnum() or c == '-')
    if not upload_id:
        return jsonify({'ok': False, 'error': 'Sin upload_id'}), 400
    chunk_path = os.path.join(_AUDIO_TMP, f'{upload_id}.webm')
    if 'chunk' in request.files:
        data = request.files['chunk'].read()
        with open(chunk_path, 'ab') as f:
            f.write(data)
    if not os.path.exists(chunk_path):
        return jsonify({'ok': False, 'error': 'Audio no encontrado'}), 404
    try:
        with open(chunk_path, 'rb') as f:
            result = cloudinary.uploader.upload(
                f, resource_type='video', folder='tuctuc_chat_audio', format='mp3'
            )
        return jsonify({'ok': True, 'url': result['secure_url']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        try: os.remove(chunk_path)
        except Exception: pass
        try:
            ahora = _time.time()
            for fn in os.listdir(_AUDIO_TMP):
                fp = os.path.join(_AUDIO_TMP, fn)
                if ahora - os.path.getmtime(fp) > 3600:
                    os.remove(fp)
        except Exception: pass


@bp.route('/api/chat/invitado/imagen', methods=['POST'])
def api_chat_invitado_imagen():
    if 'imagen' not in request.files:
        return jsonify({'ok': False, 'error': 'No se recibió imagen'}), 400
    try:
        result = cloudinary.uploader.upload(
            request.files['imagen'],
            folder='tuctuc_chat_imagenes',
            transformation=[{'width': 1200, 'crop': 'limit', 'quality': 'auto'}]
        )
        return jsonify({'ok': True, 'url': result['secure_url']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/mis-conversaciones', methods=['GET'])
def api_chat_mis_conversaciones():
    mid = get_chat_tercero_id()
    if not mid:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        _asegurar_schema_chat(conn)
        convs = conn.execute('''
            SELECT c.id, c.token, c.origen, c.creador_id,
                   CASE WHEN c.creador_id = %(mid)s THEN c.invitado_id ELSE c.creador_id END AS otro_id,
                   t_otro.nombre    AS nombre_otro,
                   t_otro.foto_perfil AS foto_otro,
                   t_otro.tipo_tercero AS tipo_otro,
                   (SELECT COUNT(*) FROM mensajes m
                    WHERE m.conversacion_id = c.id
                      AND m.remitente_id != %(mid)s
                      AND m.estado = 'pendiente') AS no_leidos,
                   (SELECT m2.mensaje FROM mensajes m2
                    WHERE m2.conversacion_id = c.id
                    ORDER BY m2.fecha DESC LIMIT 1) AS ultimo_mensaje,
                   (SELECT m2.tipo FROM mensajes m2
                    WHERE m2.conversacion_id = c.id
                    ORDER BY m2.fecha DESC LIMIT 1) AS ultimo_tipo,
                   (SELECT m2.fecha FROM mensajes m2
                    WHERE m2.conversacion_id = c.id
                    ORDER BY m2.fecha DESC LIMIT 1) AS ultima_fecha
            FROM conversaciones c
            JOIN terceros t_otro
              ON t_otro.id = CASE WHEN c.creador_id = %(mid)s THEN c.invitado_id ELSE c.creador_id END
            WHERE (c.creador_id = %(mid)s OR c.invitado_id = %(mid)s) AND c.activa = TRUE
            ORDER BY ultima_fecha DESC NULLS LAST
        ''', {'mid': mid}).fetchall()
        conn.close()
        return jsonify({'ok': True, 'conversaciones': [dict(c) for c in convs]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/mi-perfil', methods=['GET'])
def api_chat_mi_perfil():
    mid = get_chat_tercero_id()
    if not mid:
        return jsonify({'ok': False}), 401
    try:
        conn = get_db_connection()
        row = conn.execute(
            'SELECT id, nombre, foto_perfil, token_chat, tipo_tercero FROM terceros WHERE id = %s', (mid,)
        ).fetchone()
        conn.close()
        if row:
            return jsonify({'ok': True, 'id': row['id'], 'nombre': row['nombre'],
                            'foto': row['foto_perfil'] or '', 'token_chat': row['token_chat'] or '',
                            'tipo_tercero': row['tipo_tercero'] or 'invitado'})
        return jsonify({'ok': False})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@bp.route('/api/chat/registrar-telefono', methods=['POST'])
def api_chat_registrar_telefono():
    mid = get_chat_tercero_id()
    if not mid:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    telefono = (data.get('telefono') or '').strip()
    nombre   = (data.get('nombre')   or '').strip()
    if not telefono or len(telefono) < 7:
        return jsonify({'ok': False, 'error': 'Teléfono inválido'})
    try:
        conn = get_db_connection()
        actual = conn.execute(
            'SELECT id, tipo_tercero, telefono FROM terceros WHERE id = %s', (mid,)
        ).fetchone()
        if not actual:
            conn.close()
            return jsonify({'ok': False, 'error': 'Usuario no encontrado'})
        if actual['tipo_tercero'] == 'registrado' and actual['telefono']:
            conn.close()
            return jsonify({'ok': False, 'error': 'Ya tienes cuenta registrada'})
        existente = conn.execute(
            'SELECT id FROM terceros WHERE telefono = %s AND id != %s', (telefono, mid)
        ).fetchone()
        if existente:
            winner = existente['id']
            for tabla, col in [('conversaciones','creador_id'), ('conversaciones','invitado_id'),
                                ('mensajes','remitente_id'), ('mensajes','destinatario_id')]:
                conn.execute(f'UPDATE {tabla} SET {col} = %s WHERE {col} = %s', (winner, mid))
            if nombre:
                conn.execute('UPDATE terceros SET nombre = %s WHERE id = %s', (nombre, winner))
            conn.execute('DELETE FROM terceros WHERE id = %s', (mid,))
            conn.commit()
            conn.close()
            session.pop('chat_tercero_id', None)
            session.pop('chat_token', None)
            session['usuario_id'] = winner
            return jsonify({'ok': True, 'tercero_id': winner, 'merged': True})
        else:
            updates = ['tipo_tercero = %s', 'telefono = %s']
            params  = ['registrado', telefono]
            if nombre:
                updates.append('nombre = %s')
                params.append(nombre)
            params.append(mid)
            conn.execute(f"UPDATE terceros SET {', '.join(updates)} WHERE id = %s", params)
            conn.commit()
            conn.close()
            session.pop('chat_tercero_id', None)
            session.pop('chat_token', None)
            session['usuario_id'] = mid
            return jsonify({'ok': True, 'tercero_id': mid, 'merged': False})
    except Exception as e:
        try: conn.rollback()
        except: pass
        return jsonify({'ok': False, 'error': str(e)})


@bp.route('/api/chat/perfil/foto', methods=['POST'])
def api_chat_perfil_foto():
    token_inv = request.form.get('token_invitado', '').strip()
    usuario_id = get_chat_tercero_id()
    if not usuario_id and not token_inv:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    if 'foto' not in request.files:
        return jsonify({'ok': False, 'error': 'No se recibió foto'}), 400
    try:
        result = cloudinary.uploader.upload(
            request.files['foto'],
            folder='tuctuc_chat_avatars',
            transformation=[{'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'}]
        )
        url = result['secure_url']
        conn = get_db_connection()
        conn.execute('ALTER TABLE terceros ADD COLUMN IF NOT EXISTS foto_perfil TEXT')
        if usuario_id:
            conn.execute('UPDATE terceros SET foto_perfil = %s WHERE id = %s', (url, usuario_id))
        else:
            conn.execute(
                "UPDATE terceros SET foto_perfil = %s WHERE token_chat = %s AND tipo_tercero = 'invitado'",
                (url, token_inv)
            )
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'url': url})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/eliminar/<token>', methods=['DELETE'])
def api_chat_eliminar(token):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        conv = conn.execute(
            'SELECT * FROM conversaciones WHERE token = %s AND creador_id = %s',
            (token, session['usuario_id'])
        ).fetchone()
        if not conv:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        conn.execute('DELETE FROM mensajes WHERE conversacion_id = %s', (conv['id'],))
        conn.execute('DELETE FROM conversaciones WHERE id = %s', (conv['id'],))
        conn.execute("DELETE FROM terceros WHERE id = %s AND tipo_tercero = 'invitado'",
                     (conv['invitado_id'],))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Galería de fotos ───────────────────────────────────────────────────────

@bp.route('/api/chat/fotos/agregar', methods=['POST'])
def api_chat_fotos_agregar():
    token_inv = request.form.get('token_invitado', '').strip()
    usuario_id = session.get('usuario_id')
    if not usuario_id and not token_inv:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    if 'foto' not in request.files:
        return jsonify({'ok': False, 'error': 'No se recibió foto'}), 400
    try:
        result = cloudinary.uploader.upload(
            request.files['foto'],
            folder='tuctuc_chat_fotos',
            transformation=[{'width': 800, 'height': 800, 'crop': 'limit'}]
        )
        url = result['secure_url']
        conn = get_db_connection()
        _crear_tabla_fotos(conn)
        if usuario_id:
            tercero_id = usuario_id
        else:
            row = conn.execute(
                "SELECT id FROM terceros WHERE token_chat = %s AND tipo_tercero = 'invitado'",
                (token_inv,)
            ).fetchone()
            if not row:
                conn.close()
                return jsonify({'ok': False, 'error': 'Token inválido'}), 404
            tercero_id = row['id']
        orden = conn.execute(
            'SELECT COALESCE(MAX(orden), -1) + 1 FROM fotos_tercero WHERE tercero_id = %s',
            (tercero_id,)
        ).fetchone()[0]
        nueva = conn.execute(
            'INSERT INTO fotos_tercero (tercero_id, url, orden) VALUES (%s, %s, %s) RETURNING id',
            (tercero_id, url, orden)
        ).fetchone()
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'id': nueva['id'], 'url': url, 'orden': orden})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/fotos/ver', methods=['GET'])
def api_chat_fotos_ver():
    tercero_id = request.args.get('tercero_id')
    token_inv = request.args.get('token', '').strip()
    try:
        conn = get_db_connection()
        _crear_tabla_fotos(conn)
        if not tercero_id and token_inv:
            row = conn.execute('SELECT id FROM terceros WHERE token_chat = %s', (token_inv,)).fetchone()
            if row:
                tercero_id = row['id']
        if not tercero_id:
            conn.close()
            return jsonify({'ok': False, 'fotos': []})
        fotos = conn.execute(
            'SELECT id, url, orden FROM fotos_tercero WHERE tercero_id = %s ORDER BY orden ASC',
            (int(tercero_id),)
        ).fetchall()
        resultado = [dict(f) for f in fotos]
        if not resultado:
            row = conn.execute(
                'SELECT foto_perfil FROM terceros WHERE id = %s AND foto_perfil IS NOT NULL',
                (int(tercero_id),)
            ).fetchone()
            if row and row['foto_perfil']:
                resultado = [{'id': None, 'url': row['foto_perfil'], 'orden': 0}]
        conn.close()
        return jsonify({'ok': True, 'fotos': resultado})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'fotos': []})


@bp.route('/api/chat/fotos/<int:foto_id>', methods=['DELETE'])
def api_chat_fotos_eliminar(foto_id):
    body = request.get_json(silent=True, force=True) or {}
    token_inv = body.get('token_invitado', '') if isinstance(body, dict) else ''
    usuario_id = session.get('usuario_id')
    if not usuario_id and not token_inv:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        _crear_tabla_fotos(conn)
        foto = conn.execute('SELECT * FROM fotos_tercero WHERE id = %s', (foto_id,)).fetchone()
        if not foto:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrada'}), 404
        if usuario_id:
            autorizado = (foto['tercero_id'] == usuario_id)
        else:
            inv = conn.execute('SELECT id FROM terceros WHERE token_chat = %s', (token_inv,)).fetchone()
            autorizado = inv and foto['tercero_id'] == inv['id']
        if not autorizado:
            conn.close()
            return jsonify({'ok': False, 'error': 'Sin permiso'}), 403
        conn.execute('DELETE FROM fotos_tercero WHERE id = %s', (foto_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Merlin ─────────────────────────────────────────────────────────────────

@bp.route('/api/chat/merlin/iniciar', methods=['POST'])
def api_chat_merlin_iniciar():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    usuario_id = session['usuario_id']
    try:
        conn = get_db_connection()
        merlin = conn.execute(
            "SELECT id FROM terceros WHERE tipo_tercero = 'merlin' LIMIT 1"
        ).fetchone()
        if not merlin:
            merlin = conn.execute(
                "INSERT INTO terceros (nombre, tipo_tercero) VALUES ('Merlin', 'merlin') RETURNING id"
            ).fetchone()
            conn.commit()
        merlin_id = merlin['id']
        conv = conn.execute(
            """SELECT token FROM conversaciones
               WHERE creador_id = %s AND invitado_id = %s AND activa = TRUE LIMIT 1""",
            (usuario_id, merlin_id)
        ).fetchone()
        if conv:
            conn.close()
            host = request.host_url.rstrip('/')
            return jsonify({'ok': True, 'token': conv['token'],
                            'link': f"{host}/chat/{conv['token']}", 'nuevo': False})
        token = _sec.token_urlsafe(12)
        conn.execute(
            """INSERT INTO conversaciones (creador_id, invitado_id, token, nombre_invitado, origen)
               VALUES (%s, %s, %s, 'Merlin', 'merlin')""",
            (usuario_id, merlin_id, token)
        )
        conn.commit()
        conn.close()
        host = request.host_url.rstrip('/')
        return jsonify({'ok': True, 'token': token,
                        'link': f"{host}/chat/{token}", 'nuevo': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Cards de negocios ──────────────────────────────────────────────────────

@bp.route('/api/chat/cards/negocios')
def api_chat_cards_negocios():
    token_chat = request.args.get('token_chat', '').strip()
    uid = session.get('usuario_id')
    try:
        conn = get_db_connection()
        tercero_id = None
        if token_chat:
            t = conn.execute(
                "SELECT id FROM terceros WHERE token_chat = %s LIMIT 1", (token_chat,)
            ).fetchone()
            if t:
                tercero_id = t['id']
        elif uid:
            tercero_id = uid
        if not tercero_id:
            conn.close()
            return jsonify({'ok': True, 'negocios': []})
        negocios = []
        rests = conn.execute("""
            SELECT 'restaurante' as tipo, slug, nombre, NULL as imagen
            FROM restaurantes WHERE admin_id = %s AND activo = TRUE ORDER BY nombre
        """, (tercero_id,)).fetchall()
        negocios.extend([dict(r) for r in rests])
        tiendas = conn.execute("""
            SELECT 'tienda' as tipo, slug, nombre, NULL as imagen
            FROM tiendas WHERE admin_id = %s AND activo = TRUE ORDER BY nombre
        """, (tercero_id,)).fetchall()
        negocios.extend([dict(t) for t in tiendas])
        conn.close()
        return jsonify({'ok': True, 'negocios': negocios})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/cards/items')
def api_chat_cards_items():
    tipo = request.args.get('tipo', '').strip()
    slug = request.args.get('slug', '').strip()
    if not tipo or not slug:
        return jsonify({'ok': False, 'error': 'tipo y slug requeridos'}), 400
    try:
        conn = get_db_connection()
        items = []
        host = request.host_url.rstrip('/')
        if tipo == 'restaurante':
            rest = conn.execute(
                "SELECT id, nombre FROM restaurantes WHERE slug = %s LIMIT 1", (slug,)
            ).fetchone()
            if rest:
                rows = conn.execute("""
                    SELECT id, nombre, precio, imagen, descripcion, tipo
                    FROM opciones_menu WHERE restaurante_id = %s AND activo = TRUE
                    ORDER BY tipo, nombre
                """, (rest['id'],)).fetchall()
                items = [{'id': r['id'], 'titulo': r['nombre'], 'descripcion': r['descripcion'] or '',
                          'precio': r['precio'], 'imagen': r['imagen'] or '',
                          'negocio': rest['nombre'], 'tipo_item': r['tipo'] or 'plato',
                          'url': f"{host}/r/{slug}", 'tipo_card': 'plato'} for r in rows]
        elif tipo == 'tienda':
            tienda = conn.execute(
                "SELECT id, nombre FROM tiendas WHERE slug = %s LIMIT 1", (slug,)
            ).fetchone()
            if tienda:
                rows = conn.execute("""
                    SELECT id, nombre, precio, imagen, descripcion
                    FROM productos_tienda WHERE tienda_id = %s AND disponible = TRUE ORDER BY nombre
                """, (tienda['id'],)).fetchall()
                items = [{'id': r['id'], 'titulo': r['nombre'], 'descripcion': r['descripcion'] or '',
                          'precio': r['precio'], 'imagen': r['imagen'] or '',
                          'negocio': tienda['nombre'], 'tipo_item': 'producto',
                          'url': f"{host}/t/{slug}", 'tipo_card': 'producto'} for r in rows]
        conn.close()
        return jsonify({'ok': True, 'items': items})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Estados de mensajes ────────────────────────────────────────────────────

@bp.route('/api/chat/mensajes/estados', methods=['GET'])
def api_chat_mensajes_estados():
    ids_str = request.args.get('ids', '')
    if not ids_str:
        return jsonify({'ok': True, 'estados': {}})
    try:
        ids = [int(i) for i in ids_str.split(',') if i.strip().isdigit()]
    except Exception:
        return jsonify({'ok': True, 'estados': {}})
    if not ids:
        return jsonify({'ok': True, 'estados': {}})
    try:
        conn = get_db_connection()
        rows = conn.execute('SELECT id, estado FROM mensajes WHERE id = ANY(%s)', (ids,)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'estados': {str(r['id']): r['estado'] for r in rows}})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Apuntes ────────────────────────────────────────────────────────────────

@bp.route('/api/chat/apunte', methods=['POST'])
def api_chat_apunte_crear():
    autor_id = get_chat_tercero_id()
    if not autor_id:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json()
    token = (data.get('token') or '').strip()
    contenido = (data.get('contenido') or '').strip()
    tipo = data.get('tipo', 'texto')
    url_archivo = data.get('url_archivo') or None
    if not token:
        return jsonify({'ok': False, 'error': 'token requerido'}), 400
    try:
        conn = get_db_connection()
        _asegurar_tabla_apuntes(conn)
        row = conn.execute("""
            INSERT INTO apuntes (autor_id, token_conv, contenido, tipo, url_archivo)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (autor_id, token, contenido or None, tipo, url_archivo)).fetchone()
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'id': row['id']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/apuntes/<token>', methods=['GET'])
def api_chat_apuntes_listar(token):
    autor_id = get_chat_tercero_id()
    if not autor_id:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        from zoneinfo import ZoneInfo
        _bogota = ZoneInfo('America/Bogota')
        conn = get_db_connection()
        _asegurar_tabla_apuntes(conn)
        rows = conn.execute("""
            SELECT id, contenido, tipo, url_archivo, created_at
            FROM apuntes WHERE token_conv = %s AND autor_id = %s ORDER BY created_at ASC
        """, (token, autor_id)).fetchall()
        conn.close()
        def _ser(r):
            d = dict(r)
            if d.get('created_at') and hasattr(d['created_at'], 'replace'):
                d['created_at'] = d['created_at'].replace(tzinfo=_bogota).isoformat()
            return d
        return jsonify({'ok': True, 'apuntes': [_ser(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/apunte/<int:apunte_id>', methods=['DELETE'])
def api_chat_apunte_eliminar(apunte_id):
    autor_id = get_chat_tercero_id()
    if not autor_id:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM apuntes WHERE id = %s AND autor_id = %s", (apunte_id, autor_id))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
