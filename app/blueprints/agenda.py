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
        conn.commit()


@bp.route('/agenda')
@admin_required
def agenda():
    _asegurar_tabla()
    with get_db_connection() as conn:
        cur = conn.execute("""
            SELECT id, texto, completado, categoria, orden
            FROM agenda_items
            ORDER BY completado ASC, orden ASC, id ASC
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
    if not texto:
        return jsonify({'ok': False, 'error': 'Texto vacío'})
    with get_db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO agenda_items (texto, categoria) VALUES (%s, %s) RETURNING id",
            (texto, categoria)
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


@bp.route('/agenda/merlin', methods=['POST'])
def merlin_agregar():
    data = request.get_json()
    if data.get('token') != 'merlin-agenda-2026':
        return jsonify({'ok': False, 'error': 'Token inválido'}), 403
    _asegurar_tabla()
    texto = (data.get('texto') or '').strip()
    categoria = (data.get('categoria') or '').strip()
    if not texto:
        return jsonify({'ok': False, 'error': 'Texto vacío'})
    with get_db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO agenda_items (texto, categoria) VALUES (%s, %s) RETURNING id",
            (texto, categoria)
        )
        item_id = cur.fetchone()[0]
        conn.commit()
    return jsonify({'ok': True, 'id': item_id})
