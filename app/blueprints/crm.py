import os
import tempfile
import json
import threading
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
        conv = conn.execute('''
            SELECT c.creador_id, c.invitado_id, c.activa,
                   t_cre.nombre AS nombre_creador, t_inv.nombre AS nombre_invitado
            FROM conversaciones c
            LEFT JOIN terceros t_cre ON t_cre.id = c.creador_id
            LEFT JOIN terceros t_inv ON t_inv.id = c.invitado_id
            WHERE c.token = %s
        ''', (token,)).fetchone()
        conn.close()
    except Exception:
        conv = None

    if not conv or not conv['activa']:
        return "Conversación no encontrada", 404

    # Si quien abre el link no es participante de esta conversación
    # (sin sesión, o con sesión de otra persona/otro invitado), entra como el invitado.
    actual = get_chat_tercero_id()
    if actual not in (conv['creador_id'], conv['invitado_id']):
        session['chat_tercero_id'] = conv['invitado_id']
        session['chat_token'] = token
        actual = conv['invitado_id']

    es_inv = actual == conv['invitado_id']
    nombre_otro = conv['nombre_creador'] if es_inv else conv['nombre_invitado']

    return render_template('chat_v3.html',
                           mi_tercero_id=actual,
                           es_invitado=es_inv,
                           token_inicial=token,
                           nombre_inicial=nombre_otro or '')


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
        """CREATE TABLE IF NOT EXISTS chat_push_subscriptions (
            id SERIAL PRIMARY KEY,
            tercero_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            user_agent TEXT,
            activo BOOLEAN DEFAULT TRUE,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_chat_push_tercero ON chat_push_subscriptions(tercero_id)",
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


# ── Web Push Nativo (VAPID) ────────────────────────────────────────────────

_VAPID_CONFIG_CACHE = None

def _obtener_vapid_config():
    global _VAPID_CONFIG_CACHE
    if _VAPID_CONFIG_CACHE is not None:
        return _VAPID_CONFIG_CACHE
    keys_path = os.path.join(os.path.dirname(__file__), '..', 'vapid_keys.json')
    try:
        if os.path.isfile(keys_path):
            with open(keys_path, 'r', encoding='utf-8') as f:
                _VAPID_CONFIG_CACHE = json.load(f)
                return _VAPID_CONFIG_CACHE
    except Exception as e:
        print('[VAPID] Error cargando vapid_keys.json:', e)
    return None

def _despachar_push_asincrono(destinatario_id, titulo, cuerpo, token='', url='', icono=''):
    """Envía la notificación Web Push nativa en segundo plano para no demorar la respuesta HTTP."""
    if not destinatario_id:
        return
    try:
        t = threading.Thread(
            target=_enviar_push_a_tercero_worker,
            args=(int(destinatario_id), titulo, cuerpo, token, url, icono),
            daemon=True
        )
        t.start()
    except Exception as e:
        print('[VAPID dispatch error]:', e)

def _enviar_push_a_tercero_worker(destinatario_id, titulo, cuerpo, token, url, icono):
    cfg = _obtener_vapid_config()
    if not cfg or not cfg.get('private_key'):
        return
    try:
        from pywebpush import webpush, WebPushException
    except Exception as e:
        print('[VAPID] pywebpush no disponible:', e)
        return

    conn = None
    try:
        conn = get_db_connection()
        subs = conn.execute("""
            SELECT id, endpoint, p256dh, auth
            FROM chat_push_subscriptions
            WHERE tercero_id = %s AND activo = TRUE
        """, (destinatario_id,)).fetchall()
        if not subs:
            return

        payload_dict = {
            'title': titulo or 'Mensaje en TUC TUC',
            'body': cuerpo or 'Tienes un nuevo mensaje.',
            'icon': icono or '/static/icons/icon-192.png',
            'badge': '/static/icons/icon-192.png',
            'token': token or '',
            'url': url or (f"/chat2?open_token={token}" if token else "/chat2"),
            'vibrate': [300, 120, 300, 120, 450]
        }
        payload_data = json.dumps(payload_dict)
        priv_key = cfg['private_key']
        claims = {'sub': cfg.get('claims_sub') or 'mailto:admin@tuc-tuc.co'}

        for sub in subs:
            sub_info = {
                'endpoint': sub['endpoint'],
                'keys': {
                    'p256dh': sub['p256dh'],
                    'auth': sub['auth']
                }
            }
            try:
                webpush(
                    subscription_info=sub_info,
                    data=payload_data,
                    vapid_private_key=priv_key,
                    vapid_claims=claims,
                    timeout=6
                )
            except WebPushException as ex:
                resp = getattr(ex, 'response', None)
                status_code = getattr(resp, 'status_code', None)
                if status_code in (404, 410):
                    try:
                        conn.execute("UPDATE chat_push_subscriptions SET activo = FALSE WHERE id = %s", (sub['id'],))
                        conn.commit()
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        print('[VAPID worker error]:', e)
    finally:
        if conn:
            try: conn.close()
            except Exception: pass


@bp.route('/api/chat/vapid-public-key', methods=['GET'])
def api_chat_vapid_public_key():
    cfg = _obtener_vapid_config()
    if not cfg or not cfg.get('public_key'):
        return jsonify({'ok': False, 'error': 'VAPID no configurado'}), 500
    return jsonify({'ok': True, 'public_key': cfg['public_key']})


@bp.route('/api/chat/push/suscribir', methods=['POST'])
def api_chat_push_suscribir():
    data = request.get_json() or {}
    sub = data.get('subscription') or {}
    endpoint = (sub.get('endpoint') or '').strip()
    keys = sub.get('keys') or {}
    p256dh = (keys.get('p256dh') or '').strip()
    auth = (keys.get('auth') or '').strip()
    tercero_id = data.get('tercero_id') or get_chat_tercero_id() or session.get('usuario_id')

    if not endpoint or not p256dh or not auth or not tercero_id:
        return jsonify({'ok': False, 'error': 'Faltan parámetros de suscripción'}), 400

    try:
        conn = get_db_connection()
        _asegurar_schema_chat(conn)
        ua = request.headers.get('User-Agent', '')[:300]
        conn.execute("""
            INSERT INTO chat_push_subscriptions (tercero_id, endpoint, p256dh, auth, user_agent, activo, actualizado_en)
            VALUES (%s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (endpoint) DO UPDATE
            SET tercero_id = EXCLUDED.tercero_id,
                p256dh = EXCLUDED.p256dh,
                auth = EXCLUDED.auth,
                user_agent = EXCLUDED.user_agent,
                activo = TRUE,
                actualizado_en = CURRENT_TIMESTAMP
        """, (int(tercero_id), endpoint, p256dh, auth, ua))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'mensaje': 'Suscripción Web Push guardada'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/push/desuscribir', methods=['POST'])
def api_chat_push_desuscribir():
    data = request.get_json() or {}
    sub = data.get('subscription') or {}
    endpoint = (sub.get('endpoint') or '').strip()
    if not endpoint:
        return jsonify({'ok': False, 'error': 'Falta endpoint'}), 400
    try:
        conn = get_db_connection()
        conn.execute("UPDATE chat_push_subscriptions SET activo = FALSE WHERE endpoint = %s", (endpoint,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/push/test', methods=['GET', 'POST'])
def api_chat_push_test():
    """Envía una notificación push de prueba síncrona y retorna diagnóstico detallado."""
    data = request.get_json(silent=True) or {}
    tercero_id = data.get('tercero_id') or request.args.get('tercero_id') or get_chat_tercero_id() or session.get('usuario_id')
    try:
        tercero_id = int(tercero_id) if tercero_id else None
    except (ValueError, TypeError):
        tercero_id = None

    cfg = _obtener_vapid_config()
    if not cfg:
        return jsonify({'ok': False, 'error': 'VAPID no configurado en servidor (app/vapid_keys.json)'})

    try:
        from pywebpush import webpush, WebPushException
        pywebpush_ok = True
    except Exception as e:
        return jsonify({'ok': False, 'error': f'pywebpush no disponible en servidor: {e}'})

    conn = get_db_connection()
    _asegurar_schema_chat(conn)
    if tercero_id:
        subs = conn.execute("SELECT id, endpoint, p256dh, auth, user_agent, tercero_id FROM chat_push_subscriptions WHERE tercero_id = %s AND activo = TRUE", (tercero_id,)).fetchall()
        if not subs:
            subs = conn.execute("SELECT id, endpoint, p256dh, auth, user_agent, tercero_id FROM chat_push_subscriptions WHERE activo = TRUE").fetchall()
    else:
        subs = conn.execute("SELECT id, endpoint, p256dh, auth, user_agent, tercero_id FROM chat_push_subscriptions WHERE activo = TRUE").fetchall()

    if not subs:
        conn.close()
        return jsonify({
            'ok': False,
            'subs_count': 0,
            'error': 'No hay dispositivos suscritos con notificaciones push activas. Primero abre el chat y presiona "Activar alertas con app cerrada".'
        })

    titulo = "🔔 Prueba de Alerta TUC TUC"
    cuerpo = "¡Prueba exitosa! Tu dispositivo está recibiendo alertas y sonido en segundo plano."
    payload_dict = {
        'title': titulo,
        'body': cuerpo,
        'icon': '/static/icons/icon-192.png',
        'badge': '/static/icons/icon-192.png',
        'url': '/chat2',
        'vibrate': [300, 120, 300, 120, 450]
    }
    payload_data = json.dumps(payload_dict)
    priv_key = cfg['private_key']
    claims = {'sub': cfg.get('claims_sub') or 'mailto:admin@tuc-tuc.co'}

    resultados = []
    for s in subs:
        sub_info = {
            'endpoint': s['endpoint'],
            'keys': {'p256dh': s['p256dh'], 'auth': s['auth']}
        }
        res_item = {'id': s['id'], 'endpoint': s['endpoint'][:50] + '...'}
        try:
            resp = webpush(
                subscription_info=sub_info,
                data=payload_data,
                vapid_private_key=priv_key,
                vapid_claims=claims,
                timeout=8
            )
            res_item['ok'] = True
            res_item['status_code'] = getattr(resp, 'status_code', 200)
        except WebPushException as ex:
            res_item['ok'] = False
            r = getattr(ex, 'response', None)
            code = getattr(r, 'status_code', None)
            res_item['status_code'] = code
            res_item['error'] = str(ex)
            if code in (404, 410):
                try:
                    conn.execute("UPDATE chat_push_subscriptions SET activo = FALSE WHERE id = %s", (s['id'],))
                    conn.commit()
                except Exception:
                    pass
        except Exception as e:
            res_item['ok'] = False
            res_item['error'] = str(e)
        resultados.append(res_item)

    conn.close()
    exitosos = sum(1 for r in resultados if r.get('ok'))
    return jsonify({
        'ok': True,
        'subs_count': len(subs),
        'exitosos': exitosos,
        'resultados': resultados,
        'mensaje': f'Prueba Web Push enviada a {len(subs)} dispositivo(s) ({exitosos} con éxito).'
    })


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
        viewer_id = request.args.get('viewer_id', type=int) or get_chat_tercero_id()
        if viewer_id in (conv['creador_id'], conv['invitado_id']):
            otro_id = conv['creador_id'] if viewer_id == conv['invitado_id'] else conv['invitado_id']
        else:
            otro_id = conv['creador_id']
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
    req_remitente = data.get('remitente_id')
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
        sender = get_chat_tercero_id()
        if req_remitente and int(req_remitente) in (conv['creador_id'], conv['invitado_id']):
            remitente_id = int(req_remitente)
            destinatario_id = conv['invitado_id'] if remitente_id == conv['creador_id'] else conv['creador_id']
        elif es_creador or (sender and sender == conv['creador_id']):
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

        # Despacho en segundo plano de notificación Web Push nativa (VAPID)
        try:
            nombre_rem = 'Alguien'
            row_rem = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (remitente_id,)).fetchone()
            if row_rem and row_rem['nombre']:
                nombre_rem = row_rem['nombre']
            
            cuerpo = mensaje or ''
            if tipo == 'audio':
                cuerpo = '🎤 Mensaje de voz'
            elif tipo == 'imagen':
                cuerpo = '📷 Imagen recibida'
            elif tipo == 'cancion':
                cuerpo = '🎵 ' + (cuerpo or 'Canción compartida')
            elif tipo == 'reporte':
                cuerpo = '📊 Reporte compartido'
            elif not cuerpo:
                cuerpo = 'Nuevo mensaje'
            
            if len(cuerpo) > 120:
                cuerpo = cuerpo[:117] + '...'
            
            titulo = f"💬 {nombre_rem} en TUC TUC"
            url_push = f"/chat2?open_token={conv['token']}"
            _despachar_push_asincrono(destinatario_id, titulo, cuerpo, token=conv['token'], url=url_push)
        except Exception as _ex_push:
            print('[Error despachando push]:', _ex_push)

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
    mid = get_chat_tercero_id()
    uid = session.get('usuario_id')
    ids_validos = tuple({x for x in (mid, uid) if x})
    if not ids_validos:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        placeholders = ', '.join(['%s'] * len(ids_validos))
        conv = conn.execute(
            f'''SELECT * FROM conversaciones
                WHERE token = %s
                  AND (creador_id IN ({placeholders}) OR invitado_id IN ({placeholders}))''',
            (token,) + ids_validos + ids_validos
        ).fetchone()
        if not conv:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        conn.execute('DELETE FROM mensajes WHERE conversacion_id = %s', (conv['id'],))
        try:
            conn.execute('DELETE FROM apuntes WHERE token_conv = %s', (token,))
        except Exception:
            pass
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
    usuario_id = get_chat_tercero_id()
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
    usuario_id = get_chat_tercero_id()
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
    usuario_id = get_chat_tercero_id()
    if not usuario_id:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
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


# ── Usuarios (Terceros) de los módulos + Enlazar + Globo flotante ──────────

@bp.route('/api/chat/usuarios/buscar', methods=['GET'])
def api_chat_usuarios_buscar():
    mid = get_chat_tercero_id()
    if not mid:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    q = (request.args.get('q') or '').strip()
    try:
        conn = get_db_connection()
        _asegurar_schema_chat(conn)
        like_q = f'%{q}%'
        rows = conn.execute('''
            SELECT t.id, t.nombre, COALESCE(t.telefono, '') AS telefono,
                   COALESCE(t.tipo_tercero, '') AS tipo_tercero,
                   COALESCE(t.foto_perfil, '') AS foto_perfil,
                   EXISTS(
                       SELECT 1 FROM terceros_negocios tn
                       WHERE tn.tercero_id = t.id AND tn.activo = TRUE
                   ) AS en_negocio
            FROM terceros t
            WHERE t.id != %(mid)s
              AND COALESCE(t.nombre, '') != ''
              AND COALESCE(t.tipo_tercero, '') NOT IN ('negocio', 'merlin')
              AND (
                  COALESCE(t.tipo_tercero, '') != 'invitado'
                  OR (t.telefono IS NOT NULL AND t.telefono != '')
                  OR EXISTS(SELECT 1 FROM terceros_negocios tn WHERE tn.tercero_id = t.id)
                  OR EXISTS(SELECT 1 FROM permisos_terceros pt WHERE pt.tercero_id = t.id)
              )
              AND (
                  %(q)s = ''
                  OR t.nombre ILIKE %(like_q)s
                  OR COALESCE(t.telefono, '') ILIKE %(like_q)s
                  OR CAST(t.id AS TEXT) = %(q)s
              )
            ORDER BY
              en_negocio DESC,
              (CASE WHEN COALESCE(t.telefono, '') != '' THEN 1 ELSE 0 END) DESC,
              t.nombre ASC
            LIMIT 30
        ''', {'mid': mid, 'q': q, 'like_q': like_q}).fetchall()
        conn.close()
        return jsonify({'ok': True, 'usuarios': [dict(r) for r in rows]})
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e), 'usuarios': []}), 500


@bp.route('/api/chat/iniciar-con-usuario', methods=['POST'])
def api_chat_iniciar_con_usuario():
    mid = get_chat_tercero_id()
    if not mid:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    target_id = data.get('usuario_tercero_id')
    try:
        target_id = int(target_id)
    except Exception:
        return jsonify({'ok': False, 'error': 'Usuario inválido'}), 400
    if target_id == int(mid):
        return jsonify({'ok': False, 'error': 'No puedes iniciar un chat contigo mismo'}), 400

    try:
        conn = get_db_connection()
        _asegurar_schema_chat(conn)
        target = conn.execute(
            'SELECT id, nombre, tipo_tercero FROM terceros WHERE id = %s', (target_id,)
        ).fetchone()
        if not target:
            conn.close()
            return jsonify({'ok': False, 'error': 'Usuario no encontrado'}), 404

        if not target['tipo_tercero'] or target['tipo_tercero'] == 'invitado':
            conn.execute(
                "UPDATE terceros SET tipo_tercero = 'registrado' WHERE id = %s", (target_id,)
            )

        conv = conn.execute('''
            SELECT id, token, activa FROM conversaciones
            WHERE (creador_id = %s AND invitado_id = %s)
               OR (creador_id = %s AND invitado_id = %s)
            ORDER BY activa DESC, id DESC LIMIT 1
        ''', (mid, target_id, target_id, mid)).fetchone()

        host = request.host_url.rstrip('/')
        if conv:
            if not conv['activa']:
                conn.execute('UPDATE conversaciones SET activa = TRUE WHERE id = %s', (conv['id'],))
            conn.commit()
            conn.close()
            return jsonify({
                'ok': True,
                'token': conv['token'],
                'nombre': target['nombre'],
                'link': f"{host}/chat/{conv['token']}",
                'existente': True
            })

        token = _sec.token_urlsafe(12)
        nueva = conn.execute('''
            INSERT INTO conversaciones (creador_id, invitado_id, token, nombre_invitado, origen, activa)
            VALUES (%s, %s, %s, %s, 'usuario_app', TRUE)
            RETURNING id
        ''', (mid, target_id, token, target['nombre'])).fetchone()
        conn.commit()
        conn.close()
        return jsonify({
            'ok': True,
            'token': token,
            'nombre': target['nombre'],
            'link': f'{host}/chat/{token}',
            'conv_id': nueva['id'],
            'existente': False
        })
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/enlazar-usuario', methods=['POST'])
def api_chat_enlazar_usuario():
    mid = get_chat_tercero_id()
    uid = session.get('usuario_id')
    ids_validos = tuple({int(x) for x in (mid, uid) if x})
    if not ids_validos:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    data = request.get_json() or {}
    token = (data.get('token') or '').strip()
    target_id = data.get('usuario_tercero_id')
    try:
        target_id = int(target_id)
    except Exception:
        return jsonify({'ok': False, 'error': 'Usuario inválido'}), 400
    if not token:
        return jsonify({'ok': False, 'error': 'Conversación requerida'}), 400

    try:
        conn = get_db_connection()
        _asegurar_schema_chat(conn)
        target = conn.execute(
            'SELECT id, nombre, tipo_tercero FROM terceros WHERE id = %s', (target_id,)
        ).fetchone()
        if not target:
            conn.close()
            return jsonify({'ok': False, 'error': 'Usuario no encontrado'}), 404

        placeholders = ', '.join(['%s'] * len(ids_validos))
        conv = conn.execute(
            f'''SELECT * FROM conversaciones
                WHERE token = %s
                  AND (creador_id IN ({placeholders}) OR invitado_id IN ({placeholders}))''',
            (token,) + ids_validos + ids_validos
        ).fetchone()
        if not conv:
            conn.close()
            return jsonify({'ok': False, 'error': 'Conversación no encontrada'}), 404

        es_creador = conv['creador_id'] in ids_validos
        mi_id_conv = conv['creador_id'] if es_creador else conv['invitado_id']
        old_otro_id = conv['invitado_id'] if es_creador else conv['creador_id']

        if target_id == mi_id_conv:
            conn.close()
            return jsonify({'ok': False, 'error': 'No puedes enlazar la conversación contigo mismo'}), 400

        if not target['tipo_tercero'] or target['tipo_tercero'] == 'invitado':
            conn.execute("UPDATE terceros SET tipo_tercero = 'registrado' WHERE id = %s", (target_id,))

        if old_otro_id == target_id:
            conn.execute('UPDATE conversaciones SET nombre_invitado = %s WHERE id = %s',
                         (target['nombre'], conv['id']))
            conn.commit()
            conn.close()
            return jsonify({'ok': True, 'token': token, 'nombre': target['nombre'], 'otro_id': target_id})

        # Verificar si ya existe otra conversación activa entre mi_id_conv y target_id
        conv_existente = conn.execute('''
            SELECT id, token FROM conversaciones
            WHERE id != %s AND activa = TRUE
              AND ((creador_id = %s AND invitado_id = %s) OR (creador_id = %s AND invitado_id = %s))
            ORDER BY id DESC LIMIT 1
        ''', (conv['id'], mi_id_conv, target_id, target_id, mi_id_conv)).fetchone()

        if conv_existente:
            final_conv_id = conv_existente['id']
            final_token = conv_existente['token']
            conn.execute('''
                UPDATE mensajes
                SET conversacion_id = %s,
                    remitente_id = CASE WHEN remitente_id = %s THEN %s ELSE remitente_id END,
                    destinatario_id = CASE WHEN destinatario_id = %s THEN %s ELSE destinatario_id END
                WHERE conversacion_id = %s
            ''', (final_conv_id, old_otro_id, target_id, old_otro_id, target_id, conv['id']))
            try:
                conn.execute('UPDATE apuntes SET token_conv = %s WHERE token_conv = %s',
                             (final_token, token))
            except Exception:
                pass
            conn.execute('DELETE FROM conversaciones WHERE id = %s', (conv['id'],))
        else:
            final_token = token
            if es_creador:
                conn.execute('''
                    UPDATE conversaciones
                    SET invitado_id = %s, nombre_invitado = %s
                    WHERE id = %s
                ''', (target_id, target['nombre'], conv['id']))
            else:
                conn.execute('''
                    UPDATE conversaciones
                    SET creador_id = %s
                    WHERE id = %s
                ''', (target_id, conv['id']))
            conn.execute('''
                UPDATE mensajes
                SET remitente_id = CASE WHEN remitente_id = %s THEN %s ELSE remitente_id END,
                    destinatario_id = CASE WHEN destinatario_id = %s THEN %s ELSE destinatario_id END
                WHERE conversacion_id = %s
            ''', (old_otro_id, target_id, old_otro_id, target_id, conv['id']))

        # Limpiar tercero temporal 'invitado' si quedó huérfano
        otras = conn.execute('''
            SELECT 1 FROM conversaciones
            WHERE creador_id = %s OR invitado_id = %s LIMIT 1
        ''', (old_otro_id, old_otro_id)).fetchone()
        if not otras:
            conn.execute("DELETE FROM terceros WHERE id = %s AND tipo_tercero = 'invitado'", (old_otro_id,))

        conn.commit()
        conn.close()
        return jsonify({
            'ok': True,
            'token': final_token,
            'nombre': target['nombre'],
            'otro_id': target_id
        })
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/chat/resumen-globo', methods=['GET'])
def api_chat_resumen_globo():
    mid = get_chat_tercero_id()
    if not mid:
        return jsonify({'ok': True, 'autenticado': False, 'total_no_leidos': 0})
    try:
        conn = get_db_connection()
        _asegurar_schema_chat(conn)
        row = conn.execute('''
            SELECT COUNT(*) AS total
            FROM mensajes m
            JOIN conversaciones c ON c.id = m.conversacion_id
            WHERE c.activa = TRUE
              AND (c.creador_id = %(mid)s OR c.invitado_id = %(mid)s)
              AND m.remitente_id != %(mid)s
              AND m.estado = 'pendiente'
        ''', {'mid': mid}).fetchone()
        total = int(row['total'] or 0) if row else 0

        ultimo = None
        if total > 0:
            u = conn.execute('''
                SELECT m.id, m.mensaje, m.tipo, c.token, t.nombre AS remitente
                FROM mensajes m
                JOIN conversaciones c ON c.id = m.conversacion_id
                JOIN terceros t ON t.id = m.remitente_id
                WHERE c.activa = TRUE
                  AND (c.creador_id = %(mid)s OR c.invitado_id = %(mid)s)
                  AND m.remitente_id != %(mid)s
                  AND m.estado = 'pendiente'
                ORDER BY m.id DESC LIMIT 1
            ''', {'mid': mid}).fetchone()
            if u:
                ultimo = dict(u)
        conn.close()
        return jsonify({
            'ok': True,
            'autenticado': True,
            'mi_tercero_id': mid,
            'total_no_leidos': total,
            'ultimo': ultimo
        })
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e), 'total_no_leidos': 0})


_GLOBO_CHAT_SNIPPET = """
<!-- ── Globo flotante global de Mensajería TUC TUC ── -->
<style>
  #tuctuc-chat-globo {
    position: fixed;
    bottom: 24px;
    right: 80px;
    z-index: 9450;
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background: linear-gradient(135deg, #c96442, #a84c2c);
    color: #fcf9f3;
    border: none;
    cursor: pointer;
    box-shadow: 0 6px 20px rgba(201, 100, 66, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    font-family: system-ui, -apple-system, sans-serif;
  }
  #tuctuc-chat-globo:hover {
    transform: scale(1.07);
    box-shadow: 0 8px 26px rgba(201, 100, 66, 0.6);
  }
  #tuctuc-chat-badge {
    position: absolute;
    top: -4px;
    right: -4px;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    border-radius: 999px;
    background: #ef4444;
    color: #ffffff;
    font-size: 11px;
    font-weight: 800;
    display: none;
    align-items: center;
    justify-content: center;
    border: 2px solid #ffffff;
    box-shadow: 0 2px 6px rgba(239, 68, 68, 0.5);
    animation: tuctucPulseBadge 1.8s infinite;
  }
  @keyframes tuctucPulseBadge {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.12); }
  }
  #tuctuc-chat-toast {
    position: fixed;
    bottom: 84px;
    right: 16px;
    z-index: 9455;
    max-width: min(300px, calc(100vw - 32px));
    background: #1f1e1b;
    color: #fcf9f3;
    border: 1px solid rgba(201, 100, 66, 0.45);
    border-radius: 14px;
    padding: 10px 14px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.28);
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 13px;
    cursor: pointer;
    display: none;
    box-sizing: border-box;
  }
  #tuctuc-chat-drawer,
  #tuctuc-chat-drawer * {
    box-sizing: border-box;
  }
  #tuctuc-chat-drawer {
    position: fixed;
    bottom: 84px;
    right: 16px;
    width: min(410px, calc(100vw - 32px));
    max-width: calc(100% - 32px);
    height: min(640px, calc(100vh - 104px));
    height: min(640px, calc(100dvh - 104px));
    z-index: 9460;
    background: #f5f1e8;
    border-radius: 18px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.32);
    border: 1px solid rgba(0, 0, 0, 0.12);
    display: none;
    flex-direction: column;
    overflow: hidden;
    font-family: system-ui, -apple-system, sans-serif;
  }
  #tuctuc-chat-drawer.open {
    display: flex;
  }
  .tuctuc-drawer-bar {
    background: #1f1e1b;
    color: #fcf9f3;
    padding: 8px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    flex-shrink: 0;
    width: 100%;
    max-width: 100%;
    min-width: 0;
  }
  .tuctuc-drawer-actions {
    background: #2b2925;
    padding: 6px 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    overflow: hidden;
    flex-shrink: 0;
  }
  .tuctuc-ctx-btn {
    flex: 1;
    min-width: 0;
    border: 1px solid rgba(252, 249, 243, 0.2);
    background: rgba(255, 255, 255, 0.08);
    color: #fcf9f3;
    font-size: 11.5px;
    font-weight: 600;
    padding: 5px 8px;
    border-radius: 999px;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: center;
    transition: background 0.15s;
  }
  .tuctuc-ctx-btn:hover {
    background: #c96442;
    border-color: #c96442;
  }
  @media (max-width: 640px) {
    #tuctuc-chat-globo { right: 74px; bottom: 18px; width: 46px; height: 46px; }
    #tuctuc-chat-drawer {
      left: 8px;
      right: 8px;
      bottom: 70px;
      width: calc(100vw - 16px);
      max-width: calc(100% - 16px);
      height: calc(100vh - 84px);
      height: calc(100dvh - 84px);
      border-radius: 16px;
    }
  }
