import os
import re
import unicodedata
import uuid
from datetime import datetime  # noqa

import requests as http_requests
from flask import (Blueprint, jsonify, redirect, render_template,
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
    if session.get('rol') == 'Administrador':
        return redirect(url_for('auth.admin_area'))
    return redirect(url_for('auth.admin_login'))


@bp.route('/api/version')
def api_version():
    import subprocess
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    commit = ''
    commit_source = ''
    commit_error = ''

    for env_name in ('GIT_COMMIT', 'COMMIT_SHA', 'SOURCE_VERSION', 'RENDER_GIT_COMMIT', 'HEROKU_SLUG_COMMIT'):
        env_commit = os.environ.get(env_name, '').strip()
        if env_commit:
            commit = env_commit[:7]
            commit_source = env_name
            break

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
    return render_template('admin_menu.html')


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
        conn.close()
        return jsonify({
            'ok': True,
            'columnas': [dict(c) for c in columnas],
            'total': count['total'] if count else 0,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


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
