import os
import re
import unicodedata
import uuid
from datetime import datetime  # noqa

import requests as http_requests
from flask import (abort, Blueprint, jsonify, redirect, render_template,
                   request, session, url_for)

from ..db import get_db_connection
from .auth import admin_required, solo_admin

bp = Blueprint('core', __name__)

BACKUPS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'backups')

_config_tipologia_lista = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def generar_slug(nombre):
    slug = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    slug = slug.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')


def crear_tabla_config_tipologia(conn):
    global _config_tipologia_lista
    if _config_tipologia_lista:
        return
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config_tipologia (
            tipo TEXT PRIMARY KEY,
            dias_gratis INTEGER NOT NULL DEFAULT 0,
            modo_descuento TEXT NOT NULL DEFAULT 'calendario'
        )
    """)
    for tipo, dias, modo in [
        ('restaurante', 0, 'uso_real'),
        ('tienda',      0, 'calendario'),
        ('taller',      0, 'calendario'),
        ('hospedaje',   0, 'calendario'),
        ('inmobiliaria',0, 'calendario'),
        ('compraventa', 0, 'calendario'),
    ]:
        conn.execute(
            "INSERT INTO config_tipologia (tipo, dias_gratis, modo_descuento) VALUES (%s, %s, %s) ON CONFLICT (tipo) DO NOTHING",
            (tipo, dias, modo)
        )
    conn.commit()
    _config_tipologia_lista = True


def _contactos_allowed():
    return session.get('rol') in ('Administrador', 'ClienteVFP', 'Tienda', 'Restaurante') and session.get('usuario_id')


def _asegurar_tabla_contactos(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contactos (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER,
            tercero_id INTEGER,
            nombre TEXT,
            telefono TEXT,
            chat_token TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    for sql in [
        "ALTER TABLE contactos ADD COLUMN IF NOT EXISTS tercero_id INTEGER",
        "ALTER TABLE contactos ADD COLUMN IF NOT EXISTS chat_token TEXT",
        "ALTER TABLE contactos ADD COLUMN IF NOT EXISTS negocio_id INTEGER",
    ]:
        conn.execute(sql)
    conn.commit()


def _migrar_contactos_tercero(conn, origen_id, destino_id):
    if not origen_id or not destino_id or int(origen_id) == int(destino_id):
        return
    conn.execute(
        "UPDATE contactos SET tercero_id = %s, negocio_id = %s WHERE tercero_id = %s",
        (destino_id, destino_id, origen_id)
    )
    conn.commit()


def _contactos_tercero_id(conn):
    tercero_actual = session.get('chat_tercero_id')
    uid = session.get('usuario_id')
    rol = session.get('rol')
    if not uid:
        return None

    if rol in ('Tienda', 'Restaurante'):
        return uid

    nombre = session.get('nombre') or ''
    if nombre:
        tercero_con_tel = conn.execute(
            """
            SELECT id FROM terceros
            WHERE nombre ILIKE %s AND telefono IS NOT NULL AND telefono <> ''
            ORDER BY id DESC LIMIT 1
            """,
            (nombre,)
        ).fetchone()
        if tercero_con_tel:
            _migrar_contactos_tercero(conn, tercero_actual, tercero_con_tel['id'])
            session['chat_tercero_id'] = tercero_con_tel['id']
            session.modified = True
            return tercero_con_tel['id']

    if tercero_actual:
        return tercero_actual

    tercero = None
    if nombre:
        tercero = conn.execute(
            "SELECT id FROM terceros WHERE nombre = %s LIMIT 1",
            (nombre,)
        ).fetchone()
    if tercero:
        session['chat_tercero_id'] = tercero['id']
        session.modified = True
        return tercero['id']

    if nombre:
        nuevo = conn.execute(
            "INSERT INTO terceros (nombre, tipo_tercero) VALUES (%s, 'admin') RETURNING id",
            (nombre,)
        ).fetchone()
        conn.commit()
        session['chat_tercero_id'] = nuevo['id']
        session.modified = True
        return nuevo['id']

    return uid


# ── Telegram ──────────────────────────────────────────────────────────────────

def enviar_notificacion_telegram(mensaje):
    try:
        conn = get_db_connection()
        config = conn.execute(
            'SELECT telegram_token, telegram_chat_id, notificaciones_activas FROM "CONFIGURACION_SISTEMA" WHERE id = 1'
        ).fetchone()
        conn.close()
        if not config or not config['notificaciones_activas']:
            return False
        token = config['telegram_token']
        chat_id = config['telegram_chat_id']
        if not token or not chat_id:
            return False
        r = http_requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'HTML'},
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        print(f'[Telegram] Error: {e}')
        return False


# ── Rutas principales ─────────────────────────────────────────────────────────

@bp.route('/ping')
def ping():
    return 'pong', 200


@bp.route('/')
def index():
    if session.get('usuario_id') or session.get('rol'):
        return redirect(url_for('core.colaborador_inicio'))
    return redirect(url_for('auth.admin_login'))


@bp.route('/api/version')
def api_version():
    import subprocess
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    commit = ''
    commit_source = ''
    commit_error = ''

    def _commit_from_git_files(base_dir):
        git_dir = os.path.join(base_dir, '.git')
        if os.path.isfile(git_dir):
            with open(git_dir, encoding='utf-8') as f:
                git_ref = f.read().strip()
            if git_ref.startswith('gitdir:'):
                git_dir = os.path.abspath(os.path.join(base_dir, git_ref.split(':', 1)[1].strip()))

        head_path = os.path.join(git_dir, 'HEAD')
        with open(head_path, encoding='utf-8') as f:
            head = f.read().strip()

        if not head.startswith('ref:'):
            return head[:7]

        ref = head.split(' ', 1)[1].strip()
        ref_path = os.path.join(git_dir, *ref.split('/'))
        if os.path.exists(ref_path):
            with open(ref_path, encoding='utf-8') as f:
                return f.read().strip()[:7]

        packed_refs = os.path.join(git_dir, 'packed-refs')
        with open(packed_refs, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('^'):
                    continue
                sha, packed_ref = line.split(' ', 1)
                if packed_ref == ref:
                    return sha[:7]

        return ''

    for env_name in ('GIT_COMMIT', 'COMMIT_SHA', 'SOURCE_VERSION', 'RENDER_GIT_COMMIT', 'HEROKU_SLUG_COMMIT'):
        env_commit = os.environ.get(env_name, '').strip()
        if env_commit:
            commit = env_commit[:7]
            commit_source = env_name
            break

    if not commit:
        try:
            commit = _commit_from_git_files(repo_dir)
            if commit:
                commit_source = os.path.join(repo_dir, '.git')
        except Exception as e:
            commit_error = str(e)

    if not commit:
        for git_dir in (repo_dir, os.getcwd()):
            try:
                commit = subprocess.check_output(
                    ['git', 'rev-parse', '--short', 'HEAD'],
                    cwd=git_dir,
                    stderr=subprocess.STDOUT,
                    encoding='utf-8'
                ).strip()
                commit_source = git_dir
                break
            except Exception as e:
                commit_error = str(e)

    return jsonify({
        'version': '2.0.0',
        'ok': True,
        'commit': commit,
        'commit_source': commit_source,
        'commit_error': commit_error,
    })


@bp.route('/empieza')
@bp.route('/empieza/<ref_vendedor>')
def landing_empieza(ref_vendedor=None):
    dias_negociados = int(request.args.get('dias', 0))
    cfg = {}
    conn = None
    try:
        conn = get_db_connection()
        crear_tabla_config_tipologia(conn)
        rows = conn.execute("SELECT tipo, dias_gratis FROM config_tipologia").fetchall()
        cfg = {r['tipo']: {'dias_gratis': r['dias_gratis']} for r in rows}
        conn.close()
    except Exception:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
    return render_template('empieza.html', cfg=cfg,
                           ref_vendedor=ref_vendedor or '',
                           dias_negociados=dias_negociados)


@bp.route('/api/prospecto', methods=['POST'])
def api_crear_prospecto():
    data = request.get_json()
    nombre = data.get('nombre', '').strip()
    telefono = ''.join(filter(str.isdigit, data.get('telefono', '')))
    tipologia = data.get('tipologia', '').strip()

    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    if len(telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular debe tener al menos 10 dígitos'}), 400
    if not tipologia:
        return jsonify({'ok': False, 'error': 'Selecciona un tipo de negocio'}), 400

    try:
        conn = get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prospectos (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                telefono VARCHAR(20) NOT NULL,
                tipologia VARCHAR(50) NOT NULL,
                estado VARCHAR(20) DEFAULT 'nuevo',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        existente = conn.execute(
            "SELECT id FROM prospectos WHERE telefono = %s LIMIT 1", (telefono,)
        ).fetchone()
        if existente:
            conn.execute(
                "UPDATE prospectos SET nombre = %s, tipologia = %s, estado = 'nuevo' WHERE id = %s",
                (nombre, tipologia, existente['id'])
            )
        else:
            conn.execute(
                "INSERT INTO prospectos (nombre, telefono, tipologia) VALUES (%s, %s, %s)",
                (nombre, telefono, tipologia)
            )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/registro-rapido', methods=['POST'])
def api_registro_rapido():
    from .restaurantes import _crear_tablas as crear_tablas_restaurante
    from .tiendas import _crear_tablas as crear_tablas_tienda

    data = request.get_json()
    tipo            = data.get('tipo', '').strip()
    nombre_neg      = data.get('nombre_negocio', '').strip()
    subtipo         = data.get('subtipo', 'menu_dia').strip()
    nombre_due      = data.get('nombre_dueno', '').strip()
    telefono        = ''.join(filter(str.isdigit, data.get('telefono', '')))
    ref_vendedor    = data.get('ref_vendedor', '').strip()[:50]
    dias_negociados = int(data.get('dias_negociados', 0))

    if tipo not in ('restaurante', 'tienda'):
        return jsonify({'ok': False, 'error': 'Tipo de negocio inválido'}), 400
    if not nombre_neg:
        return jsonify({'ok': False, 'error': 'Nombre del negocio requerido'}), 400
    if not nombre_due:
        return jsonify({'ok': False, 'error': 'Tu nombre es requerido'}), 400
    if len(telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular debe tener al menos 10 dígitos'}), 400

    slug = generar_slug(nombre_neg)

    try:
        conn = get_db_connection()
        # Tercero del dueño (persona)
        tercero = conn.execute(
            "SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (telefono,)
        ).fetchone()
        if tercero:
            admin_id = tercero['id']
            conn.execute("UPDATE terceros SET nombre = %s WHERE id = %s", (nombre_due, admin_id))
            conn.commit()
        else:
            admin_id = conn.execute(
                "INSERT INTO terceros (nombre, telefono, tipo_tercero) VALUES (%s, %s, 'persona') RETURNING id",
                (nombre_due, telefono)
            ).fetchone()[0]
            conn.commit()

        crear_tabla_config_tipologia(conn)
        cfg_tipo = conn.execute("SELECT dias_gratis FROM config_tipologia WHERE tipo=%s", (tipo,)).fetchone()
        dias_gratis = dias_negociados if dias_negociados > 0 else (cfg_tipo['dias_gratis'] if cfg_tipo else 0)

        if tipo == 'restaurante':
            crear_tablas_restaurante(conn)
            conn.execute("ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS ref_vendedor TEXT")
            if conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone():
                conn.close()
                return jsonify({'ok': False, 'error': 'Ya existe un restaurante con ese nombre'}), 400
            token_acceso = uuid.uuid4().hex
            negocio_tercero_id = conn.execute(
                "INSERT INTO terceros (nombre, tipo_tercero) VALUES (%s, 'negocio') RETURNING id", (nombre_neg,)
            ).fetchone()[0]
            conn.execute("""
                INSERT INTO restaurantes (nombre, slug, tipo_restaurante, admin_id, admin_nombre, admin_telefono, token_acceso, dias_pagados, activo, tercero_id, ref_vendedor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s)
            """, (nombre_neg, slug, subtipo, admin_id, nombre_due, telefono, token_acceso, dias_gratis, negocio_tercero_id, ref_vendedor or None))
            conn.commit()
            conn.close()
            session.update({'usuario_id': admin_id, 'nombre': nombre_due,
                            'telefono': telefono, 'rol': 'Restaurante'})
            session.permanent = True
            return jsonify({'ok': True, 'redirect': f'/mi-restaurante/{slug}'})

        else:  # tienda
            crear_tablas_tienda(conn)
            conn.execute("ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS ref_vendedor TEXT")
            if conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone():
                conn.close()
                return jsonify({'ok': False, 'error': 'Ya existe una tienda con ese nombre'}), 400
            token_acceso = uuid.uuid4().hex
            negocio_tercero_id = conn.execute(
                "INSERT INTO terceros (nombre, tipo_tercero) VALUES (%s, 'negocio') RETURNING id", (nombre_neg,)
            ).fetchone()[0]
            conn.execute("""
                INSERT INTO tiendas (nombre, slug, admin_id, admin_nombre, admin_telefono, token_acceso, dias_pagados, activo, tercero_id, ref_vendedor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s)
            """, (nombre_neg, slug, admin_id, nombre_due, telefono, token_acceso, dias_gratis, negocio_tercero_id, ref_vendedor or None))
            conn.commit()
            conn.close()
            session.update({'usuario_id': admin_id, 'nombre': nombre_due,
                            'telefono': telefono, 'rol': 'Tienda'})
            session.permanent = True
            return jsonify({'ok': True, 'redirect': f'/mi-tienda/{slug}'})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Admin — rutas generales ───────────────────────────────────────────────────

@bp.route('/admin/acceso/<codigo>')
def admin_acceso(codigo):
    CODIGO_ADMIN = 'tuctuc2025'
    if codigo != CODIGO_ADMIN:
        return redirect(url_for('auth.admin_login'))
    conn = get_db_connection()
    admin = conn.execute(
        "SELECT * FROM usuarios WHERE rol = 'Administrador' LIMIT 1"
    ).fetchone()
    conn.close()
    if not admin:
        return redirect(url_for('auth.admin_login'))
    session.clear()
    session.update({
        'usuario_id': admin['id'],
        'nombre': admin['nombre'],
        'rol': 'Administrador',
        'dispositivo_id': admin.get('dispositivo_id', ''),
    })
    session.permanent = True
    return redirect(url_for('auth.admin_area'))


@bp.route('/admin/menu')
@bp.route('/admin_menu')
@admin_required
def admin_menu():
    return render_template('admin_menu.html',
                           nombre=session.get('nombre', ''),
                           device_id=session.get('dispositivo_id', ''))


@bp.route('/admin/contactos')
def admin_contactos():
    if not _contactos_allowed():
        return redirect(url_for('auth.admin_login'))
    conn = get_db_connection()
    try:
        _asegurar_tabla_contactos(conn)
        tercero_id = _contactos_tercero_id(conn)
        if not tercero_id:
            return redirect(url_for('auth.admin_login'))
        return render_template(
            'contactos_admin.html',
            admin_id=tercero_id,
            nombre_admin=session.get('nombre', '')
        )
    finally:
        conn.close()


@bp.route('/api/admin/contactos', methods=['GET'])
def api_admin_contactos_lista():
    if not _contactos_allowed():
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _asegurar_tabla_contactos(conn)
        tercero_id = _contactos_tercero_id(conn)
        rows = conn.execute("""
            SELECT id, nombre, telefono, created_at::text
            FROM contactos
            WHERE tercero_id = %s
            ORDER BY nombre NULLS LAST, created_at DESC
        """, (tercero_id,)).fetchall()
        return jsonify({'ok': True, 'contactos': [dict(r) for r in rows]})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin/contactos/importar', methods=['POST'])
def api_admin_contactos_importar():
    if not _contactos_allowed():
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    lista = data.get('contactos', [])
    if not lista:
        return jsonify({'ok': False, 'error': 'contactos requeridos'}), 400
    conn = get_db_connection()
    try:
        _asegurar_tabla_contactos(conn)
        tercero_id = _contactos_tercero_id(conn)
        insertados = 0
        omitidos = 0
        for c in lista:
            nombre = (c.get('nombre') or '').strip()
            telefono = (c.get('telefono') or '').strip()
            if telefono.startswith('00'):
                telefono = '+' + telefono[2:]
            if not (nombre or telefono):
                continue
            if telefono:
                existe = conn.execute(
                    "SELECT 1 FROM contactos WHERE tercero_id = %s AND telefono = %s",
                    (tercero_id, telefono)
                ).fetchone()
                if existe:
                    omitidos += 1
                    continue
            conn.execute(
                "INSERT INTO contactos (negocio_id, tercero_id, nombre, telefono) VALUES (%s, %s, %s, %s)",
                (tercero_id, tercero_id, nombre or None, telefono or None)
            )
            insertados += 1
        conn.commit()
        return jsonify({'ok': True, 'insertados': insertados, 'omitidos': omitidos})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin/contactos/<int:cid>', methods=['DELETE'])
def api_admin_contactos_eliminar(cid):
    if not _contactos_allowed():
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _asegurar_tabla_contactos(conn)
        tercero_id = _contactos_tercero_id(conn)
        conn.execute(
            "DELETE FROM contactos WHERE id = %s AND tercero_id = %s",
            (cid, tercero_id)
        )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/admin/parametros')
@admin_required
def admin_parametros():
    return render_template('admin_parametros.html')


@bp.route('/admin/mantenimiento')
@admin_required
def admin_mantenimiento():
    return render_template('admin_mantenimiento.html')


@bp.route('/admin/negocios')
@admin_required
def admin_negocios():
    try:
        conn = get_db_connection()
        crear_tabla_config_tipologia(conn)
        totales = {}
        for key, tabla, filtro in [
            ('restaurantes',  'restaurantes', "activo = TRUE"),
            ('tiendas',       'tiendas',      "activo = TRUE"),
            ('talleres',      'negocios',     "tipo = 'taller' AND activo = TRUE"),
            ('inmobiliarias', 'inmobiliarias','activa = TRUE'),
            ('compraventas',  'negocios',     "tipo = 'compraventa' AND activo = TRUE"),
            ('hospedajes',    'negocios',     "tipo = 'hospedaje' AND activo = TRUE"),
        ]:
            try:
                totales[key] = (conn.execute(f"SELECT COUNT(*) FROM {tabla} WHERE {filtro}").fetchone() or [0])[0]
            except Exception:
                conn.rollback()
                totales[key] = 0

        cfg_rows = []
        try:
            cfg_rows = conn.execute("SELECT tipo, dias_gratis, modo_descuento FROM config_tipologia").fetchall()
        except Exception:
            conn.rollback()
        cfg = {r['tipo']: {'dias_gratis': r['dias_gratis'], 'modo_descuento': r['modo_descuento']} for r in cfg_rows}
        conn.close()
        return render_template('admin_negocios.html', cfg=cfg, **{f'total_{k}': v for k, v in totales.items()})
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/admin/taller')
@admin_required
def admin_taller_lista():
    try:
        conn = get_db_connection()
        talleres = conn.execute("""
            SELECT n.id, n.nombre, n.slug, n.admin_nombre, n.admin_telefono,
                   n.token_acceso, n.dias_pagados, n.activo,
                   (SELECT COUNT(*) FROM citas_servicio cs WHERE cs.negocio_id = n.id) AS total_citas
            FROM negocios n WHERE n.tipo = 'taller' ORDER BY n.id DESC
        """).fetchall()
        conn.close()
        return render_template('admin_taller_lista.html', talleres=talleres)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/admin/inmobiliaria')
@admin_required
def admin_inmobiliaria_lista():
    try:
        conn = get_db_connection()
        inmobiliarias = conn.execute("""
            SELECT i.id, i.nombre, i.slug, i.telefono, i.whatsapp, i.activa,
                   i.bolsa_habilitada, i.descripcion, i.dias_pagados,
                   t.nombre AS propietario_nombre,
                   (SELECT COUNT(*) FROM propiedad_inmobiliaria pi WHERE pi.inmobiliaria_id = i.id) AS total_propiedades
            FROM inmobiliarias i
            LEFT JOIN terceros t ON t.id = i.propietario_id
            ORDER BY i.id DESC
        """).fetchall()
        conn.close()
        return render_template('admin_inmobiliaria_lista.html', inmobiliarias=inmobiliarias)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/admin/compraventa')
@admin_required
def admin_compraventa_lista():
    try:
        conn = get_db_connection()
        compraventas = conn.execute("""
            SELECT n.id, n.nombre, n.slug, n.activo, n.dias_pagados,
                   t.nombre AS propietario_nombre, t.telefono AS propietario_telefono,
                   (SELECT COUNT(*) FROM compraventa_vehiculos cv WHERE cv.negocio_id = n.id) AS total_vehiculos
            FROM negocios n
            LEFT JOIN terceros t ON t.id = n.propietario_id
            WHERE n.tipo = 'compraventa' ORDER BY n.id DESC
        """).fetchall()
        conn.close()
        return render_template('admin_compraventa_lista.html', compraventas=compraventas)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/admin/hospedaje')
@admin_required
def admin_hospedaje_lista():
    try:
        conn = get_db_connection()
        hospedajes = conn.execute("""
            SELECT n.id, n.nombre, n.slug, n.admin_nombre, n.admin_telefono,
                   n.token_acceso, n.dias_pagados, n.activo,
                   (SELECT COUNT(*) FROM pedidos_hospedaje ph WHERE ph.negocio_id = n.id) AS total_reservas
            FROM negocios n WHERE n.tipo = 'hospedaje' ORDER BY n.id DESC
        """).fetchall()
        conn.close()
        return render_template('admin_hospedaje_lista.html', hospedajes=hospedajes)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/api/admin/config-tipologia/<tipo>', methods=['POST'])
@admin_required
def api_admin_config_tipologia(tipo):
    TIPOS_VALIDOS = {'restaurante', 'tienda', 'taller', 'hospedaje', 'inmobiliaria', 'compraventa'}
    if tipo not in TIPOS_VALIDOS:
        return jsonify({'ok': False, 'error': 'Tipo inválido'}), 400
    data = request.get_json()
    try:
        dias_gratis = int(data.get('dias_gratis', 0))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'dias_gratis debe ser número'}), 400
    modo_descuento = data.get('modo_descuento', 'calendario')
    if modo_descuento not in ('uso_real', 'calendario'):
        return jsonify({'ok': False, 'error': 'Modo inválido'}), 400
    try:
        conn = get_db_connection()
        crear_tabla_config_tipologia(conn)
        conn.execute(
            "INSERT INTO config_tipologia (tipo, dias_gratis, modo_descuento) VALUES (%s, %s, %s) "
            "ON CONFLICT (tipo) DO UPDATE SET dias_gratis=%s, modo_descuento=%s",
            (tipo, dias_gratis, modo_descuento, dias_gratis, modo_descuento)
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Switch de base de datos ───────────────────────────────────────────────────

@bp.route('/admin/switch-database', methods=['POST'])
@admin_required
def admin_switch_database():
    data = request.get_json()
    mode = data.get('mode', 'production')
    if mode not in ['production', 'local']:
        return jsonify({'ok': False, 'error': 'Modo inválido'}), 400
    session['db_mode'] = mode
    modo_texto = '[PRODUCCION] Render' if mode == 'production' else '[LOCAL] Backup'
    return jsonify({'ok': True, 'mode': mode, 'mensaje': f'Cambiado a {modo_texto}'})


@bp.route('/admin/get-database-mode', methods=['GET'])
@admin_required
def admin_get_database_mode():
    return jsonify({'ok': True, 'mode': session.get('db_mode', 'production')})


# ── Backups ───────────────────────────────────────────────────────────────────

@bp.route('/admin/backups')
@admin_required
def admin_backups():
    archivos = []
    if os.path.exists(BACKUPS_DIR):
        for f in sorted(os.listdir(BACKUPS_DIR), reverse=True):
            if f.endswith('.sql'):
                ruta = os.path.join(BACKUPS_DIR, f)
                stat = os.stat(ruta)
                archivos.append({
                    'nombre': f,
                    'fecha': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                    'tamano_mb': round(stat.st_size / 1024 / 1024, 2)
                })
    return render_template('admin_backups.html', backups=archivos,
                           db_mode=session.get('db_mode', 'production'))


@bp.route('/api/admin/backup/crear', methods=['POST'])
@admin_required
def api_admin_backup_crear():
    import psycopg2
    try:
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        db_url = os.getenv('DATABASE_URL', '')
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{ts}_prod.sql'
        filepath = os.path.join(BACKUPS_DIR, filename)

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name
        """)
        tables = [r[0] for r in cur.fetchall()]

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('-- TUC TUC Backup — Producción\n')
            f.write(f'-- Generado: {datetime.now().isoformat()}\n\n')
            f.write("SET client_encoding = 'UTF8';\n\n")
            for table in tables:
                cur.execute("SELECT COUNT(*) FROM " + f'"{table}"')
                count = cur.fetchone()[0]
                if count == 0:
                    continue
                cur.execute(f'SELECT * FROM "{table}"')
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                f.write(f'\n-- Tabla: {table} ({count} filas)\n')
                for row in rows:
                    vals = ', '.join(
                        'NULL' if v is None else f"'{str(v).replace(chr(39), chr(39)+chr(39))}'"
                        for v in row
                    )
                    f.write(f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({vals});\n')

        conn.close()
        stat = os.stat(filepath)
        return jsonify({'ok': True, 'archivo': filename,
                        'tamano_mb': round(stat.st_size / 1024 / 1024, 2)})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/backup/<nombre>/descargar')
@admin_required
def api_admin_backup_descargar(nombre):
    from flask import send_file
    filepath = os.path.join(BACKUPS_DIR, nombre)
    if not os.path.exists(filepath) or not nombre.endswith('.sql'):
        return jsonify({'ok': False, 'error': 'Archivo no encontrado'}), 404
    return send_file(filepath, as_attachment=True, download_name=nombre)


# ── Mantenimiento DB ──────────────────────────────────────────────────────────

@bp.route('/api/admin/db/tablas')
@admin_required
def api_admin_db_tablas():
    try:
        conn = get_db_connection()
        tablas = conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """).fetchall()
        conn.close()
        return jsonify({'ok': True, 'tablas': [t['table_name'] for t in tablas]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/db/tabla/<nombre>/estructura')
@admin_required
def api_admin_db_estructura(nombre):
    try:
        conn = get_db_connection()
        columnas = conn.execute("""
            SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (nombre,)).fetchall()
        if not columnas:
            conn.close()
            return jsonify({'ok': False, 'error': f'Tabla "{nombre}" no encontrada'}), 404
        count = conn.execute(f'SELECT COUNT(*) as total FROM "{nombre}"').fetchone()
        
        # Obtener claves primarias
        pk_rows = conn.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
        """, (nombre,)).fetchall()
        primary_key = [r['attname'] for r in pk_rows]
        
        conn.close()
        return jsonify({
            'ok': True,
            'columnas': [dict(c) for c in columnas],
            'total': count['total'] if count else 0,
            'primary_key': primary_key
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/db/tabla/<nombre>/registros')
@admin_required
def api_admin_db_registros(nombre):
    try:
        pagina = int(request.args.get('pagina', 1))
        limite = int(request.args.get('limite', 50))
        orden = request.args.get('orden', '').strip()
        direccion = request.args.get('direccion', 'asc').strip()
        filtro_columna = request.args.get('filtro_columna', '').strip()
        filtro_valor = request.args.get('filtro_valor', '').strip()
        
        offset = (pagina - 1) * limite
        
        conn = get_db_connection()
        # Verificar que la tabla exista
        exists = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s", (nombre,)).fetchone()
        if not exists:
            conn.close()
            return jsonify({'ok': False, 'error': f'Tabla "{nombre}" no existe'}), 404
            
        if filtro_columna:
            col_exists = conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s", (nombre, filtro_columna)).fetchone()
            if not col_exists:
                conn.close()
                return jsonify({'ok': False, 'error': f'Columna de filtro "{filtro_columna}" inválida'}), 400
                
        if orden:
            col_exists = conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s", (nombre, orden)).fetchone()
            if not col_exists:
                orden = ''
                
        query_base = f'FROM "{nombre}"'
        params = []
        if filtro_columna and filtro_valor:
            col_type = conn.execute("SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s", (nombre, filtro_columna)).fetchone()
            if col_type and col_type['data_type'] in ('integer', 'bigint', 'numeric', 'double precision', 'real', 'smallint'):
                try:
                    val_num = float(filtro_valor)
                    query_base += f' WHERE "{filtro_columna}" = %s'
                    params.append(val_num)
                except ValueError:
                    query_base += f' WHERE CAST("{filtro_columna}" AS TEXT) ILIKE %s'
                    params.append(f'%{filtro_valor}%')
            elif col_type and col_type['data_type'] == 'boolean':
                val_bool = filtro_valor.lower() in ('true', '1', 'yes', 's', 'sí', 'si')
                query_base += f' WHERE "{filtro_columna}" = %s'
                params.append(val_bool)
            else:
                query_base += f' WHERE CAST("{filtro_columna}" AS TEXT) ILIKE %s'
                params.append(f'%{filtro_valor}%')
                
        count_row = conn.execute(f"SELECT COUNT(*) as total {query_base}", tuple(params)).fetchone()
        total_registros = count_row['total'] if count_row else 0
        total_paginas = (total_registros + limite - 1) // limite if total_registros > 0 else 1
        
        order_sql = ''
        if orden:
            dir_sql = 'DESC' if direccion.lower() == 'desc' else 'ASC'
            order_sql = f' ORDER BY "{orden}" {dir_sql}'
        else:
            first_col = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position LIMIT 1", (nombre,)).fetchone()
            if first_col:
                order_sql = f' ORDER BY "{first_col["column_name"]}" ASC'
                
        sql = f'SELECT * {query_base}{order_sql} LIMIT %s OFFSET %s'
        rows = conn.execute(sql, tuple(params) + (limite, offset)).fetchall()
        
        registros = []
        for r in rows:
            row_dict = {}
            for k, v in dict(r).items():
                if isinstance(v, datetime):
                    row_dict[k] = v.isoformat()
                elif hasattr(v, 'to_eng_string'):  # Decimal
                    row_dict[k] = float(v)
                else:
                    row_dict[k] = v
            registros.append(row_dict)
            
        conn.close()
        return jsonify({
            'ok': True,
            'registros': registros,
            'total_paginas': total_paginas
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/db/tabla/<nombre>/actualizar', methods=['POST'])
@admin_required
def api_admin_db_actualizar(nombre):
    data = request.get_json() or {}
    pk_val = data.get('id')
    campo = data.get('campo')
    valor = data.get('valor')
    pk_col = data.get('pk_column', 'id')
    
    if not pk_val or not campo:
        return jsonify({'ok': False, 'error': 'id y campo requeridos'}), 400
        
    conn = get_db_connection()
    try:
        exists = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s", (nombre,)).fetchone()
        if not exists:
            conn.close()
            return jsonify({'ok': False, 'error': f'Tabla "{nombre}" no existe'}), 404
            
        col_exists = conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s", (nombre, campo)).fetchone()
        pk_exists = conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s", (nombre, pk_col)).fetchone()
        if not col_exists or not pk_exists:
            conn.close()
            return jsonify({'ok': False, 'error': 'Columna o PK inválida'}), 400
            
        prev_row = conn.execute(f'SELECT "{campo}" FROM "{nombre}" WHERE "{pk_col}" = %s', (pk_val,)).fetchone()
        valor_anterior = prev_row[campo] if prev_row else None
        
        conn.execute(f'UPDATE "{nombre}" SET "{campo}" = %s WHERE "{pk_col}" = %s', (valor, pk_val))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'valor_anterior': valor_anterior})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/db/tabla/<nombre>/insertar', methods=['POST'])
@admin_required
def api_admin_db_insertar(nombre):
    data = request.get_json() or {}
    campos = data.get('campos', {})
    if not campos:
        return jsonify({'ok': False, 'error': 'No se enviaron datos para insertar'}), 400
        
    conn = get_db_connection()
    try:
        exists = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s", (nombre,)).fetchone()
        if not exists:
            conn.close()
            return jsonify({'ok': False, 'error': f'Tabla "{nombre}" no existe'}), 404
            
        columns_list = []
        values_placeholders = []
        params = []
        for col, val in campos.items():
            col_exists = conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s", (nombre, col)).fetchone()
            if not col_exists:
                conn.close()
                return jsonify({'ok': False, 'error': f'Columna "{col}" no existe'}), 400
            columns_list.append(f'"{col}"')
            values_placeholders.append('%s')
            params.append(val)
            
        sql = f'INSERT INTO "{nombre}" ({", ".join(columns_list)}) VALUES ({", ".join(values_placeholders)})'
        conn.execute(sql, tuple(params))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/db/tabla/<nombre>/eliminar', methods=['POST'])
@admin_required
def api_admin_db_eliminar(nombre):
    data = request.get_json() or {}
    ids = data.get('ids', [])
    pk_col = data.get('pk_column', 'id')
    if not ids:
        return jsonify({'ok': False, 'error': 'No se especificaron IDs para eliminar'}), 400
        
    conn = get_db_connection()
    try:
        exists = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s", (nombre,)).fetchone()
        if not exists:
            conn.close()
            return jsonify({'ok': False, 'error': f'Tabla "{nombre}" no existe'}), 404
            
        pk_exists = conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s", (nombre, pk_col)).fetchone()
        if not pk_exists:
            conn.close()
            return jsonify({'ok': False, 'error': 'PK inválida'}), 400
            
        placeholders = ', '.join(['%s'] * len(ids))
        sql = f'DELETE FROM "{nombre}" WHERE "{pk_col}" IN ({placeholders})'
        conn.execute(sql, tuple(ids))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/admin/db/tabla/<nombre>/exportar')
@admin_required
def api_admin_db_exportar(nombre):
    filtro_columna = request.args.get('filtro_columna', '').strip()
    filtro_valor = request.args.get('filtro_valor', '').strip()
    
    conn = get_db_connection()
    try:
        exists = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s", (nombre,)).fetchone()
        if not exists:
            conn.close()
            return "Tabla no existe", 404
            
        query_base = f'FROM "{nombre}"'
        params = []
        if filtro_columna and filtro_valor:
            col_exists = conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s", (nombre, filtro_columna)).fetchone()
            if col_exists:
                query_base += f' WHERE CAST("{filtro_columna}" AS TEXT) ILIKE %s'
                params.append(f'%{filtro_valor}%')
                
        sql = f'SELECT * {query_base}'
        rows = conn.execute(sql, tuple(params)).fetchall()
        
        if not rows:
            conn.close()
            return "Sin registros", 400
            
        cols = [d[0] for d in conn.execute(f'SELECT * FROM "{nombre}" LIMIT 0').description]
        
        import csv
        from io import StringIO
        from flask import make_response
        
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(cols)
        for r in rows:
            cw.writerow([dict(r)[col] for col in cols])
            
        response = make_response(si.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=export_{nombre}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response.headers['Content-Type'] = 'text/csv'
        
        conn.close()
        return response
    except Exception as e:
        try: conn.close()
        except: pass
        return str(e), 500


# ── Deploy webhook ────────────────────────────────────────────────────────────

@bp.route('/api/webhook/deploy', methods=['POST'])
def api_webhook_render_deploy():
    try:
        data = request.get_json(silent=True) or {}
        commit_data = data.get('commit', {})
        commit = str(commit_data.get('id', 'desconocido'))[:7] if isinstance(commit_data, dict) else 'desconocido'
        msg_commit = str(commit_data.get('message', '')) if isinstance(commit_data, dict) else ''
        hora = datetime.now().strftime('%H:%M:%S')
        detalle = f"\n<i>{msg_commit}</i>" if msg_commit else ''
        enviar_notificacion_telegram(
            f"✅ <b>Deploy confirmado (PC)</b>\n"
            f"Commit: <code>{commit}</code>{detalle}\n"
            f"Hora: {hora}"
        )
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── PORTAL DE ACCESOS DIRECTOS PERSONALIZADO (MI MENU) ───────────────────────

@bp.route('/admin/mi-menu')
def admin_mi_menu():
    if 'rol' not in session or session['rol'] not in ('Administrador', 'ClienteVFP', 'Restaurante', 'Tienda', 'Vendedor'):
        return redirect(url_for('auth.admin_login'))
        
    referer = request.referrer
    if referer and '/admin/mi-menu' not in referer and ('/admin/' in referer or '/contabilidad/' in referer or '/vendedor/' in referer or '/mi-restaurante/' in referer or '/mi-tienda/' in referer):
        session['last_dashboard_url'] = referer
    
    dashboard_url = session.get('last_dashboard_url')
    if not dashboard_url:
        rol = session.get('rol')
        if rol == 'Vendedor':
            dashboard_url = '/vendedor'
        else:
            dashboard_url = '/admin/area'
            
    nombre_display = session.get('nombre', session.get('nombre_usuario', 'Usuario'))
    return render_template('mi_menu.html', 
                           nombre=nombre_display, 
                           dashboard_url=dashboard_url)


@bp.route('/api/mi-menu/items', methods=['GET'])
def api_mi_menu_items():
    if 'rol' not in session or session['rol'] not in ('Administrador', 'ClienteVFP', 'Restaurante', 'Tienda', 'Vendedor'):
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    from ..db import get_db_connection
    uid = session.get('usuario_id')
    try:
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT id, nombre, url, COALESCE(orden, 0) AS orden 
            FROM menu_shortcuts_usuario 
            WHERE usuario_id = %s 
            ORDER BY orden ASC, id ASC
        """, (uid,)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'items': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/mi-menu/item', methods=['POST'])
