import os

from flask import Blueprint, render_template, request, jsonify
from ..db import get_db_connection
from .auth import admin_required

bp = Blueprint('agenda', __name__)


def _asegurar_tabla():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agenda_items (
                id SERIAL PRIMARY KEY,
                texto TEXT NOT NULL,
                completado BOOLEAN DEFAULT FALSE,
                categoria TEXT DEFAULT '',
                orden INT DEFAULT 0,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("ALTER TABLE agenda_items ADD COLUMN fecha_limite TIMESTAMP")
        except Exception:
            pass
        conn.commit()


@bp.route('/agenda')
@admin_required
def agenda():
    _asegurar_tabla()
    with get_db_connection() as conn:
        cur = conn.execute("""
            SELECT id, texto, completado, categoria, orden, fecha_limite
            FROM agenda_items
            ORDER BY completado ASC,
                     CASE WHEN fecha_limite IS NOT NULL THEN 0 ELSE 1 END ASC,
                     fecha_limite ASC NULLS LAST,
                     orden ASC, id ASC
        """)
        items = cur.fetchall()
    return render_template('agenda.html', items=items)


@bp.route('/agenda/item', methods=['POST'])
@admin_required
def agregar_item():
    _asegurar_tabla()
    data = request.get_json()
    texto = (data.get('texto') or '').strip()
    categoria = (data.get('categoria') or '').strip()
    fecha_limite = (data.get('fecha_limite') or '').strip() or None
    if not texto:
        return jsonify({'ok': False, 'error': 'Texto vacío'})
    with get_db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO agenda_items (texto, categoria, fecha_limite) VALUES (%s, %s, %s) RETURNING id",
            (texto, categoria, fecha_limite)
        )
        item_id = cur.fetchone()[0]
        conn.commit()
    return jsonify({'ok': True, 'id': item_id})


@bp.route('/agenda/item/<int:item_id>/toggle', methods=['POST'])
@admin_required
def toggle_item(item_id):
    with get_db_connection() as conn:
        cur = conn.execute(
            "UPDATE agenda_items SET completado = NOT completado WHERE id = %s RETURNING completado",
            (item_id,)
        )
        row = cur.fetchone()
        conn.commit()
    if not row:
        return jsonify({'ok': False, 'error': 'No encontrado'})
    return jsonify({'ok': True, 'completado': row['completado']})


@bp.route('/agenda/item/<int:item_id>', methods=['DELETE'])
@admin_required
def eliminar_item(item_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM agenda_items WHERE id = %s", (item_id,))
        conn.commit()
    return jsonify({'ok': True})


@bp.route('/agenda/item/<int:item_id>/edit', methods=['POST'])
@admin_required
def editar_item(item_id):
    data = request.get_json() or {}
    texto = (data.get('texto') or '').strip()
    categoria = (data.get('categoria') or '').strip()
    fecha_limite = (data.get('fecha_limite') or '').strip() or None
    
    if not texto:
        return jsonify({'ok': False, 'error': 'El texto de la tarea no puede estar vacío'})
        
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE agenda_items SET texto = %s, categoria = %s, fecha_limite = %s WHERE id = %s",
            (texto, categoria, fecha_limite, item_id)
        )
        conn.commit()
    return jsonify({'ok': True})