</style>

<button id="tuctuc-chat-globo" onclick="tuctucToggleChatDrawer()" title="Mensajería y soporte TUC TUC">
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
  </svg>
  <span id="tuctuc-chat-badge">0</span>
</button>

<div id="tuctuc-chat-toast" onclick="tuctucAbrirConversacionToast()"></div>

<div id="tuctuc-chat-drawer">
  <div class="tuctuc-drawer-bar">
    <div style="display:flex;align-items:center;gap:8px;font-size:13.5px;font-weight:700;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
      <span>💬 MiniChat TUC TUC</span>
    </div>
    <div style="display:flex;align-items:center;gap:6px;flex-shrink:0">
      <button onclick="window.open('/chat2','_blank')" title="Abrir en pantalla completa"
              style="background:transparent;border:none;color:#fcf9f3;cursor:pointer;font-size:14px;padding:4px 6px">↗</button>
      <button onclick="tuctucToggleChatDrawer(false)" title="Cerrar"
              style="background:transparent;border:none;color:#fcf9f3;cursor:pointer;font-size:16px;padding:4px 6px">✕</button>
    </div>
  </div>
  <div class="tuctuc-drawer-actions">
    <button class="tuctuc-ctx-btn" id="tuctuc-btn-ctx-cancion" style="display:none;background:rgba(201,100,66,0.35);border-color:#c96442" onclick="tuctucCompartirCancionActual()">
      🎵 Compartir
    </button>
    <button class="tuctuc-ctx-btn" id="tuctuc-btn-activar-push" onclick="tuctucActivarPushDesdeGlobo()" style="background:rgba(16,185,129,0.22);border-color:#10b981;color:#10b981;font-weight:700">
      🔔 Activar Alertas
    </button>
    <button class="tuctuc-ctx-btn" id="tuctuc-btn-probar-timbre" onclick="tuctucProbarTimbreDesdeGlobo()" style="background:rgba(232,133,106,0.22);border-color:#e8856a;color:#e8856a;font-weight:700">
      🔊 Probar Timbre
    </button>
    <button class="tuctuc-ctx-btn" onclick="tuctucCompartirContexto('pregunta')">
      ❓ Consultar
    </button>
    <button class="tuctuc-ctx-btn" onclick="tuctucCompartirContexto('reporte')">
      📊 Compartir vista
    </button>
  </div>
  <iframe id="tuctuc-chat-iframe" src="about:blank" style="flex:1;width:100%;max-width:100%;min-width:0;border:none;background:#f5f1e8;display:block"></iframe>