def api_mi_menu_item_save():
    if 'rol' not in session or session['rol'] not in ('Administrador', 'ClienteVFP', 'Restaurante', 'Tienda', 'Vendedor'):
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    from ..db import get_db_connection
    uid = session.get('usuario_id')
    data = request.get_json() or {}
    item_id = data.get('id')
    nombre = (data.get('nombre') or '').strip()
    url = (data.get('url') or '').strip()
    orden = int(data.get('orden') or 0)
    
    if not nombre or not url:
        return jsonify({'ok': False, 'error': 'El nombre y la URL son requeridos.'}), 400
        
    try:
        conn = get_db_connection()
        if item_id:
            # Update existing shortcut, verifying ownership
            conn.execute("""
                UPDATE menu_shortcuts_usuario 
                SET nombre = %s, url = %s, orden = %s 
                WHERE id = %s AND usuario_id = %s
            """, (nombre, url, orden, int(item_id), uid))
        else:
            # Insert new shortcut
            conn.execute("""
                INSERT INTO menu_shortcuts_usuario (usuario_id, nombre, url, orden)
                VALUES (%s, %s, %s, %s)
            """, (uid, nombre, url, orden))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/negocio/<int:negocio_id>/logo', methods=['POST'])
def api_negocio_logo_upload(negocio_id):
    if 'rol' not in session or session['rol'] not in ('Administrador', 'ClienteVFP', 'Restaurante', 'Tienda', 'Vendedor'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401
    
    uid = session.get('usuario_id')
    role = session.get('rol')
    tercero_id = session.get('chat_tercero_id')
    
    # Si no es administrador global, verificar si está vinculado al negocio
    if role not in ('Administrador',):
        if not tercero_id:
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        from ..db import get_db_connection
        conn = get_db_connection()
        link = conn.execute(
            "SELECT 1 FROM terceros_negocios WHERE tercero_id = %s AND negocio_id = %s AND activo = TRUE",
            (tercero_id, negocio_id)
        ).fetchone()
        conn.close()
        if not link:
            return jsonify({'ok': False, 'error': 'No tienes permisos en este negocio'}), 403
            
    if 'logo' not in request.files:
        return jsonify({'ok': False, 'error': 'No se envió ninguna imagen'}), 400
        
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'ok': False, 'error': 'Archivo vacío'}), 400
        
    # Validar formato
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
        return jsonify({'ok': False, 'error': 'Formato no permitido (solo imágenes)'}), 400
        
    try:
        from PIL import Image
        from flask import current_app
        logos_dir = os.path.join(current_app.root_path, 'static', 'logos')
        os.makedirs(logos_dir, exist_ok=True)
        
        filepath = os.path.join(logos_dir, f"{negocio_id}.png")
        img = Image.open(file.stream)
        img.save(filepath, format="PNG")
        
        return jsonify({'ok': True, 'logo_url': f"/static/logos/{negocio_id}.png"})
    except Exception as e:
        return jsonify({'ok': False, 'error': f"Error al procesar la imagen: {str(e)}"}), 500