@bp.route('/agenda/merlin', methods=['GET', 'POST'])
def merlin_agenda():
    token = request.args.get('token') or (request.get_json(silent=True) or {}).get('token')
    if token != os.environ.get('AGENDA_MERLIN_TOKEN', 'merlin-agenda-2026'):
        return jsonify({'ok': False, 'error': 'Token inválido'}), 403

    if request.method == 'GET':
        with get_db_connection() as conn:
            cur = conn.execute("""
                SELECT id, texto, completado, fecha_limite
                FROM agenda_items
                ORDER BY completado ASC,
                         CASE WHEN fecha_limite IS NOT NULL THEN 0 ELSE 1 END ASC,
                         fecha_limite ASC NULLS LAST, id ASC
            """)
            rows = cur.fetchall()
        items = [{'id': r[0], 'texto': r[1], 'completado': r[2],
                  'fecha_limite': r[3].isoformat() if r[3] else None} for r in rows]
        return jsonify({'ok': True, 'items': items})

    _asegurar_tabla()
    data = request.get_json(silent=True) or {}
    accion = (data.get('accion') or 'agregar').strip().lower()

    if accion in ('completar', 'reabrir'):
        try:
            item_id = int(data.get('id'))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'ID inválido'}), 400

        completado = accion == 'completar'
        with get_db_connection() as conn:
            cur = conn.execute(
                """UPDATE agenda_items
                   SET completado = %s
                   WHERE id = %s
                   RETURNING id, completado""",
                (completado, item_id)
            )
            row = cur.fetchone()
            conn.commit()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        return jsonify({
            'ok': True,
            'id': row['id'],
            'completado': row['completado'],
        })

    if accion != 'agregar':
        return jsonify({'ok': False, 'error': 'Acción no válida'}), 400

    texto = (data.get('texto') or '').strip()
    categoria = (data.get('categoria') or '').strip()
    fecha_limite = (data.get('fecha_limite') or '').strip() or None
    if not texto:
        return jsonify({'ok': False, 'error': 'Texto vacío'})
    with get_db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO agenda_items (texto, categoria, fecha_limite) VALUES (%s, %s, %s) RETURNING id",
            (texto, categoria, fecha_limite)
        )
        item_id = cur.fetchone()[0]
        conn.commit()
    return jsonify({'ok': True, 'id': item_id})


@bp.route('/agenda/reordenar', methods=['POST'])
@admin_required
def reordenar_agenda():
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids or not isinstance(ids, list):
        return jsonify({'ok': False, 'error': 'Lista de IDs inválida'})
    
    with get_db_connection() as conn:
        for idx, item_id in enumerate(ids):
            conn.execute(
                "UPDATE agenda_items SET orden = %s WHERE id = %s",
                (idx, item_id)
            )
        conn.commit()
    return jsonify({'ok': True})


@bp.route('/agenda/item/<int:item_id>/activar', methods=['POST'])
@admin_required
def activar_item_agenda(item_id):
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT texto, categoria FROM agenda_items WHERE id = %s",
            (item_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'Tarea no encontrada'})
        
        texto = row['texto']
        categoria = row['categoria']
        contenido = f"[Requerimiento #{item_id}] {texto} ({categoria})"
        
        conn.execute(
            "INSERT INTO chat_mensajes (rol, contenido, canal, archivado) VALUES ('user', %s, 'captura', FALSE)",
            (contenido,)
        )
        conn.commit()
    return jsonify({'ok': True})


@bp.route('/agenda/item/activar-multi', methods=['POST'])
@admin_required
def activar_multi_agenda():
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids or not isinstance(ids, list):
        return jsonify({'ok': False, 'error': 'Lista de IDs inválida'})
    
    with get_db_connection() as conn:
        placeholders = ', '.join(['%s'] * len(ids))
        cur = conn.execute(
            f"SELECT id, texto, categoria FROM agenda_items WHERE id IN ({placeholders})",
            tuple(ids)
        )
        rows = cur.fetchall()
        if not rows:
            return jsonify({'ok': False, 'error': 'Tareas no encontradas'})
        
        # Build consolidated message
        lines = []
        for row in rows:
            lines.append(f"- [Requerimiento #{row['id']}] {row['texto']} ({row['categoria']})")
        
        contenido = "Activar tareas agrupadas:\n" + "\n".join(lines)
        
        conn.execute(
            "INSERT INTO chat_mensajes (rol, contenido, canal, archivado) VALUES ('user', %s, 'captura', FALSE)",
            (contenido,)
        )
        conn.commit()
    return jsonify({'ok': True})