</div>

<script>
(function() {
  if (window._tuctucGloboInit) return;
  window._tuctucGloboInit = true;

  let _ultimoMsgToastId = parseInt(sessionStorage.getItem('tuctuc_last_toast_msg') || '0', 10);
  let _ultimoTokenToast = '';
  let _iframeCargado = false;

  function _ajustarDrawerViewport() {
    const dr = document.getElementById('tuctuc-chat-drawer');
    if (!dr) return;
    const vw = Math.min(
      window.innerWidth || 9999,
      document.documentElement.clientWidth || 9999,
      window.visualViewport ? window.visualViewport.width : 9999
    );
    if (vw <= 640) {
      const w = Math.max(260, vw - 16);
      dr.style.left = '8px';
      dr.style.right = 'auto';
      dr.style.width = w + 'px';
      dr.style.maxWidth = w + 'px';
    } else {
      dr.style.left = '';
      dr.style.right = '16px';
      dr.style.width = Math.min(410, vw - 32) + 'px';
      dr.style.maxWidth = (vw - 32) + 'px';
    }
  }

  function _detectarContextoRockola() {
    const isRockola = window.location.hostname === 'rockola.tuc-tuc.co' ||
                      window.location.pathname.includes('/rockola') ||
                      typeof window.SALA !== 'undefined';
    const btnCancion = document.getElementById('tuctuc-btn-ctx-cancion');
    if (btnCancion) {
      btnCancion.style.display = isRockola ? 'inline-block' : 'none';
    }
  }

  window.addEventListener('resize', _ajustarDrawerViewport);
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', _ajustarDrawerViewport);
  }

  // Si no hay botón de inspector de ayuda, acercar el globo al borde derecho
  window.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('btn-ayuda-inspector')) {
      const g = document.getElementById('tuctuc-chat-globo');
      if (g) g.style.right = '18px';
    }
    _ajustarDrawerViewport();
    _detectarContextoRockola();
  });

  function _cargarIframe(url) {
    const ifr = document.getElementById('tuctuc-chat-iframe');
    if (!ifr) return;
    ifr.src = url;
    _iframeCargado = true;
  }

  // ── Audio de notificación potente ──────────────────────────
  let _audioGloboCtx = null;
  function _globoCtx() {
    if (!_audioGloboCtx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) _audioGloboCtx = new AC();
    }
    return _audioGloboCtx;
  }

  function _despertarAudio() {
    const c = _globoCtx();
    if (c && c.state === 'suspended') {
      c.resume().catch(() => {});
    }
  }
  ['click', 'touchstart', 'keydown'].forEach(ev => {
    window.addEventListener(ev, _despertarAudio, { once: true, passive: true });
  });

  function _tocarChimeFuerte() {
    try {
      if (localStorage.getItem('chat_sonido_habilitado') === 'false') return;
      const c = _globoCtx();
      if (!c) return;
      if (c.state === 'suspended') {
        c.resume().then(() => _emitirChime(c)).catch(() => {});
      } else {
        _emitirChime(c);
      }
      if ('vibrate' in navigator) {
        try { navigator.vibrate([200, 100, 200]); } catch (e) {}
      }
    } catch(e) {}
  }

  function _emitirChime(ctx) {
    try {
      const t0 = ctx.currentTime;
      const notas = [
        { f: 880, start: 0, dur: 0.16, vol: 0.70, type: 'triangle' },
        { f: 1320, start: 0.12, dur: 0.28, vol: 0.80, type: 'triangle' }
      ];
      notas.forEach(n => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = n.type;
        osc.frequency.setValueAtTime(n.f, t0 + n.start);
        gain.gain.setValueAtTime(0.001, t0 + n.start);
        gain.gain.linearRampToValueAtTime(n.vol, t0 + n.start + 0.015);
        gain.gain.linearRampToValueAtTime(0.0001, t0 + n.start + n.dur);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(t0 + n.start);
        osc.stop(t0 + n.start + n.dur + 0.05);
        setTimeout(() => {
          try { osc.stop(); } catch(e) {}
          try { osc.disconnect(); gain.disconnect(); } catch(e) {}
        }, (n.start + n.dur + 0.1) * 1000);
      });
    } catch(e) {
      console.warn('emitirChime error', e);
    }
  }

  window.tuctucToggleChatDrawer = function(forzar) {
    const dr = document.getElementById('tuctuc-chat-drawer');
    const toast = document.getElementById('tuctuc-chat-toast');
    if (toast) toast.style.display = 'none';
    if (!dr) return;
    _despertarAudio();
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {});
    }
    _ajustarDrawerViewport();
    _detectarContextoRockola();
    const abrir = typeof forzar === 'boolean' ? forzar : !dr.classList.contains('open');
    dr.classList.toggle('open', abrir);
    if (abrir && !_iframeCargado) {
      _cargarIframe('/chat2?embed=1');
    }
  };

  window.tuctucCompartirContexto = function(modo, extraData) {
    const dr = document.getElementById('tuctuc-chat-drawer');
    _ajustarDrawerViewport();
    _detectarContextoRockola();
    if (dr && !dr.classList.contains('open')) dr.classList.add('open');
    const urlActual = window.location.href;
    const titulo = (document.title || window.location.pathname).replace('— TUC TUC', '').trim();
    let targetUrl = '/chat2?embed=1&share_mode=' + encodeURIComponent(modo)
      + '&share_url=' + encodeURIComponent(urlActual)
      + '&share_title=' + encodeURIComponent(titulo);
    if (extraData && typeof extraData === 'object') {
      if (extraData.cancion) targetUrl += '&share_cancion=' + encodeURIComponent(extraData.cancion);
      if (extraData.artista) targetUrl += '&share_artista=' + encodeURIComponent(extraData.artista);
      if (extraData.sala) targetUrl += '&share_sala=' + encodeURIComponent(extraData.sala);
    }
    _cargarIframe(targetUrl);
  };

  window.tuctucCompartirCancionActual = function() {
    let titulo = '';
    let artista = '';
    if (typeof window.cancionActualGlobal === 'object' && window.cancionActualGlobal?.nombre) {
      titulo = window.cancionActualGlobal.nombre.replace(/\.[^.]+$/, '');
      artista = window.cancionActualGlobal.owner || '';
    } else {
      const titEl = document.getElementById('np-titulo-texto') || document.getElementById('sonando');
      if (titEl && titEl.textContent && !titEl.textContent.includes('Cargando') && !titEl.textContent.includes('Esperando')) {
        titulo = titEl.textContent.trim();
      }
      const autEl = document.getElementById('np-autor-texto');
      if (autEl) artista = autEl.textContent.trim();
    }
    const sala = typeof window.SALA !== 'undefined' ? window.SALA : '';
    window.tuctucCompartirContexto('cancion', {
      cancion: titulo || ('Música en Sala ' + (sala ? '#' + sala : 'Rockola')),
      artista: artista,
      sala: sala
    });
  };

  async function _obtenerSWReg() {
    if (!('serviceWorker' in navigator)) return null;
    let r = await navigator.serviceWorker.getRegistration('/sw.js');
    if (!r) r = await navigator.serviceWorker.getRegistration();
    if (!r) r = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    if (r.active) return r;
    return new Promise(res => {
      const t = setTimeout(() => res(r), 3000);
      navigator.serviceWorker.ready.then(rr => { clearTimeout(t); res(rr); }).catch(() => { clearTimeout(t); res(r); });
    });
  }

  window.tuctucActivarPushDesdeGlobo = async function() {
    _despertarAudio();
    _tocarChimeFuerte();
    const btn = document.getElementById('tuctuc-btn-activar-push');
    if (btn) btn.textContent = '⏳ Activando...';
    try {
      if ('Notification' in window) {
        const perm = await Notification.requestPermission();
        if (perm === 'granted' && 'serviceWorker' in navigator) {
          localStorage.setItem('chat_sonido_habilitado', 'true');
          const reg = await _obtenerSWReg();
          const rKey = await fetch('/api/chat/vapid-public-key');
          const dKey = await rKey.json();
          if (dKey.ok && dKey.public_key && reg) {
            const padding = '='.repeat((4 - dKey.public_key.length % 4) % 4);
            const base64 = (dKey.public_key + padding).replace(/-/g, '+').replace(/_/g, '/');
            const rawData = window.atob(base64);
            const outputArray = new Uint8Array(rawData.length);
            for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
            let sub = await reg.pushManager.getSubscription();
            if (sub) {
              try { await sub.unsubscribe(); } catch(eUnsub) {}
              sub = null;
            }
            try {
              sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: outputArray });
            } catch(subErr) {
              console.warn('Push subscribe error en globo:', subErr);
              if (btn) {
                btn.textContent = '✓ Alertas y Timbre OK';
                btn.style.background = '#10b981';
                btn.style.borderColor = '#10b981';
                btn.style.color = '#ffffff';
              }
              alert(`✓ Sonido y avisos en pantalla activados correctamente.\n\nNota: Para app cerrada tu navegador bloqueó Google FCM. Si usas Brave activa "Google services for push messaging" en brave://settings/privacy.`);
              return;
            }
            await fetch('/api/chat/push/suscribir', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ subscription: sub })
            });
            if (btn) {
              btn.textContent = '✓ Alertas Push OK';
              btn.style.background = '#10b981';
              btn.style.borderColor = '#10b981';
              btn.style.color = '#ffffff';
            }
            alert('✓ Alertas Web Push y timbre activados correctamente en este dispositivo.');
            return;
          }
        }
      }
      if (btn) btn.textContent = '🔔 Activar Alertas';
      const ifr = document.getElementById('tuctuc-chat-iframe');
      if (ifr && ifr.contentWindow) {
        ifr.contentWindow.postMessage({ type: 'tuctuc_abrir_perfil' }, '*');
      }
    } catch(e) {
      console.warn('tuctucActivarPushDesdeGlobo error', e);
      if (btn) btn.textContent = '🔔 Activar Alertas';
      alert('Aviso: ' + (e.message || e));
    }
  };

  window.tuctucProbarTimbreDesdeGlobo = async function() {
    _despertarAudio();
    _tocarChimeFuerte();
    try {
      await fetch('/api/chat/push/test', { method: 'POST' });
    } catch(e) {}
  };

  window.tuctucAbrirConversacionToast = function() {
    const toast = document.getElementById('tuctuc-chat-toast');
    if (toast) toast.style.display = 'none';
    const dr = document.getElementById('tuctuc-chat-drawer');
    if (dr) dr.classList.add('open');
    _cargarIframe('/chat2?embed=1' + (_ultimoTokenToast ? '&open_token=' + encodeURIComponent(_ultimoTokenToast) : ''));
  };

  async function _pollGlobo() {
    try {
      const r = await fetch('/api/chat/resumen-globo');
      if (!r.ok) return;
      const d = await r.json();
      if (!d || !d.ok) return;
      const badge = document.getElementById('tuctuc-chat-badge');
      const total = Number(d.total_no_leidos || 0);
      if (badge) {
        if (total > 0) {
          badge.style.display = 'flex';
          badge.textContent = total > 99 ? '99+' : String(total);
        } else {
          badge.style.display = 'none';
        }
      }
      if (d.ultimo && d.ultimo.id && d.ultimo.id > _ultimoMsgToastId) {
        _ultimoMsgToastId = d.ultimo.id;
        sessionStorage.setItem('tuctuc_last_toast_msg', String(_ultimoMsgToastId));
        _ultimoTokenToast = d.ultimo.token || '';

        // Tocar sonido fuerte y vibrar
        _tocarChimeFuerte();

        const txt = d.ultimo.tipo === 'audio' ? '🎵 Audio recibido'
                  : d.ultimo.tipo === 'imagen' ? '🖼 Imagen recibida'
                  : d.ultimo.tipo === 'card' ? '📌 ' + (d.ultimo.mensaje || 'Enlace / Reporte')
                  : (d.ultimo.mensaje || 'Nuevo mensaje');

        // Notificación nativa del sistema operativo si la pestaña está en segundo plano o minimizada
        if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
          try {
            new Notification('💬 ' + (d.ultimo.remitente || 'Mensaje de TUC TUC'), {
              body: txt,
              icon: '/static/icons/icon-192.png',
              tag: 'tuctuc-chat-' + d.ultimo.id
            });
          } catch(e) {}
        }

        const dr = document.getElementById('tuctuc-chat-drawer');
        if (!dr || !dr.classList.contains('open')) {
          const toast = document.getElementById('tuctuc-chat-toast');
          if (toast) {
            toast.innerHTML = '<div style="font-weight:700;color:#e8856a;margin-bottom:2px">💬 '
              + String(d.ultimo.remitente || 'Mensaje nuevo').replace(/</g,'&lt;')
              + '</div><div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
              + String(txt).replace(/</g,'&lt;') + '</div>';
            toast.style.display = 'block';
            setTimeout(() => { if (toast) toast.style.display = 'none'; }, 7000);
          }
        }
      }
    } catch (e) {}
  }

  _pollGlobo();
  setInterval(_pollGlobo, 8000);

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
    navigator.serviceWorker.addEventListener('message', ev => {
      if (ev.data && ev.data.type === 'tuctuc_push_recibido') {
        _despertarAudio();
        _tocarChimeFuerte();
        _mostrarToast(ev.data.body || 'Nuevo mensaje en TUC TUC', ev.data.token || '');
      }
      if (ev.data && ev.data.type === 'tuctuc_push_click') {
        if (typeof window.tuctucToggleChatDrawer === 'function') {
          window.tuctucToggleChatDrawer(true);
        }
        if (ev.data.url) {
          const u = ev.data.url;
          _cargarIframe(u + (u.includes('?') ? '&' : '?') + 'embed=1');
        }
      }
    });
  }
})();
</script>
"""


@bp.after_app_request
def _inyectar_globo_chat_global(response):
    try:
        if request.method != 'GET':
            return response
        p = request.path or ''
        if (p.startswith('/api/') or p.startswith('/static/') or
                p.startswith('/chat') or p.startswith('/login') or
                p.startswith('/admin/login') or request.args.get('embed') == '1'):
            return response
        if not (session.get('chat_tercero_id') or session.get('usuario_id')):
            return response
        if response.direct_passthrough:
            return response
        ctype = response.content_type or ''
        if 'text/html' not in ctype.lower():
            return response
        html = response.get_data(as_text=True)
        if '</body>' not in html or 'id="tuctuc-chat-globo"' in html:
            return response
        html = html.replace('</body>', _GLOBO_CHAT_SNIPPET + '\n</body>', 1)
        response.set_data(html)
    except Exception:
        pass
    return response