@bp.route('/api/mi-menu/item/<int:item_id>', methods=['DELETE'])
def api_mi_menu_item_delete(item_id):
    if 'rol' not in session or session['rol'] not in ('Administrador', 'ClienteVFP', 'Restaurante', 'Tienda', 'Vendedor'):
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    from ..db import get_db_connection
    uid = session.get('usuario_id')
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM menu_shortcuts_usuario WHERE id = %s AND usuario_id = %s", (item_id, uid))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


def _tercero_de_sesion(conn, ses):
    """chat_tercero_id, o usuario_id si es un tercero valido.

    Los accesos magic-link/PIN ponen usuario_id=tercero sin chat_tercero_id
    y el portal quedaba 'Sin Empresa' (Margarita 03/11)."""
    tid = ses.get('chat_tercero_id')
    if tid:
        return tid
    uid = ses.get('usuario_id')
    if not uid:
        return None
    try:
        row = conn.execute("SELECT id FROM terceros WHERE id = %s", (uid,)).fetchone()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    return row['id'] if row else None


def _negocio_activo_de_sesion(conn, ses, tercero_id):
    """active_negocio_id, o primer negocio vinculado (molde inject_negocios_context).

    Las sesiones magic-link/PIN/SU no siempre traen negocio fijado; el contexto
    lo cura al renderizar, pero el guardian corre antes y debe resolver igual."""
    nid = ses.get('active_negocio_id')
    if nid:
        return nid
    if not tercero_id:
        return None
    try:
        row = conn.execute(
            "SELECT negocio_id AS id FROM terceros_negocios WHERE tercero_id = %s AND activo = TRUE ORDER BY negocio_id LIMIT 1",
            (tercero_id,)).fetchone()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    return row['id'] if row else None

