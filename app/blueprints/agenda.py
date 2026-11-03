import os
from datetime import datetime

from functools import wraps

from flask import Blueprint, render_template, request, jsonify, send_from_directory, url_for, redirect, session
from ..db import get_db_connection

bp = Blueprint('agenda', __name__)

def _login_required(f):
    """Cualquier usuario autenticado (2026-11-02: agenda para todos)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('usuario_id'):
            if (request.is_json or
                    request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                    'application/json' in request.headers.get('Accept', '')):
                return jsonify({'ok': False, 'error': 'No autenticado'}), 401
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return wrapper


def _uid():
    try:
        v = session.get('usuario_id')
        return int(v) if v else None
    except (TypeError, ValueError):
        return None


def _es_admin():
    return session.get('rol') == 'Administrador'


def _alcance():
    """(where, params): no-admin solo ve lo suyo; admin todo."""
    if _es_admin():
        return '', []
    return ' AND usuario_id = %s', [_uid()]


_AGENDA_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agenda_imagenes')
os.makedirs(_AGENDA_IMG_DIR, exist_ok=True)

_OCR_BIN = None
for _candidate in ('/usr/bin/tesseract', r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
    if os.path.exists(_candidate):
        _OCR_BIN = _candidate
        break


def _escribir_bridge_chat(mensaje, prefix='todos'):
    """Escribe mensaje en bridge_chat.md para que el Telegram bridge lo reenvíe."""
    try:
        bridge_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'bridge_chat.md'
        )
        bloque = f"\n{prefix} - {mensaje}\n"
        with open(bridge_path, 'a', encoding='utf-8') as f:
            f.write(bloque)
    except Exception:
        pass


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
        try:
            conn.execute("ALTER TABLE agenda_items ADD COLUMN usuario_id INTEGER")
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS asistentes_estado (
                nombre VARCHAR(50) PRIMARY KEY,
                disponible BOOLEAN DEFAULT FALSE,
                ultimo_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


@bp.route('/agenda')
@_login_required
def agenda():
    _asegurar_tabla()
    _alc, _par = _alcance()
    _fuid = request.args.get('usuario_id', '').strip()
    if _es_admin() and _fuid:
        try:
            _alc, _par = ' AND usuario_id = %s', [int(_fuid)]
        except ValueError:
            pass
    with get_db_connection() as conn:
        cur = conn.execute("""
            SELECT id, texto, completado, categoria, orden, fecha_limite, completado_en, enviado_a, usuario_id
            FROM agenda_items
            WHERE 1 = 1""" + _alc + """
            ORDER BY completado ASC,
                     CASE WHEN completado = FALSE AND enviado_a IS NOT NULL AND enviado_a != '' THEN 0 ELSE 1 END ASC,
                     CASE WHEN completado = FALSE THEN
                         (CASE WHEN fecha_limite IS NOT NULL THEN 0 ELSE 1 END)
                     ELSE 2 END ASC,
                     CASE WHEN completado = FALSE THEN fecha_limite ELSE NULL END ASC NULLS LAST,
                     CASE WHEN completado = FALSE THEN orden ELSE NULL END ASC,
                     CASE WHEN completado = FALSE THEN id ELSE NULL END ASC,
                     completado_en DESC NULLS LAST,
                     id DESC
        """, _par)
        items = cur.fetchall()
        cur2 = conn.execute("""
            SELECT item_id, id, url, ruta, ocr_texto FROM agenda_item_imagenes ORDER BY id
        """)
        imagenes = {}
        for r in cur2.fetchall():
            url = r['url']
            if r['ruta']:
                url = url_for('agenda.servir_imagen_item', img_id=r['id'])
            imagenes.setdefault(r['item_id'], []).append({
                'id': r['id'], 'url': url,
                'ocr_texto': r['ocr_texto'] or ''
            })
            
        # Obtener estados de asistentes
        asistentes = {'antigravity': 'offline', 'opencode': 'offline'}
        try:
            cur_states = conn.execute("SELECT nombre, disponible, ultimo_heartbeat FROM asistentes_estado")
            for row in cur_states.fetchall():
                nombre = row['nombre']
                disponible = row['disponible']
                ultimo = row['ultimo_heartbeat']
                online = False
                if disponible and ultimo:
                    diff = (datetime.now() - ultimo).total_seconds()
                    if diff < 45:
                        online = True
                asistentes[nombre] = 'online' if online else 'offline'
        except Exception:
            pass

    return render_template('agenda.html', items=items, imagenes=imagenes, asistentes=asistentes)


@bp.route('/agenda/item', methods=['POST'])
@_login_required
def agregar_item():
    _asegurar_tabla()
    data = request.get_json() or {}
    texto = (data.get('texto') or '').strip()
    categoria = (data.get('categoria') or '').strip()
    fecha_limite = (data.get('fecha_limite') or '').strip() or None
    if not texto:
        return jsonify({'ok': False, 'error': 'Texto vacío'})
    with get_db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO agenda_items (texto, categoria, fecha_limite, usuario_id) VALUES (%s, %s, %s, %s) RETURNING id",
            (texto, categoria, fecha_limite, _uid())
        )
        item_id = cur.fetchone()[0]
        conn.commit()
    return jsonify({'ok': True, 'id': item_id})


@bp.route('/agenda/item/<int:item_id>/toggle', methods=['POST'])
@_login_required
def toggle_item(item_id):
    with get_db_connection() as conn:
        _w, _p = _alcance()
        row = conn.execute("SELECT completado FROM agenda_items WHERE id = %s" + _w, (item_id, *_p)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'})
        
        nuevo_estado = not row['completado']
        if nuevo_estado:
            conn.execute(
                "UPDATE agenda_items SET completado = TRUE, completado_en = CURRENT_TIMESTAMP WHERE id = %s" + _w,
                (item_id, *_p)
            )
        else:
            conn.execute(
                "UPDATE agenda_items SET completado = FALSE, completado_en = NULL WHERE id = %s" + _w,
                (item_id, *_p)
            )
        conn.commit()
    return jsonify({'ok': True, 'completado': nuevo_estado})


@bp.route('/agenda/item/<int:item_id>', methods=['DELETE'])
@_login_required
def eliminar_item(item_id):
    _w, _p = _alcance()
    with get_db_connection() as conn:
        row = conn.execute("SELECT id FROM agenda_items WHERE id = %s" + _w, (item_id, *_p)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'No encontrado'})
        conn.execute("DELETE FROM agenda_items WHERE id = %s", (item_id,))
        conn.commit()
    return jsonify({'ok': True})


@bp.route('/agenda/item/<int:item_id>/imagen', methods=['POST'])
@_login_required
def subir_imagen_item(item_id):
    _asegurar_tabla()
    _w, _p = _alcance()
    with get_db_connection() as conn:
        _ok = conn.execute("SELECT id FROM agenda_items WHERE id = %s" + _w, (item_id, *_p)).fetchone()
    if not _ok:
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    if 'imagen' not in request.files:
        return jsonify({'ok': False, 'error': 'No se recibió archivo'}), 400
    try:
        file = request.files['imagen']
        ext = os.path.splitext(file.filename or '')[-1].lower() or '.jpg'
        if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'):
            ext = '.jpg'

        nombre = f'item{item_id}_{os.urandom(6).hex()}{ext}'
        ruta = os.path.join(_AGENDA_IMG_DIR, nombre)
        guardado = False

        try:
            from PIL import Image, ImageOps
            img = Image.open(file)
            img = ImageOps.exif_transpose(img)
            if ext in ('.jpg', '.jpeg') or img.mode in ('RGB', 'YCbCr', 'CMYK'):
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                ext = '.jpg'
                nombre = f'item{item_id}_{os.urandom(6).hex()}{ext}'
                ruta = os.path.join(_AGENDA_IMG_DIR, nombre)
                img.save(ruta, 'JPEG', quality=85, optimize=True)
                guardado = True
            elif ext == '.webp':
                nombre = f'item{item_id}_{os.urandom(6).hex()}.webp'
                ruta = os.path.join(_AGENDA_IMG_DIR, nombre)
                img.save(ruta, 'WEBP', quality=85)
                guardado = True
        except Exception:
            pass

        if not guardado:
            file.seek(0)
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
@_login_required
def servir_imagen_item(img_id):
    with get_db_connection() as conn:
        cur = conn.execute("SELECT i.ruta, i.url, a.usuario_id FROM agenda_item_imagenes i JOIN agenda_items a ON a.id = i.item_id WHERE i.id = %s", (img_id,))
        row = cur.fetchone()
    if not row:
        return 'Not found', 404
    if not _es_admin() and row['usuario_id'] != _uid():
        return 'Not found', 404

    ruta_guardada = row['ruta'] or ''
    nombre = os.path.basename(ruta_guardada) if ruta_guardada else ''

    # 1. Buscar en _AGENDA_IMG_DIR por nombre de archivo
    if nombre:
        ruta_directorio = os.path.join(_AGENDA_IMG_DIR, nombre)
        if os.path.exists(ruta_directorio):
            return send_from_directory(_AGENDA_IMG_DIR, nombre)

    # 2. Buscar por ruta absoluta directa si existe
    if ruta_guardada and os.path.exists(ruta_guardada):
        return send_from_directory(os.path.dirname(ruta_guardada), os.path.basename(ruta_guardada))

    # 3. Si hay URL externa (ej. Cloudinary / S3)
    if row['url']:
        return redirect(row['url'])

    return 'Not found', 404


@bp.route('/agenda/imagen/<int:img_id>', methods=['DELETE'])
@_login_required
def eliminar_imagen_item(img_id):
    with get_db_connection() as conn:
        cur = conn.execute("SELECT i.ruta, i.url, a.usuario_id FROM agenda_item_imagenes i JOIN agenda_items a ON a.id = i.item_id WHERE i.id = %s", (img_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'Imagen no encontrada'})
        if not _es_admin() and row['usuario_id'] != _uid():
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
@_login_required
def editar_item(item_id):
    data = request.get_json() or {}
    texto = (data.get('texto') or '').strip()
    categoria = (data.get('categoria') or '').strip()
    fecha_limite = (data.get('fecha_limite') or '').strip() or None
    
    if not texto:
        return jsonify({'ok': False, 'error': 'El texto de la tarea no puede estar vacío'})
        
    _w, _p = _alcance()
    with get_db_connection() as conn:
        row = conn.execute("SELECT id FROM agenda_items WHERE id = %s" + _w, (item_id, *_p)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'Tarea no encontrada'})
        conn.execute(
            "UPDATE agenda_items SET texto = %s, categoria = %s, fecha_limite = %s WHERE id = %s" + _w,
            (texto, categoria, fecha_limite, item_id, *_p)
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
            "INSERT INTO agenda_items (texto, categoria, fecha_limite, usuario_id) VALUES (%s, %s, %s, %s) RETURNING id",
            (texto, categoria, fecha_limite, _uid())
        )
        item_id = cur.fetchone()[0]
        conn.commit()
    return jsonify({'ok': True, 'id': item_id})


@bp.route('/agenda/reordenar', methods=['POST'])
@_login_required
def reordenar_agenda():
    data = request.get_json() or {}
    ids = data.get('ids')
    if not ids or not isinstance(ids, list):
        return jsonify({'ok': False, 'error': 'Lista de IDs inválida'})
    
    _w, _p = _alcance()
    with get_db_connection() as conn:
        for idx, item_id in enumerate(ids):
            conn.execute(
                "UPDATE agenda_items SET orden = %s WHERE id = %s" + _w,
                (idx, item_id, *_p)
            )
        conn.commit()
    return jsonify({'ok': True})


@bp.route('/agenda/item/<int:item_id>/activar', methods=['POST'])
@_login_required
def activar_item_agenda(item_id):
    _w, _p = _alcance()
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT texto, categoria FROM agenda_items WHERE id = %s" + _w,
            (item_id, *_p)
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
        conn.execute(
            "UPDATE agenda_items SET enviado_a = 'ASISTENTES' WHERE id = %s" + _w,
            (item_id, *_p)
        )
        conn.commit()

        _escribir_bridge_chat(contenido)

    return jsonify({'ok': True})


@bp.route('/agenda/item/activar-multi', methods=['POST'])
@_login_required
def activar_multi_agenda():
    data = request.get_json() or {}
    ids = data.get('ids')
    asistente = (data.get('asistente') or 'todos').strip().lower()
    if not ids or not isinstance(ids, list):
        return jsonify({'ok': False, 'error': 'Lista de IDs inválida'})
    
    _w, _p = _alcance()
    with get_db_connection() as conn:
        placeholders = ', '.join(['%s'] * len(ids))
        cur = conn.execute(
            f"SELECT id, texto, categoria FROM agenda_items WHERE id IN ({placeholders})" + _w,
            tuple(ids) + tuple(_p)
        )
        rows = cur.fetchall()
        if not rows:
            return jsonify({'ok': False, 'error': 'Tareas no encontradas'})
        
        # Resolver etiquetas del asistente
        if asistente == 'antigravity':
            db_label = 'Antigravity'
            prefix = 'anti'
            db_content = f"@anti Activar tareas agrupadas:\n"
        elif asistente == 'opencode':
            db_label = 'Open Code'
            prefix = 'open'
            db_content = f"@open Activar tareas agrupadas:\n"
        else:
            db_label = 'ASISTENTES'
            prefix = 'todos'
            db_content = "Activar tareas agrupadas:\n"
            
        # Build consolidated message
        lines = []
        for row in rows:
            lines.append(f"- [Requerimiento #{row['id']}] {row['texto']} ({row['categoria']})")
        
        contenido = "\n".join(lines)
        
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
        
        db_content += contenido
        
        conn.execute(
            "INSERT INTO chat_mensajes (rol, contenido, canal, archivado) VALUES ('user', %s, 'captura', FALSE)",
            (db_content,)
        )
        
        placeholders3 = ', '.join(['%s'] * len(ids))
        conn.execute(
            f"UPDATE agenda_items SET enviado_a = %s WHERE id IN ({placeholders3})" + _w,
            (db_label,) + tuple(ids) + tuple(_p)
        )
        conn.commit()
        _escribir_bridge_chat(db_content, prefix)
        
    return jsonify({'ok': True})
