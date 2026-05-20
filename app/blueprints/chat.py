from flask import Blueprint, render_template, request, session, redirect, jsonify
from ..db import get_db_connection

bp = Blueprint('chat_admin', __name__)


def _crear_tabla_chat_mensajes(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_mensajes (
            id         SERIAL PRIMARY KEY,
            rol        VARCHAR(20)  NOT NULL,
            contenido  TEXT         NOT NULL,
            created_at TIMESTAMPTZ  DEFAULT NOW(),
            estado     VARCHAR(20)  DEFAULT 'pendiente',
            archivado  BOOLEAN      DEFAULT FALSE,
            canal      VARCHAR(20)  DEFAULT 'terminal'
        )
    """)
    conn.commit()
    for alter in [
        "ALTER TABLE chat_mensajes ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'pendiente'",
        "ALTER TABLE chat_mensajes ADD COLUMN IF NOT EXISTS archivado BOOLEAN DEFAULT FALSE",
        "ALTER TABLE chat_mensajes ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
        "ALTER TABLE chat_mensajes ADD COLUMN IF NOT EXISTS canal VARCHAR(20) DEFAULT 'terminal'",
    ]:
        try:
            conn.execute(alter)
            conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass


# ── Captura ────────────────────────────────────────────────────────────────

@bp.route('/captura')
def captura_chat():
    if 'usuario_id' not in session:
        return redirect('/login')
    return render_template('captura_chat.html')


@bp.route('/api/captura/historial')
def api_captura_historial():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        since_id = request.args.get('since_id', type=int, default=0)
        conn = get_db_connection()
        _crear_tabla_chat_mensajes(conn)
        if since_id:
            rows = conn.execute("""
                SELECT id, rol, contenido, created_at
                FROM chat_mensajes
                WHERE archivado = FALSE AND id > %s
                  AND (canal = 'captura' OR rol = 'assistant')
                ORDER BY created_at ASC
            """, (since_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT id, rol, contenido, created_at
                FROM chat_mensajes
                WHERE archivado = FALSE
                  AND (canal = 'captura' OR rol = 'assistant')
                ORDER BY created_at ASC
                LIMIT 60
            """).fetchall()
        conn.close()
        return jsonify({'ok': True, 'mensajes': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/captura/mensaje', methods=['POST'])
def api_captura_mensaje():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    texto = (data.get('mensaje') or '').strip()
    if not texto:
        return jsonify({'ok': False, 'error': 'Mensaje vacío'}), 400
    conn = None
    try:
        conn = get_db_connection()
        _crear_tabla_chat_mensajes(conn)
        row = conn.execute(
            "INSERT INTO chat_mensajes (rol, contenido, estado, canal) VALUES (%s, %s, %s, %s) RETURNING id",
            ('user', texto, 'enviado', 'captura')
        ).fetchone()
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'id': row['id']})
    except Exception as e:
        if conn:
            try: conn.rollback(); conn.close()
            except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Admin chat ─────────────────────────────────────────────────────────────

@bp.route('/admin/chat')
def admin_chat():
    if 'usuario_id' not in session:
        return redirect('/login')
    try:
        conn = get_db_connection()
        _crear_tabla_chat_mensajes(conn)
        mensajes = conn.execute(
            "SELECT id, rol, contenido, created_at FROM chat_mensajes WHERE archivado = FALSE ORDER BY id ASC"
        ).fetchall()
        hay_pendientes = conn.execute(
            "SELECT 1 FROM chat_mensajes WHERE estado IN ('pendiente','procesando') AND archivado = FALSE LIMIT 1"
        ).fetchone() is not None
        conn.close()
        return render_template('chat_admin.html', mensajes=mensajes, hay_pendientes=hay_pendientes)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/api/admin/chat', methods=['POST'])