@bp.app_context_processor
def inject_negocios_context():
    if 'usuario_id' not in session:
        return {'session_negocios': [], 'negocio_activo': None}
    
    from ..db import get_db_connection
    conn = get_db_connection()
    try:
        role = session.get('rol')
        tercero_id = _tercero_de_sesion(conn, session)
        if tercero_id and not session.get('chat_tercero_id'):
            session['chat_tercero_id'] = tercero_id
            session.modified = True
        
        negocios = []
        if role in ('Administrador',):
            # El superadmin ve todos los negocios en el sistema
            rows = conn.execute("""
                SELECT id, nombre FROM terceros 
                WHERE tipo_tercero = 'negocio' 
                ORDER BY id
            """).fetchall()
            negocios = [dict(r) for r in rows]
        else:
            # Los demás usuarios ven solo los negocios vinculados en terceros_negocios
            if tercero_id:
                rows = conn.execute("""
                    SELECT t.id, t.nombre 
                    FROM terceros_negocios tn
                    JOIN terceros t ON t.id = tn.negocio_id
                    WHERE tn.tercero_id = %s AND tn.activo = TRUE
                    ORDER BY t.id
                """, (tercero_id,)).fetchall()
                negocios = [dict(r) for r in rows]
                
        # Para cada negocio, verificar si existe su archivo de logo
        import os
        from flask import current_app
        logos_dir = os.path.join(current_app.root_path, 'static', 'logos')
        for neg in negocios:
            filename = f"{neg['id']}.png"
            if os.path.exists(os.path.join(logos_dir, filename)):
                neg['logo_url'] = f"/static/logos/{filename}"
            else:
                neg['logo_url'] = None
                
        # Determinar negocio activo
        active_id = session.get('active_negocio_id')
        active_neg = None
        if active_id:
            active_neg = next((n for n in negocios if n['id'] == active_id), None)
            
        if not active_neg and negocios:
            active_neg = negocios[0]
            session['active_negocio_id'] = active_neg['id']

        # Determinar centros de utilidad del negocio activo
        centros = []
        centro_activo = None
        if active_neg:
            try:
                c_rows = conn.execute("""
                    SELECT id, codigo, nombre, tipo, color_badge 
                    FROM centros_utilidad 
                    WHERE negocio_id = %s AND activo = TRUE 
                    ORDER BY id ASC
                """, (active_neg['id'],)).fetchall()
                centros = [dict(c) for c in c_rows]
                
                c_id = session.get('centro_utilidad_id')
                if c_id:
                    centro_activo = next((c for c in centros if str(c['id']) == str(c_id)), None)
                if not centro_activo and centros:
                    centro_activo = centros[0]
                    session['centro_utilidad_id'] = centro_activo['id']
                    session['centro_utilidad_nombre'] = centro_activo['nombre']
                    session['centro_utilidad_codigo'] = centro_activo['codigo']
            except Exception:
                pass
            
        return {
            'session_negocios': negocios,
            'negocio_activo': active_neg,
            'centros_utilidad': centros,
            'centro_activo': centro_activo
        }
    except Exception:
        return {'session_negocios': [], 'negocio_activo': None}
    finally:
        try: conn.close()
        except: pass


