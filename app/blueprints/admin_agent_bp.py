import json
import secrets
from datetime import datetime, timezone

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from ..db import get_db_connection
from .auth import admin_required, solo_admin

bp = Blueprint('admin_agent', __name__)

_tablas_listas = False


def _crear_tablas(conn):
    global _tablas_listas
    if _tablas_listas:
        return
    sqls = [
        """CREATE TABLE IF NOT EXISTS admin_agent_sesiones (
            id SERIAL PRIMARY KEY,
            cliente_id VARCHAR(100) NOT NULL,
            token VARCHAR(100) NOT NULL UNIQUE,
            activo BOOLEAN DEFAULT TRUE,
            nombre VARCHAR(200),
            ip_local VARCHAR(50),
            ruta_bd VARCHAR(500),
            ultimo_ping TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS admin_agent_consultas (
            id SERIAL PRIMARY KEY,
            sesion_id INTEGER REFERENCES admin_agent_sesiones(id),
            tipo VARCHAR(50) NOT NULL,
            parametros JSONB DEFAULT '{}',
            respuesta JSONB,
            estado VARCHAR(20) DEFAULT 'pendiente',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            respondida_at TIMESTAMPTZ
        )""",
        """CREATE TABLE IF NOT EXISTS admin_agent_permisos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            cliente_id VARCHAR(100) NOT NULL,
            UNIQUE(usuario_id, cliente_id)
        )""",
        """CREATE TABLE IF NOT EXISTS admin_agent_reportes (
            id SERIAL PRIMARY KEY,
            cliente_id VARCHAR(100),
            tipo VARCHAR(50),
            estado VARCHAR(20),
            detalle TEXT,
            ip VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ]
    for sql in sqls:
        conn.execute(sql)
    conn.commit()
    for alter in [
        'ALTER TABLE admin_agent_sesiones ADD COLUMN IF NOT EXISTS nombre VARCHAR(200)',
        'ALTER TABLE admin_agent_sesiones ADD COLUMN IF NOT EXISTS ip_local VARCHAR(50)',
        'ALTER TABLE admin_agent_sesiones ADD COLUMN IF NOT EXISTS ruta_bd VARCHAR(500)',
    ]:
        try:
            conn.execute(alter)
            conn.commit()
        except Exception:
            pass
    _tablas_listas = True


def _puede_ver(usuario_id, rol, cliente_id, conn):
    if rol == 'Administrador':
        return True
    row = conn.execute(
        "SELECT 1 FROM admin_agent_permisos WHERE usuario_id=%s AND cliente_id=%s",
        (usuario_id, cliente_id)
    ).fetchone()
    return bool(row)


# ── API agente (llamada desde admin_agent.py en PC cliente) ───────────────────

@bp.route('/api/admin-agent/checkin', methods=['POST'])
def checkin():
    data = request.get_json() or {}
    cliente_id = data.get('cliente_id', '').strip()
    if not cliente_id:
        return jsonify({'ok': False, 'error': 'cliente_id requerido'}), 400
    nombre   = (data.get('nombre') or cliente_id).strip()
    ip_local = (data.get('ip_local') or '').strip()
    ruta_bd  = (data.get('ruta_bd') or '').strip()
    token    = secrets.token_hex(24)
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        conn.execute("UPDATE admin_agent_sesiones SET activo=FALSE WHERE cliente_id=%s", (cliente_id,))
        conn.execute(
            "INSERT INTO admin_agent_sesiones (cliente_id, token, nombre, ip_local, ruta_bd) VALUES (%s,%s,%s,%s,%s)",
            (cliente_id, token, nombre, ip_local, ruta_bd)
        )
        conn.commit()
        return jsonify({'ok': True, 'token': token})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/reporte', methods=['POST'])
def reporte():
    """Recibe reportes de instalación y arranque desde PCs clientes."""
    data = request.get_json() or {}
    cliente_id = data.get('cliente_id', '')
    tipo       = data.get('tipo', '')
    estado     = data.get('estado', '')
    detalle    = data.get('detalle', '')
    ip         = data.get('ip', '')
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        conn.execute(
            "INSERT INTO admin_agent_reportes (cliente_id, tipo, estado, detalle, ip) VALUES (%s,%s,%s,%s,%s)",
            (cliente_id, tipo, estado, detalle, ip)
        )
        # Notificar a Merlin via chat_mensajes canal='captura':
        # - instalacion: siempre (primera vez es crítico saberlo)
        # - arranque_*: solo si hay error (arranques ok son rutinarios)
        _notificar = tipo == 'instalacion' or (tipo.startswith('arranque') and estado != 'ok')
        if _notificar:
            resumen_detalle = detalle[-1500:] if len(detalle) > 1500 else detalle
            texto = (
                f"[REPORTE {cliente_id.upper()}] tipo={tipo} estado={estado} ip={ip}\n"
                f"{resumen_detalle}"
            )
            try:
                conn.execute(
                    "INSERT INTO chat_mensajes (rol, contenido, canal) VALUES ('user',%s,'captura')",
                    (texto,)
                )
            except Exception:
                pass  # Si chat_mensajes no existe en este entorno, no bloquear
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/reportes', methods=['GET'])
@admin_required
def ver_reportes():
    """Lista los últimos reportes para que Merlin pueda consultarlos."""
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        rows = conn.execute(
            "SELECT cliente_id, tipo, estado, detalle, ip, created_at FROM admin_agent_reportes ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        return jsonify({'ok': True, 'reportes': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/checkout', methods=['POST'])
def checkout():
    token = (request.get_json() or {}).get('token', '')
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        conn.execute("UPDATE admin_agent_sesiones SET activo=FALSE WHERE token=%s", (token,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/ping', methods=['POST'])
def ping():
    data    = request.get_json() or {}
    token   = data.get('token', '')
    ruta_bd = (data.get('ruta_bd') or '').strip() or None
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        sesion = conn.execute(
            "UPDATE admin_agent_sesiones SET ultimo_ping=NOW(), ruta_bd=COALESCE(%s,ruta_bd) "
            "WHERE token=%s AND activo=TRUE RETURNING id",
            (ruta_bd, token)
        ).fetchone()
        if not sesion:
            return jsonify({'ok': False, 'error': 'sesión inválida'}), 401
        consulta = conn.execute(
            "SELECT id, tipo, parametros FROM admin_agent_consultas "
            "WHERE sesion_id=%s AND estado='pendiente' ORDER BY id ASC LIMIT 1",
            (sesion['id'],)
        ).fetchone()
        if consulta:
            conn.execute("UPDATE admin_agent_consultas SET estado='procesando' WHERE id=%s", (consulta['id'],))
            conn.commit()
            return jsonify({'ok': True, 'consulta': {
                'id': consulta['id'],
                'tipo': consulta['tipo'],
                'parametros': consulta['parametros'],
            }})
        conn.commit()
        return jsonify({'ok': True, 'consulta': None})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/respuesta', methods=['POST'])
def respuesta():
    data = request.get_json() or {}
    token       = data.get('token', '')
    consulta_id = data.get('consulta_id')
    resp_data   = data.get('respuesta')
    error       = data.get('error')
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        sesion = conn.execute(
            "SELECT id FROM admin_agent_sesiones WHERE token=%s AND activo=TRUE", (token,)
        ).fetchone()
        if not sesion:
            return jsonify({'ok': False, 'error': 'sesión inválida'}), 401
        payload = json.dumps(resp_data if resp_data is not None else {'error': error})
        estado  = 'error' if error else 'lista'
        conn.execute(
            "UPDATE admin_agent_consultas SET respuesta=%s, estado=%s, respondida_at=NOW() "
            "WHERE id=%s AND sesion_id=%s",
            (payload, estado, consulta_id, sesion['id'])
        )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── API browser ───────────────────────────────────────────────────────────────

@bp.route('/api/admin-agent/consultar', methods=['POST'])
def consultar():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data       = request.get_json() or {}
    cliente_id = data.get('cliente_id', '').strip()
    tipo       = data.get('tipo', '').strip()
    parametros = data.get('parametros', {})
    if not cliente_id or not tipo:
        return jsonify({'ok': False, 'error': 'cliente_id y tipo requeridos'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        if not _puede_ver(session['usuario_id'], session.get('rol', ''), cliente_id, conn):
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        sesion = conn.execute(
            "SELECT id FROM admin_agent_sesiones WHERE cliente_id=%s AND activo=TRUE ORDER BY id DESC LIMIT 1",
            (cliente_id,)
        ).fetchone()
        if not sesion:
            return jsonify({'ok': False, 'error': 'Agente no conectado'}), 404
        row = conn.execute(
            "INSERT INTO admin_agent_consultas (sesion_id, tipo, parametros) VALUES (%s,%s,%s) RETURNING id",
            (sesion['id'], tipo, json.dumps(parametros))
        ).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'consulta_id': row['id']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/resultado/<int:consulta_id>', methods=['GET'])
def resultado(consulta_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        row = conn.execute(
            "SELECT estado, respuesta FROM admin_agent_consultas WHERE id=%s", (consulta_id,)
        ).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrada'}), 404
        resp = {'ok': True, 'estado': row['estado'], 'respuesta': row['respuesta']}
        if row['estado'] in ('lista', 'error'):
            try:
                conn.execute("DELETE FROM admin_agent_consultas WHERE id=%s", (consulta_id,))
                conn.commit()
            except Exception:
                pass
        return jsonify(resp)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/estado/<cliente_id>', methods=['GET'])
def estado(cliente_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        if not _puede_ver(session['usuario_id'], session.get('rol', ''), cliente_id, conn):
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        sesion = conn.execute(
            "SELECT ultimo_ping FROM admin_agent_sesiones "
            "WHERE cliente_id=%s AND activo=TRUE ORDER BY id DESC LIMIT 1",
            (cliente_id,)
        ).fetchone()
        if not sesion:
            return jsonify({'ok': True, 'conectado': False})
        ping = sesion['ultimo_ping']
        if ping.tzinfo is None:
            ping = ping.replace(tzinfo=timezone.utc)
        lag = (datetime.now(timezone.utc) - ping).total_seconds()
        return jsonify({'ok': True, 'conectado': lag < 30})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/agentes', methods=['GET'])
def agentes():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        if session.get('rol') == 'Administrador':
            rows = conn.execute("""
                SELECT DISTINCT ON (cliente_id)
                    cliente_id, nombre, ip_local, ruta_bd, activo, ultimo_ping
                FROM admin_agent_sesiones
                ORDER BY cliente_id, id DESC
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT DISTINCT ON (s.cliente_id)
                    s.cliente_id, s.nombre, s.ip_local, s.ruta_bd, s.activo, s.ultimo_ping
                FROM admin_agent_sesiones s
                JOIN admin_agent_permisos p ON p.cliente_id = s.cliente_id
                WHERE p.usuario_id = %s
                ORDER BY s.cliente_id, s.id DESC
            """, (session['usuario_id'],)).fetchall()
        now = datetime.now(timezone.utc)
        result = []
        for r in rows:
            ping = r['ultimo_ping']
            if ping and ping.tzinfo is None:
                ping = ping.replace(tzinfo=timezone.utc)
            lag = int((now - ping).total_seconds()) if ping else 9999
            result.append({
                'cliente_id': r['cliente_id'],
                'nombre':     r['nombre'] or r['cliente_id'],
                'ip_local':   r['ip_local'] or '',
                'ruta_bd':    r['ruta_bd'] or '',
                'conectado':  bool(r['activo']) and lag < 30,
                'lag':        lag,
            })
        return jsonify({'ok': True, 'agentes': result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/permisos/usuario/<int:uid>', methods=['GET'])
@solo_admin
def permisos_get(uid):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        rows = conn.execute(
            "SELECT cliente_id FROM admin_agent_permisos WHERE usuario_id=%s ORDER BY cliente_id", (uid,)
        ).fetchall()
        return jsonify({'ok': True, 'clientes': [r['cliente_id'] for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin-agent/permisos/usuario/<int:uid>', methods=['POST'])
@solo_admin
def permisos_set(uid):
    clientes = (request.get_json() or {}).get('clientes', [])
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        conn.execute("DELETE FROM admin_agent_permisos WHERE usuario_id=%s", (uid,))
        for cid in clientes:
            conn.execute(
                "INSERT INTO admin_agent_permisos (usuario_id, cliente_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (uid, cid.strip())
            )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Páginas HTML ──────────────────────────────────────────────────────────────

@bp.route('/admin/agentes')
@solo_admin
def agentes_page():
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        rows = conn.execute(
            "SELECT id, nombre, usuario FROM usuarios WHERE rol='ClienteVFP' ORDER BY nombre"
        ).fetchall()
        usuarios = [{'id': r['id'], 'nombre': r['nombre'], 'usuario': r['usuario']} for r in rows]
        return render_template('admin_agentes.html', usuarios=usuarios)
    except Exception as e:
        return str(e), 500
    finally:
        conn.close()


@bp.route('/admin/consultas')
@admin_required
def consultas_page():
    return render_template('admin_consultas.html')