def api_admin_chat():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json()
    contenido = (data.get('mensaje') or '').strip()
    if not contenido:
        return jsonify({'ok': False, 'error': 'Mensaje vacío'}), 400
    try:
        conn = get_db_connection()
        _crear_tabla_chat_mensajes(conn)
        row = conn.execute(
            "INSERT INTO chat_mensajes (rol, contenido, estado) VALUES (%s, %s, 'pendiente') RETURNING id",
            ('user', contenido)
        ).fetchone()
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'id': row['id']})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/chat/ultimo')
def api_admin_chat_ultimo():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT id, rol, contenido FROM chat_mensajes WHERE archivado = FALSE ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return jsonify({'ok': True, 'id': row['id'], 'rol': row['rol'], 'contenido': row['contenido']})
        return jsonify({'ok': True, 'id': 0})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/chat/desde/<int:desde_id>')
def api_admin_chat_desde(desde_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT id, rol, contenido FROM chat_mensajes "
            "WHERE id > %s AND rol = 'assistant' AND archivado = FALSE ORDER BY id ASC LIMIT 1",
            (desde_id,)
        ).fetchone()
        hay_procesando = conn.execute(
            "SELECT 1 FROM chat_mensajes WHERE estado = 'procesando' AND archivado = FALSE LIMIT 1"
        ).fetchone() is not None
        conn.close()
        if row:
            return jsonify({'ok': True, 'encontrado': True, 'id': row['id'],
                            'contenido': row['contenido'], 'procesando': hay_procesando})
        return jsonify({'ok': True, 'encontrado': False, 'procesando': hay_procesando})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/chat/responder', methods=['POST'])
def api_admin_chat_responder():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json()
    contenido = (data.get('contenido') or '').strip()
    if not contenido:
        return jsonify({'ok': False, 'error': 'Contenido vacío'}), 400
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO chat_mensajes (rol, contenido) VALUES (%s, %s)",
            ('assistant', contenido)
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/chat/limpiar', methods=['POST'])
def api_admin_chat_limpiar():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        result = conn.execute(
            "UPDATE chat_mensajes SET archivado = TRUE WHERE archivado = FALSE RETURNING id"
        ).fetchall()
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'archivados': len(result)})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/chat/historial')
def api_admin_chat_historial():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        mensajes = conn.execute(
            "SELECT id, rol, contenido, created_at FROM chat_mensajes ORDER BY id ASC"
        ).fetchall()
        conn.close()
        return jsonify({'ok': True, 'mensajes': [dict(m) for m in mensajes]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/admin/chat/historico')
def admin_chat_historico():
    if 'usuario_id' not in session:
        return redirect('/login')
    return render_template('chat_historico.html')


@bp.route('/api/admin/chat/historico-data')
def api_admin_chat_historico_data():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    buscar  = (request.args.get('q') or '').strip()
    pagina  = max(1, int(request.args.get('p') or 1))
    por_pag = 50
    offset  = (pagina - 1) * por_pag
    try:
        conn = get_db_connection()
        if buscar:
            total = conn.execute(
                "SELECT COUNT(*) FROM chat_mensajes WHERE archivado = TRUE AND contenido ILIKE %s",
                (f'%{buscar}%',)
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT id, rol, contenido, created_at FROM chat_mensajes "
                "WHERE archivado = TRUE AND contenido ILIKE %s "
                "ORDER BY id DESC LIMIT %s OFFSET %s",
                (f'%{buscar}%', por_pag, offset)
            ).fetchall()
        else:
            total = conn.execute(
                "SELECT COUNT(*) FROM chat_mensajes WHERE archivado = TRUE"
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT id, rol, contenido, created_at FROM chat_mensajes "
                "WHERE archivado = TRUE ORDER BY id DESC LIMIT %s OFFSET %s",
                (por_pag, offset)
            ).fetchall()
        conn.close()
        mensajes = [{
            'id':         r['id'],
            'rol':        r['rol'],
            'contenido':  r['contenido'],
            'created_at': r['created_at'].isoformat() if r['created_at'] else '',
        } for r in rows]
        return jsonify({
            'ok':      True,
            'mensajes': mensajes,
            'total':    total,
            'paginas':  -(-total // por_pag),
            'pagina':   pagina,
        })
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