@bp.route('/api/session/switch-negocio/<int:negocio_id>', methods=['POST'])
def api_session_switch_negocio(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        
    role = session.get('rol')
    tercero_id = session.get('chat_tercero_id')
    
    # Validar que el usuario tenga acceso al negocio
    if role not in ('Administrador',):
        if not tercero_id:
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        from ..db import get_db_connection
        conn = get_db_connection()
        link = conn.execute(
            "SELECT 1 FROM terceros_negocios WHERE tercero_id = %s AND negocio_id = %s AND activo = TRUE",
            (tercero_id, negocio_id)
        ).fetchone()
        conn.close()
        if not link:
            return jsonify({'ok': False, 'error': 'No tienes permisos en este negocio'}), 403
            
    session['active_negocio_id'] = negocio_id
    session.pop('centro_utilidad_id', None)
    session.pop('centro_utilidad_nombre', None)
    session.pop('centro_utilidad_codigo', None)
    session.modified = True
    return jsonify({'ok': True})


@bp.route('/api/session/switch-centro-utilidad/<int:centro_id>', methods=['POST'])
def api_session_switch_centro(centro_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    session['centro_utilidad_id'] = centro_id
    try:
        from ..db import get_db_connection
        conn = get_db_connection()
        row = conn.execute("SELECT nombre, codigo FROM centros_utilidad WHERE id = %s", (centro_id,)).fetchone()
        conn.close()
        if row:
            session['centro_utilidad_nombre'] = row['nombre']
            session['centro_utilidad_codigo'] = row['codigo']
    except Exception:
        pass
    session.modified = True
    return jsonify({'ok': True})


@bp.route('/admin/permisos')
def core_gestion_permisos():
    if 'rol' not in session or session['rol'] not in ('Administrador', 'ClienteVFP', 'Restaurante', 'Tienda', 'Vendedor'):
        return redirect(url_for('auth.admin_login'))
        
    role = session.get('rol')
    tercero_id = session.get('chat_tercero_id')
    active_negocio_id = session.get('active_negocio_id')
    
    # Si no es administrador global, validar que tenga el permiso 'gestion_permisos' para el negocio activo
    if role not in ('Administrador',):
        from ..db import get_db_connection
        conn = get_db_connection()
        try:
            tercero_id = _tercero_de_sesion(conn, session)
            active_negocio_id = _negocio_activo_de_sesion(conn, session, tercero_id)
            if not active_negocio_id or not tercero_id:
                abort(403)
            has_perm = conn.execute("""
                SELECT 1 FROM permisos_terceros pt
                JOIN pantallas p ON p.id = pt.pantalla_id
                WHERE pt.tercero_id = %s AND pt.negocio_id = %s AND p.clave = 'gestion_permisos'
            """, (tercero_id, active_negocio_id)).fetchone()
            if not has_perm:
                abort(403)
        finally:
            try:
                conn.close()
            except Exception:
                pass
            
    # Obtener las pantallas que este usuario tiene derecho a asignar
    from ..db import get_db_connection
    conn = get_db_connection()
    if role in ('Administrador',):
        pantallas = conn.execute("SELECT id, nombre, clave, endpoint, icono, modulo, url_tpl, query FROM pantallas WHERE otorgable IS NOT FALSE ORDER BY orden, id").fetchall()
    else:
        pantallas = conn.execute("""
            SELECT p.id, p.nombre, p.clave, p.endpoint, p.icono, p.modulo, p.url_tpl, p.query 
            FROM permisos_terceros pt
            JOIN pantallas p ON p.id = pt.pantalla_id
            WHERE pt.tercero_id = %s AND pt.negocio_id = %s AND p.otorgable IS NOT FALSE
            ORDER BY p.orden, p.id
        """, (tercero_id, active_negocio_id)).fetchall()
    conn.close()
    
    pant_disp = []
    for p in pantallas:
        d = dict(p)
        d['icono_bi'] = _icono_bi(d.get('endpoint'))
        pant_disp.append(d)
    return render_template('gestion_permisos.html',
                           nombre=session.get('nombre', ''),
                           pantallas_disponibles=pant_disp)


@bp.route('/api/permisos/buscar-terceros')
def api_permisos_buscar_terceros():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'results': []})
        
    from ..db import get_db_connection
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT id, nombre, telefono 
        FROM terceros 
        WHERE (nombre ILIKE %s OR telefono ILIKE %s) 
          AND (tipo_tercero IS NULL OR tipo_tercero NOT IN ('negocio', 'admin'))
        LIMIT 15
    """, (f"%{q}%", f"%{q}%")).fetchall()
    conn.close()
    
    return jsonify({'results': [dict(r) for r in rows]})


@bp.route('/api/permisos/tercero/<int:tercero_id>/negocio/<int:negocio_id>')
def api_permisos_obtener(tercero_id, negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        
    role = session.get('rol')
    if role not in ('Administrador',):
        from ..db import get_db_connection
        conn = get_db_connection()
        caller_tercero_id = _tercero_de_sesion(conn, session)
        if not caller_tercero_id:
            conn.close()
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        link = conn.execute(
            "SELECT 1 FROM terceros_negocios WHERE tercero_id = %s AND negocio_id = %s AND activo = TRUE",
            (caller_tercero_id, negocio_id)
        ).fetchone()
        conn.close()
        if not link:
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
            
    from ..db import get_db_connection
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT pantalla_id FROM permisos_terceros 
        WHERE tercero_id = %s AND negocio_id = %s
    """, (tercero_id, negocio_id)).fetchall()
    conn.close()
    
    return jsonify({
        'ok': True,
        'pantallas_autorizadas': [r['pantalla_id'] for r in rows]
    })


