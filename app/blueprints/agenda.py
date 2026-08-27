import os

from flask import Blueprint, render_template, request, jsonify, send_from_directory, url_for, redirect
from ..db import get_db_connection
from .auth import admin_required

bp = Blueprint('agenda', __name__)

_AGENDA_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agenda_imagenes')
os.makedirs(_AGENDA_IMG_DIR, exist_ok=True)

_OCR_BIN = None
for _candidate in ('/usr/bin/tesseract', r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
    if os.path.exists(_candidate):
        _OCR_BIN = _candidate
        break


def _ocr_imagen(ruta):
    """Extrae texto de una imagen con tesseract local (servidor o PC)."""
    if not _OCR_BIN:
        return None
    import subprocess
    try:
        r = subprocess.run(
            [_OCR_BIN, ruta, 'stdout', '-l', 'spa+eng', '--psm', '6'],
            capture_output=True, timeout=60
        )
        texto = r.stdout.decode('utf-8', 'replace').strip()
        return texto or None
    except Exception:
        return None


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
        try:
            conn.execute("ALTER TABLE agenda_items ADD COLUMN fecha_limite TIMESTAMP")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute("ALTER TABLE agenda_items ADD COLUMN completado_en TIMESTAMP")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute("ALTER TABLE agenda_items ADD COLUMN enviado_a TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            conn.rollback()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agenda_item_imagenes (
                id SERIAL PRIMARY KEY,
                item_id INTEGER NOT NULL REFERENCES agenda_items(id) ON DELETE CASCADE,
                url TEXT NOT NULL,
                ruta TEXT DEFAULT '',
                ocr_texto TEXT DEFAULT '',
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agenda_item_imagenes_item
            ON agenda_item_imagenes (item_id)
        """)
        try:
            conn.execute("ALTER TABLE agenda_item_imagenes ADD COLUMN ruta TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute("ALTER TABLE agenda_item_imagenes ADD COLUMN ocr_texto TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            conn.rollback()
        conn.commit()


@bp.route('/agenda')
@admin_required
def agenda():
    _asegurar_tabla()
    with get_db_connection() as conn:
        cur = conn.execute("""
            SELECT id, texto, completado, categoria, orden, fecha_limite, completado_en, enviado_a
            FROM agenda_items
            ORDER BY completado ASC,
                     CASE WHEN completado = FALSE THEN
                         (CASE WHEN fecha_limite IS NOT NULL THEN 0 ELSE 1 END)
                     ELSE 2 END ASC,
                     CASE WHEN completado = FALSE THEN fecha_limite ELSE NULL END ASC NULLS LAST,
                     CASE WHEN completado = FALSE THEN orden ELSE NULL END ASC,
                     CASE WHEN completado = FALSE THEN id ELSE NULL END ASC,
                     completado_en DESC NULLS LAST,
                     id DESC
        """)
        items = cur.fetchall()
        cur2 = conn.execute("""
            SELECT item_id, id, url, ruta, ocr_texto FROM agenda_item_imagenes ORDER BY id
        """)
        imagenes = {}
        for r in cur2.fetchall():
            url = r['url']
            if r['ruta']:
                url = url_for('agenda.servir_imagen_item', img_id=r['id'])
            imagenes.setdefault(r[0], []).append({
                'id': r[1], 'url': url,
                'ocr_texto': r['ocr_texto'] or ''
            })
    return render_template('agenda.html', items=items, imagenes=imagenes)


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
        row = conn.execute("SELECT completado FROM agenda_items WHERE id = %s", (item_id,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'})
        
        nuevo_estado = not row['completado']
        if nuevo_estado:
            conn.execute(
                "UPDATE agenda_items SET completado = TRUE, completado_en = CURRENT_TIMESTAMP WHERE id = %s",
                (item_id,)
            )
        else:
            conn.execute(
                "UPDATE agenda_items SET completado = FALSE, completado_en = NULL WHERE id = %s",
                (item_id,)
            )
        conn.commit()
    return jsonify({'ok': True, 'completado': nuevo_estado})


@bp.route('/agenda/item/<int:item_id>', methods=['DELETE'])
@admin_required
def eliminar_item(item_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM agenda_items WHERE id = %s", (item_id,))
        conn.commit()
    return jsonify({'ok': True})


@bp.route('/agenda/item/<int:item_id>/imagen', methods=['POST'])
@admin_required
def subir_imagen_item(item_id):
    _asegurar_tabla()
    if 'imagen' not in request.files:
        return jsonify({'ok': False, 'error': 'No se recibió archivo'}), 400
    try:
        file = request.files['imagen']
        ext = os.path.splitext(file.filename or '')[-1].lower() or '.png'
        if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'):
            ext = '.png'
        nombre = f'item{item_id}_{os.urandom(6).hex()}{ext}'
        ruta = os.path.join(_AGENDA_IMG_DIR, nombre)
        file.save(ruta)

        ocr_texto = _ocr_imagen(ruta) or ''

        with get_db_connection() as conn:
            cur = conn.execute(
                "INSERT INTO agenda_item_imagenes (item_id, url, ruta, ocr_texto) VALUES (%s, '', %s, %s) RETURNING id",
                (item_id, ruta, ocr_texto)
            )
            img_id = cur.fetchone()[0]
            conn.commit()
        return jsonify({
            'ok': True,
            'id': img_id,
            'url': url_for('agenda.servir_imagen_item', img_id=img_id),
            'ocr_texto': ocr_texto
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/agenda/imagen/<int:img_id>/archivo')
@admin_required
def servir_imagen_item(img_id):
    with get_db_connection() as conn:
        cur = conn.execute("SELECT ruta, url FROM agenda_item_imagenes WHERE id = %s", (img_id,))
        row = cur.fetchone()
    if not row:
        return 'Not found', 404
    if row['ruta'] and os.path.exists(row['ruta']):
        return send_from_directory(os.path.dirname(row['ruta']), os.path.basename(row['ruta']))
    if row['url']:
        return redirect(row['url'])
    return 'Not found', 404


@bp.route('/agenda/imagen/<int:img_id>', methods=['DELETE'])
@admin_required
def eliminar_imagen_item(img_id):
    with get_db_connection() as conn:
        cur = conn.execute("SELECT ruta, url FROM agenda_item_imagenes WHERE id = %s", (img_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'Imagen no encontrada'})
        conn.execute("DELETE FROM agenda_item_imagenes WHERE id = %s", (img_id,))
        conn.commit()
    ruta_local = row['ruta']
    if ruta_local and os.path.exists(ruta_local):
        try:
            os.remove(ruta_local)
        except Exception:
            pass
    if not ruta_local and row['url'] and 'cloudinary.com' in row['url']:
        try:
            public_id = row['url'].split('/')[-1].rsplit('.', 1)[0]
            import cloudinary.uploader
            cloudinary.uploader.destroy(f'tuctuc_agenda/{public_id}')
        except Exception:
            pass
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
            "INSERT INTO chat_mensajes (rol, contenido, canal, archivado) VALUES ('user', %s, 'captura', FALSE)",
            (contenido,)
        )
        conn.execute(
            "INSERT INTO chat_mensajes (rol, contenido, canal, archivado) VALUES ('user', %s, 'captura', FALSE)",
            (contenido,)
        )
        placeholders3 = ', '.join(['%s'] * len(ids))
        conn.execute(
            f"UPDATE agenda_items SET enviado_a = 'ASISTENTES' WHERE id IN ({placeholders3})",
            tuple(ids)
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
                SELECT id, texto, completado, fecha_limite, completado_en
                FROM agenda_items
                ORDER BY completado ASC,
                         CASE WHEN completado = FALSE THEN
                             (CASE WHEN fecha_limite IS NOT NULL THEN 0 ELSE 1 END)
                         ELSE 2 END ASC,
                         CASE WHEN completado = FALSE THEN fecha_limite ELSE NULL END ASC NULLS LAST,
                         CASE WHEN completado = FALSE THEN orden ELSE NULL END ASC,
                         CASE WHEN completado = FALSE THEN id ELSE NULL END ASC,
                         completado_en DESC NULLS LAST,
                         id DESC
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
            if completado:
                cur = conn.execute(
                    """UPDATE agenda_items
                       SET completado = TRUE, completado_en = CURRENT_TIMESTAMP
                       WHERE id = %s
                       RETURNING id, completado""",
                    (item_id,)
                )
            else:
                cur = conn.execute(
                    """UPDATE agenda_items
                       SET completado = FALSE, completado_en = NULL
                       WHERE id = %s
                       RETURNING id, completado""",
                    (item_id,)
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

        cur2 = conn.execute(
            "SELECT id, url, ruta, ocr_texto FROM agenda_item_imagenes WHERE item_id = %s ORDER BY id",
            (item_id,)
        )
        imgs = cur2.fetchall()
        if imgs:
            contenido += "\nIMAGENES_REFERENCIA:"
            for r in imgs:
                u = url_for('agenda.servir_imagen_item', img_id=r['id']) if r['ruta'] else r['url']
                contenido += f"\n- {u}"
                if r['ocr_texto']:
                    contenido += f"\n  [OCR: {r['ocr_texto'][:1500]}]"

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

        placeholders2 = ', '.join(['%s'] * len(ids))
        cur2 = conn.execute(
            f"SELECT item_id, id, url, ruta, ocr_texto FROM agenda_item_imagenes WHERE item_id IN ({placeholders2}) ORDER BY item_id, id",
            tuple(ids)
        )
        imgs = cur2.fetchall()
        if imgs:
            contenido += "\nIMAGENES_REFERENCIA:"
            for r in imgs:
                u = url_for('agenda.servir_imagen_item', img_id=r['id']) if r['ruta'] else r['url']
                contenido += f"\n- {r['item_id']}: {u}"
                if r['ocr_texto']:
                    contenido += f"\n  [OCR: {r['ocr_texto'][:1500]}]"

        conn.execute(
            "INSERT INTO chat_mensajes (rol, contenido, canal, archivado) VALUES ('user', %s, 'captura', FALSE)",
            (contenido,)
        )
        conn.commit()
    return jsonify({'ok': True})