@bp.route('/api/permisos/guardar', methods=['POST'])
def api_permisos_guardar():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        
    data = request.get_json()
    target_tercero_id = data.get('tercero_id')
    negocio_id = data.get('negocio_id')
    pantallas_deseadas = data.get('pantallas', [])
    
    if not target_tercero_id or not negocio_id:
        return jsonify({'ok': False, 'error': 'Datos faltantes'}), 400
        
    role = session.get('rol')
    caller_tercero_id = session.get('chat_tercero_id')
    
    from ..db import get_db_connection
    conn = get_db_connection()
    try:
        if role not in ('Administrador',):
            caller_tercero_id = _tercero_de_sesion(conn, session)
            if not caller_tercero_id:
                conn.close()
                return jsonify({'ok': False, 'error': 'No autorizado'}), 403
                
            # 1. Validar que el delegador tiene acceso al negocio y al permiso 'gestion_permisos'
            link = conn.execute(
                "SELECT 1 FROM terceros_negocios WHERE tercero_id = %s AND negocio_id = %s AND activo = TRUE",
                (caller_tercero_id, negocio_id)
            ).fetchone()
            if not link:
                conn.close()
                return jsonify({'ok': False, 'error': 'No autorizado en este negocio'}), 403
                
            has_perm = conn.execute("""
                SELECT 1 FROM permisos_terceros pt
                JOIN pantallas p ON p.id = pt.pantalla_id
                WHERE pt.tercero_id = %s AND pt.negocio_id = %s AND p.clave = 'gestion_permisos'
            """, (caller_tercero_id, negocio_id)).fetchone()
            if not has_perm:
                conn.close()
                return jsonify({'ok': False, 'error': 'No tienes permisos de gestión de accesos'}), 403
                
            # 2. Validar que el delegador no esté asignando pantallas que él mismo no posee
            mis_pantallas = conn.execute("""
                SELECT pantalla_id FROM permisos_terceros 
                WHERE tercero_id = %s AND negocio_id = %s
            """, (caller_tercero_id, negocio_id)).fetchall()
            mis_pantallas_ids = {r['pantalla_id'] for r in mis_pantallas}
            
            for p_id in pantallas_deseadas:
                if p_id not in mis_pantallas_ids:
                    conn.close()
                    return jsonify({'ok': False, 'error': f'No puedes otorgar la pantalla {p_id} porque no la posees'}), 403
                    
        # 3. Guardar permisos
        # Asegurar vinculación en terceros_negocios
        conn.execute("""
            INSERT INTO terceros_negocios (tercero_id, negocio_id, activo)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (tercero_id, negocio_id) DO UPDATE SET activo = TRUE
        """, (target_tercero_id, negocio_id))
        
        # Borrar permisos anteriores para este negocio
        if role in ('Administrador',):
            conn.execute("""
                DELETE FROM permisos_terceros 
                WHERE tercero_id = %s AND negocio_id = %s
            """, (target_tercero_id, negocio_id))
        else:
            # El delegador de negocio solo borra los permisos que él mismo posee
            mis_pantallas = conn.execute("""
                SELECT pantalla_id FROM permisos_terceros 
                WHERE tercero_id = %s AND negocio_id = %s
            """, (caller_tercero_id, negocio_id)).fetchall()
            mis_pantallas_ids = {r['pantalla_id'] for r in mis_pantallas}
            
            conn.execute("""
                DELETE FROM permisos_terceros 
                WHERE tercero_id = %s AND negocio_id = %s AND pantalla_id IN %s
            """, (target_tercero_id, negocio_id, tuple(mis_pantallas_ids) if mis_pantallas_ids else (-1,)))
            
        # Insertar nuevos
        for p_id in pantallas_deseadas:
            conn.execute("""
                INSERT INTO permisos_terceros (tercero_id, negocio_id, pantalla_id, otorgado_por)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tercero_id, negocio_id, pantalla_id) DO NOTHING
            """, (target_tercero_id, negocio_id, p_id, caller_tercero_id or target_tercero_id))
            
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


def _su_puede_simular(conn, ses, tercero_id, negocio_id):
    """Indica si la sesion puede entrar como (tercero, negocio)."""
    if ses.get('_su_original'):
        return False, 'Ya estas simulando: sal primero'
    rol = ses.get('rol')
    yo = _tercero_de_sesion(conn, ses)
    if rol == 'ClienteVFP':
        return False, 'Cuenta VFP sin acceso'
    es_super = rol in ('Administrador',)
    if not es_super:
        if not yo:
            return False, 'No autorizado'
        link = conn.execute(
            'SELECT 1 FROM terceros_negocios WHERE tercero_id = %s AND negocio_id = %s AND activo = TRUE',
            (yo, negocio_id)).fetchone()
        if not link:
            return False, 'No autorizado en este negocio'
        gest = conn.execute("""
            SELECT 1 FROM permisos_terceros pt
            JOIN pantallas p ON p.id = pt.pantalla_id
            WHERE pt.tercero_id = %s AND pt.negocio_id = %s AND p.clave = 'gestion_permisos'
        """, (yo, negocio_id)).fetchone()
        if not gest:
            return False, 'No tienes gestion de accesos'
    tgt = conn.execute(
        'SELECT id, nombre, telefono FROM terceros WHERE id = %s', (tercero_id,)).fetchone()
    if not tgt:
        return False, 'Tercero inexistente'
    vlink = conn.execute(
        'SELECT 1 FROM terceros_negocios WHERE tercero_id = %s AND negocio_id = %s AND activo = TRUE',
        (tercero_id, negocio_id)).fetchone()
    if not vlink:
        return False, 'Sin vinculo con el negocio'
    if not es_super:
        mias = {r['pantalla_id'] for r in conn.execute(
            'SELECT pantalla_id FROM permisos_terceros WHERE tercero_id = %s AND negocio_id = %s',
            (yo, negocio_id)).fetchall()}
        suyas = {r['pantalla_id'] for r in conn.execute(
            'SELECT pantalla_id FROM permisos_terceros WHERE tercero_id = %s AND negocio_id = %s',
            (tercero_id, negocio_id)).fetchall()}
        if not suyas <= mias:
            return False, 'No puedes simular accesos que no posees'
    return True, ''


@bp.route('/api/su/entrar', methods=['POST'])
def api_su_entrar():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    try:
        tercero_id = int(data.get('tercero_id') or 0)
        negocio_id = int(data.get('negocio_id') or 0)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Datos invalidos'}), 400
    if not tercero_id or not negocio_id:
        return jsonify({'ok': False, 'error': 'Datos faltantes'}), 400
    from ..db import get_db_connection
    conn = get_db_connection()
    try:
        puede, why = _su_puede_simular(conn, session, tercero_id, negocio_id)
        if not puede:
            conn.close()
            return jsonify({'ok': False, 'error': why}), 403
        tgt = conn.execute(
            'SELECT id, nombre, telefono FROM terceros WHERE id = %s', (tercero_id,)).fetchone()
        r = conn.execute('SELECT 1 FROM restaurantes WHERE tercero_id = %s LIMIT 1',
                       (negocio_id,)).fetchone()
        if r:
            rol_sim = 'Restaurante'
        else:
            t = conn.execute('SELECT 1 FROM tiendas WHERE tercero_id = %s LIMIT 1',
                           (negocio_id,)).fetchone()
            rol_sim = 'Tienda' if t else 'Vendedor'
    finally:
        try:
            conn.close()
        except Exception:
            pass
    session['_su_original'] = {
        'usuario_id': session.get('usuario_id'),
        'rol': session.get('rol'),
        'chat_tercero_id': session.get('chat_tercero_id'),
        'nombre': session.get('nombre', ''),
        'telefono': session.get('telefono', ''),
        'active_negocio_id': session.get('active_negocio_id'),
        'dispositivo_id': session.get('dispositivo_id', ''),
    }
    session['usuario_id'] = tgt['id']
    session['nombre'] = tgt['nombre']
    session['telefono'] = tgt['telefono'] or ''
    session['rol'] = rol_sim
    session.pop('chat_tercero_id', None)
    session['active_negocio_id'] = negocio_id
    session.modified = True
    return jsonify({'ok': True, 'nombre': tgt['nombre']})


@bp.route('/api/su/salir', methods=['POST'])
def api_su_salir():
    orig = session.get('_su_original')
    if not orig:
        return jsonify({'ok': False, 'error': 'No estabas simulando'}), 400
    if orig.get('usuario_id') is None:
        session.pop('usuario_id', None)
    else:
        session['usuario_id'] = orig['usuario_id']
    session['rol'] = orig.get('rol')
    if orig.get('chat_tercero_id'):
        session['chat_tercero_id'] = orig['chat_tercero_id']
    else:
        session.pop('chat_tercero_id', None)
    session['nombre'] = orig.get('nombre', '')
    session['telefono'] = orig.get('telefono', '')
    session['active_negocio_id'] = orig.get('active_negocio_id')
    session['dispositivo_id'] = orig.get('dispositivo_id', '')
    session.pop('_su_original', None)
    session.modified = True
    return jsonify({'ok': True})


@bp.after_app_request
def _inyectar_cinta_su_global(response):
    """Cinta 'Volver a mi sesion' en TODA pagina HTML durante simulacion.

    Caso Rafa 04/11 pm: atrapado en cuerpo simulado dentro de pagina
    standalone (caja/permisos) sin cinta. Mismo molde que el globo del
    chat: solo inyecta si falta (portal/inicio/base traen la suya).
    """
    try:
        if request.method != 'GET':
            return response
        if not session.get('_su_original'):
            return response
        p = request.path or ''
        if (p.startswith('/api/') or p.startswith('/static/') or
                p.startswith('/chat') or p.startswith('/login') or
                p.startswith('/admin/login') or request.args.get('embed') == '1'):
            return response
        if response.direct_passthrough:
            return response
        ctype = response.content_type or ''
        if 'text/html' not in ctype.lower():
            return response
        html = response.get_data(as_text=True)
        if '</body>' not in html or 'Volver a mi sesi' in html:
            return response
        import html as _h
        nombre = _h.escape(session.get('nombre', '') or '', quote=True)
        cinta = (
            '<style>body{padding-bottom:44px !important;}</style>'
            '<div id="tuctuc-su-cinta" style="position:fixed;bottom:0;left:0;right:0;'
            'background:#0f172a;color:#fff;font-size:12px;padding:8px 16px;'
            'display:flex;align-items:center;justify-content:center;gap:8px;'
            'z-index:2000;font-family:system-ui,sans-serif;">'
            'Viendo como <strong>' + nombre + '</strong> '
            '<button type="button" onclick="suSalir()" style="text-decoration:underline;'
            'background:transparent;border:0;color:#fff;cursor:pointer;font-size:12px;'
            'padding:0;">Volver a mi sesi\u00f3n</button></div>'
            '<script>function suSalir(){fetch(\'/api/su/salir\',{method:\'POST\'})'
            '.then(function(r){return r.json();})'
            '.then(function(d){if(d.ok){window.location.href=\'/portal\';}'
            'else{alert(\'Error: \'+(d.error||\'desconocido\'));}});}</script>'
        )
        response.set_data(html.replace('</body>', cinta + '\n</body>', 1))
    except Exception:
        pass
    return response


@bp.before_app_request
def check_dynamic_permissions():
    if 'usuario_id' not in session:
        return

    endpoint = request.endpoint
    if not endpoint:
        return
    # ClienteVFP: solo area VFP (admin_agent) + auth; resto de la web negado
    if session.get('rol') == 'ClienteVFP':
        if endpoint.startswith('admin_agent.') or endpoint.startswith('auth.') or endpoint == 'static':
            return
        if (request.is_json or
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                'application/json' in request.headers.get('Accept', '')):
            return jsonify({'ok': False, 'error': 'Cuenta VFP sin acceso web'}), 403
        abort(403)

    # Verificar si este endpoint corresponde a una pantalla registrada
    conn = get_db_connection()
    try:
        pantalla = conn.execute(
            "SELECT id, clave, nombre FROM pantallas WHERE endpoint = %s AND otorgable IS NOT FALSE LIMIT 1",
            (endpoint,)
        ).fetchone()

        if not pantalla:
            return

        # Excepción temporal: Inventario permanece accesible mientras se define su autorización.
        # Visor de manuales: se auto-chequea por slug (anonimo = publico, como antes).
        if endpoint in ('inventarios.admin_inventario', 'inventarios.admin_inventario_fisico',
                        'core.core_ver_manual'):
            return

        # 1. Superadmin bypass completo
        role = session.get('rol')
        if role in ('Administrador',):
            return

        # Tercero/negocio con respaldo magic-link/PIN/SU (la sesion fiel no trae chat_tercero_id)
        tercero_id = _tercero_de_sesion(conn, session)
        negocio_id = _negocio_activo_de_sesion(conn, session, tercero_id)

        if not tercero_id or not negocio_id:
            abort(403)

        # 2. Consultar si tiene el permiso asignado
        permiso = conn.execute("""
            SELECT 1 FROM permisos_terceros pt JOIN pantallas p ON p.id = pt.pantalla_id
            WHERE pt.tercero_id = %s AND pt.negocio_id = %s AND p.endpoint = %s
        """, (tercero_id, negocio_id, endpoint)).fetchone()

        if permiso:
            return

        # 3. Periodo de gracia para usuarios existentes (Tercero ID <= 107)
        if tercero_id <= 107:
            return

        abort(403)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _url_pantalla(fila, negocio_id, slug):
    """URL de una fila del catalogo (delega al motor)."""
    from ..buscador_motor import _url_fila
    return _url_fila(fila, negocio_id, slug)


def _asegurar_pantallas_catalogo(conn):
    """Crea/extiende pantallas y siembra el catalogo unico (omni+menu+otorgar)."""
    from ..buscador_motor import _CATALOGO_PANTALLAS, _SUGERIDOS, _MIGRAR_GRANTS
    import json as _json
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pantallas (
            id SERIAL PRIMARY KEY,
            nombre TEXT,
            clave TEXT,
            endpoint TEXT,
            icono TEXT
        )
        """)
    for _col, _typ in (('modulo', 'TEXT'), ('query', 'TEXT'), ('url_tpl', 'TEXT'),
                       ('keywords', 'TEXT'), ('orden', 'INTEGER DEFAULT 0'),
                       ('otorgable', 'BOOLEAN DEFAULT TRUE'),
                       ('sugerido', 'BOOLEAN DEFAULT FALSE')):
        conn.execute(f"ALTER TABLE pantallas ADD COLUMN IF NOT EXISTS {_col} {_typ}")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_pantallas_clave ON pantallas (clave)")
    conn.execute("UPDATE pantallas SET otorgable = TRUE WHERE otorgable IS NULL")
    conn.execute("UPDATE pantallas SET sugerido = FALSE WHERE sugerido IS NULL")
    conn.execute("UPDATE pantallas SET orden = 9000 + id WHERE orden IS NULL OR orden = 0")
    for (_clave, _nombre, _ep, _icono, _mod, _q, _tpl, _kws, _ord, _ot) in _CATALOGO_PANTALLAS:
        _k = _json.dumps(_kws, ensure_ascii=False)
        _sug = _clave in _SUGERIDOS
        _por_clave = conn.execute(
            "SELECT 1 FROM pantallas WHERE clave = %s LIMIT 1", (_clave,)).fetchone()
        if _q:
            _w = "endpoint = %s AND query = %s"
            _wp = (_ep, _q)
        else:
            _w = "endpoint = %s AND (query IS NULL OR query = '')"
            _wp = (_ep,)
        if _por_clave:
            # Autoritativo por clave (repara endpoint/query cruzados)
            conn.execute(
                """UPDATE pantallas SET nombre = %s, endpoint = %s, icono = %s, modulo = %s,
                          query = %s, url_tpl = %s, keywords = %s, orden = %s, sugerido = %s
                   WHERE clave = %s""",
                (_nombre, _ep, _icono, _mod, _q, _tpl, _k, _ord, _sug, _clave))
        else:
            _row = conn.execute(
                "SELECT id FROM pantallas WHERE " + _w + " ORDER BY id LIMIT 1", _wp).fetchone()
            if _row:
                # Autoritativo por endpoint (unifica clave; respeta otorgable)
                conn.execute(
                    """UPDATE pantallas SET clave = %s, nombre = %s, modulo = %s, url_tpl = %s,
                              keywords = %s, icono = %s, orden = %s, sugerido = %s
                       WHERE id = %s""",
                    (_clave, _nombre, _mod, _tpl, _k, _icono, _ord, _sug, _row['id']))
            else:
                conn.execute(
                    """INSERT INTO pantallas (clave, nombre, endpoint, icono, modulo, query, url_tpl,
                                              keywords, orden, otorgable, sugerido)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (clave) DO NOTHING""",
                    (_clave, _nombre, _ep, _icono, _mod, _q, _tpl, _k, _ord, _ot, _sug))
        conn.execute(
            """DELETE FROM pantallas WHERE """ + _w + """
                AND clave IS DISTINCT FROM %s
                AND NOT EXISTS (SELECT 1 FROM permisos_terceros WHERE pantalla_id = pantallas.id)""",
            tuple(_wp) + (_clave,))

    for (_viejo_ep, _nueva_clave) in _MIGRAR_GRANTS:
        _sid = conn.execute(
            "SELECT id FROM pantallas WHERE clave = %s LIMIT 1", (_nueva_clave,)).fetchone()
        if not _sid:
            continue
        for _v in conn.execute(
                "SELECT id FROM pantallas WHERE endpoint = %s", (_viejo_ep,)).fetchall() or []:
            if _v['id'] == _sid['id']:
                continue
            conn.execute(
                """DELETE FROM permisos_terceros WHERE pantalla_id = %s
                   AND EXISTS (SELECT 1 FROM permisos_terceros x
                               WHERE x.pantalla_id = %s AND x.tercero_id = permisos_terceros.tercero_id
                               AND x.negocio_id = permisos_terceros.negocio_id)""",
                (_v['id'], _sid['id']))
            conn.execute(
                "UPDATE permisos_terceros SET pantalla_id = %s WHERE pantalla_id = %s",
                (_sid['id'], _v['id']))
        conn.execute(
            """DELETE FROM pantallas WHERE endpoint = %s AND id <> %s
               AND NOT EXISTS (SELECT 1 FROM permisos_terceros WHERE pantalla_id = pantallas.id)""",
            (_viejo_ep, _sid['id']))
    try:
        conn.commit()
    except Exception:
        pass

def _pantallas_de_sesion(conn, ses):
    """Pantallas autorizadas del (tercero, negocio) en sesion.

    Misma fuente para /inicio y desk. Tercero con respaldo magic-link/PIN
    (_tercero_de_sesion); superadmin ve el catalogo completo.
    Devuelve (filas, slug_negocio, negocio_id)."""
    role = ses.get('rol')
    tercero_id = _tercero_de_sesion(conn, ses)
    active_id = ses.get('active_negocio_id')
    slug = None
    if active_id:
        r = conn.execute("SELECT slug FROM restaurantes WHERE tercero_id = %s LIMIT 1", (active_id,)).fetchone()
        if r:
            slug = r['slug']
        else:
            t = conn.execute("SELECT slug FROM tiendas WHERE tercero_id = %s LIMIT 1", (active_id,)).fetchone()
            if t:
                slug = t['slug']
    if role in ('Administrador',):
        rows = conn.execute("SELECT id, nombre, clave, endpoint, icono, modulo, url_tpl, query FROM pantallas WHERE otorgable IS NOT FALSE ORDER BY orden, id").fetchall()
    elif tercero_id and active_id:
        rows = conn.execute("""
                SELECT p.id, p.nombre, p.clave, p.endpoint, p.icono, p.modulo, p.url_tpl, p.query
                FROM permisos_terceros pt
                JOIN pantallas p ON p.id = pt.pantalla_id
                WHERE pt.tercero_id = %s AND pt.negocio_id = %s AND p.otorgable IS NOT FALSE
                ORDER BY p.orden, p.id
            """, (tercero_id, active_id)).fetchall()
    else:
        rows = []
    fuera = []
    for r in rows:
        d = dict(r)
        d['icono_bi'] = _icono_bi(d.get('endpoint'))
        fuera.append(d)
    return fuera, slug, active_id

_SECCIONES_MENU = {
    'inventarios': 'Inventario',
    'contabilidad': 'Contabilidad',
    'tiendas': 'Ventas',
    'restaurantes': 'Ventas',
    'crm': 'Comercial',
    'core': 'General',
    'agenda': 'General',
    'auth': 'General',
    'admin_agent_bp': 'Administracion',
}


_ICONOS_MENU = {
    'inventarios': 'bi-box-seam',
    'contabilidad': 'bi-calculator',
    'tiendas': 'bi-shop',
    'restaurantes': 'bi-cup-hot',
    'crm': 'bi-people',
    'agenda': 'bi-calendar-check',
    'core': 'bi-grid',
    'auth': 'bi-key',
    'admin_agent_bp': 'bi-clipboard-data',
    'rockola': 'bi-music-note-beamed',
    'domotica': 'bi-lightbulb',
}


def _icono_bi(endpoint):
    """Icono corporativo (bootstrap-icons) segun el modulo del endpoint."""
    return _ICONOS_MENU.get((endpoint or '').split('.')[0], 'bi-grid')


def _agrupar_por_modulo(pantallas):
    """Agrupa pantallas por seccion del lateral (respeta orden de llegada)."""
    grupos = {}
    orden = []
    for p in pantallas:
        pref = (p.get('endpoint') or '').split('.')[0]
        mod = p.get('modulo') or _SECCIONES_MENU.get(pref, (pref or 'general').replace('_', ' ').title())
        if mod not in grupos:
            grupos[mod] = []
            orden.append(mod)
        grupos[mod].append(p)
    return [{'modulo': m, 'items': grupos[m]} for m in orden]


@bp.route('/inicio')
def colaborador_inicio():
    if 'usuario_id' not in session and 'rol' not in session:
        return redirect(url_for('auth.admin_login'))
        
    nombre = session.get('nombre', '')

    from ..db import get_db_connection
    conn = get_db_connection()
    pantallas_autorizadas, slug, active_id = _pantallas_de_sesion(conn, session)
    conn.close()

    for d in pantallas_autorizadas:
        d['resolved_url'] = _url_pantalla(d, active_id, slug)

    return render_template('inicio.html', 
                           nombre=nombre,
                           pantallas_autorizadas=pantallas_autorizadas)


@bp.route('/portal')
def colaborador_portal():
    if 'usuario_id' not in session and 'rol' not in session:
        return redirect(url_for('auth.entrar'))
    nombre = session.get('nombre', '')
    from ..db import get_db_connection
    conn = get_db_connection()
    pantallas_autorizadas, slug, active_id = _pantallas_de_sesion(conn, session)
    conn.close()
    for d in pantallas_autorizadas:
        d['resolved_url'] = _url_pantalla(d, active_id, slug)
    menu_secciones = _agrupar_por_modulo(pantallas_autorizadas)
    return render_template('portal.html', nombre=nombre,
                           pantallas_autorizadas=pantallas_autorizadas,
                           menu_secciones=menu_secciones)


@bp.route('/admin/pantallas-catalogo')
def core_pantallas_catalogo():
    if 'rol' not in session or session['rol'] not in ('Administrador',):
        abort(403)
        
    from ..db import get_db_connection
    conn = get_db_connection()
    rows = conn.execute("SELECT id, nombre, clave, endpoint, icono FROM pantallas ORDER BY id").fetchall()
    conn.close()
    
    return render_template('pantallas_catalogo.html', 
                           pantallas=[dict(r) for r in rows])


# ── BUSCADOR OMNIBOX Y VISOR DE MANUALES ─────────────────────────────────────

@bp.route('/docs/<path:manual_slug>')
def core_ver_manual(manual_slug):
    import os
    from ..buscador_motor import MANUALES_MAPA
    
    if 'usuario_id' in session and session.get('rol') != 'Administrador':
        from ..db import get_db_connection as _g2
        _cx = _g2()
        try:
            _tid = _tercero_de_sesion(_cx, session)
            _neg = _negocio_activo_de_sesion(_cx, session, _tid)
            if not _tid or not _neg:
                abort(403)
            _pm = _cx.execute(
                """SELECT 1 FROM permisos_terceros pt JOIN pantallas p ON p.id = pt.pantalla_id
                   WHERE pt.tercero_id = %s AND pt.negocio_id = %s AND p.clave = %s""",
                (_tid, _neg, 'manual_' + manual_slug)).fetchone()
            if not _pm and _tid > 107:
                abort(403)
        finally:
            try:
                _cx.close()
            except Exception:
                pass
    archivo_info = MANUALES_MAPA.get(manual_slug)
    if not archivo_info:
        nombre_archivo = f"{manual_slug}_usuario.md"
        titulo_doc = manual_slug.replace('-', ' ').title()
    else:
        nombre_archivo = archivo_info[0]
        titulo_doc = archivo_info[1]
        
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    docs_path = os.path.join(base_dir, 'docs', 'manuales', nombre_archivo)
    if not os.path.exists(docs_path):
        dev_docs = os.path.join(os.path.expanduser('~'), 'Documents', 'docs', 'manuales', 'tuctuc', nombre_archivo)
        if os.path.exists(dev_docs):
            docs_path = dev_docs
        else:
            return "Manual no encontrado", 404
            
    try:
        with open(docs_path, encoding='utf-8') as f:
            contenido_md = f.read()
    except Exception as e:
        return f"Error al leer manual: {e}", 500
        
    back_url = request.referrer or '/inicio'
    return render_template('docs_viewer.html',
                           titulo=f"{titulo_doc} — Manual de Usuario",
                           tipo_badge="Manual de Usuario",
                           contenido_md=contenido_md,
                           fecha="2026-10-26",
                           back_url=back_url)


def _manuales_otorgados(conn, ses):
    """Slugs de manuales otorgados al (tercero, negocio). None = todos."""
    if ses.get('rol') == 'Administrador':
        return None
    tercero_id = _tercero_de_sesion(conn, ses)
    negocio_id = ses.get('active_negocio_id')
    if not tercero_id or not negocio_id:
        return set()
    rows = conn.execute(r"""
        SELECT p.query FROM permisos_terceros pt
        JOIN pantallas p ON p.id = pt.pantalla_id
        WHERE pt.tercero_id = %s AND pt.negocio_id = %s AND p.clave LIKE 'manual\_%%'
    """, (tercero_id, negocio_id)).fetchall()
    return {r['query'][4:] for r in rows if (r['query'] or '').startswith('doc=')}


def _endpoints_otorgados(conn, ses):
    """Endpoints otorgados al (tercero, negocio) en sesion. None = todos."""
    if ses.get('rol') == 'Administrador':
        return None
    tercero_id = _tercero_de_sesion(conn, ses)
    negocio_id = ses.get('active_negocio_id')
    if not tercero_id or not negocio_id:
        return set()
    rows = conn.execute("""
        SELECT p.endpoint FROM permisos_terceros pt
        JOIN pantallas p ON p.id = pt.pantalla_id
        WHERE pt.tercero_id = %s AND pt.negocio_id = %s
    """, (tercero_id, negocio_id)).fetchall()
    return {r['endpoint'] for r in rows if r['endpoint']}

@bp.route('/api/buscador/omni', methods=['GET'])
def api_buscador_omni():
    from ..buscador_motor import buscar_omni
    q = request.args.get('q', '').strip()
    negocio_id = request.args.get('negocio_id') or session.get('active_negocio_id')
    slug = session.get('negocio_slug')
    if not slug and negocio_id:
        from ..db import get_db_connection
        try:
            _conn = get_db_connection()
            _r = _conn.execute(
                "SELECT slug FROM restaurantes WHERE tercero_id = %s LIMIT 1",
                (negocio_id,)).fetchone()
            if _r:
                slug = _r['slug']
            else:
                _t = _conn.execute(
                    "SELECT slug FROM tiendas WHERE tercero_id = %s LIMIT 1",
                    (negocio_id,)).fetchone()
                if _t:
                    slug = _t['slug']
            _conn.close()
        except Exception:
            pass

    otorgados = None
    manuales = None
    if 'usuario_id' in session and session.get('rol') != 'Administrador':
        from ..db import get_db_connection
        try:
            _c0 = get_db_connection()
            try:
                otorgados = _endpoints_otorgados(_c0, session)
            finally:
                _c0.close()
        except Exception:
            otorgados = set()
        try:
            _c1 = get_db_connection()
            try:
                manuales = _manuales_otorgados(_c1, session)
            finally:
                _c1.close()
        except Exception:
            manuales = set()
    res = buscar_omni(q, negocio_id=negocio_id, slug=slug, otorgados=otorgados,
                      manuales_otorgados=manuales)
    datos = []
    extras = {'sueltos': [], 'sueltos_total': 0}
    if negocio_id and len(q) >= 2:
        from ..buscador_motor import buscar_datos_producto, buscar_sueltos
        from ..db import get_db_connection
        try:
            _c2 = get_db_connection()
            try:
                datos = buscar_datos_producto(_c2, q, negocio_id, slug)
                if datos:
                    _s = buscar_sueltos(_c2, negocio_id)
                    extras = {'sueltos': _s['items'], 'sueltos_total': _s['total']}
            finally:
                _c2.close()
        except Exception:
            datos = []
    res['datos'] = datos
    res['extras'] = extras
    return jsonify(res)

@bp.route('/api/buscador/voz', methods=['POST'])
def api_buscador_voz():
    from flask import Response
    import hashlib
    import tempfile
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    d = request.get_json(force=True, silent=True) or {}
    texto = (d.get('texto') or '').strip()
    voz_id = (d.get('voz') or 'salome').strip().lower()
    VOCES = {'salome': ('es-CO-SalomeNeural', '+50%'),
             'gonzalo': ('es-CO-GonzaloNeural', '+50%')}
    if voz_id not in VOCES:
        return jsonify({'ok': False, 'error': 'voz no válida'}), 400
    if not texto or len(texto) > 400:
        return jsonify({'ok': False, 'error': 'texto vacío o muy largo'}), 400
    voz, vol = VOCES[voz_id]
    key = hashlib.sha1('|'.join((voz, vol, texto)).encode('utf-8')).hexdigest()
    cdir = os.path.join(tempfile.gettempdir(), 'tuctuc_voz_cache')
    try:
        os.makedirs(cdir, exist_ok=True)
    except OSError:
        pass
    path = os.path.join(cdir, key + '.mp3')
    if not os.path.exists(path):
        try:
            import edge_tts
        except ImportError:
            return jsonify({'ok': False, 'error': 'voz no disponible en el servidor'}), 503
        try:
            import asyncio
            asyncio.run(edge_tts.Communicate(texto, voz, volume=vol).save(path))
        except Exception:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
            return jsonify({'ok': False, 'error': 'no se pudo sintetizar'}), 502
        try:
            fs = sorted((os.path.join(cdir, f) for f in os.listdir(cdir)
                         if f.endswith('.mp3')), key=lambda p: os.path.getmtime(p))
            for viejo in fs[:-200]:
                try:
                    os.remove(viejo)
                except OSError:
                    pass
        except OSError:
            pass
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError:
        return jsonify({'ok': False, 'error': 'no se pudo leer el audio'}), 500
    return Response(data, mimetype='audio/mpeg')

