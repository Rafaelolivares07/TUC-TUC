from functools import wraps
from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, flash, jsonify)
from ..db import get_db_connection

bp = Blueprint('auth', __name__)


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        rol = session.get('rol')
        uid = session.get('usuario_id')
        if not uid and not rol:
            if (request.is_json or
                    request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                    'application/json' in request.headers.get('Accept', '')):
                return jsonify({'ok': False, 'error': 'No autenticado'}), 401
            return redirect(url_for('auth.admin_login'))
        if rol not in ('Administrador', 'ClienteVFP', 'Restaurante', 'Tienda', 'Vendedor'):
            if (request.is_json or
                    request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                    'application/json' in request.headers.get('Accept', '')):
                return jsonify({'ok': False, 'error': 'Acceso denegado'}), 403
            return redirect('/inicio')
        return f(*args, **kwargs)
    return wrapper


def solo_admin(f):
    """Requiere rol Administrador (no ClienteVFP)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('rol') != 'Administrador':
            if (request.is_json or
                    request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
                return jsonify({'ok': False, 'error': 'Acceso denegado'}), 403
            flash('Acceso denegado. Se requiere ser Administrador.', 'danger')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return wrapper


@bp.route('/admin')
def admin_redirect():
    if session.get('usuario_id') or session.get('rol'):
        return redirect('/inicio')
    return redirect(url_for('auth.admin_login'))


@bp.route('/admin/login', methods=['GET'])
def admin_login():
    if session.get('usuario_id') or session.get('rol'):
        return redirect('/inicio')
    return render_template('admin_login.html')


@bp.route('/admin/login', methods=['POST'])
def admin_login_post():
    return _procesar_login('/inicio', 'auth.admin_login')


@bp.route('/entrar', methods=['GET'])
def entrar():
    if session.get('usuario_id') or session.get('rol'):
        return redirect('/')
    return render_template('admin_login.html', form_action='/entrar')


@bp.route('/entrar', methods=['POST'])
def entrar_post():
    return _procesar_login('/', 'auth.entrar')


def _procesar_login(ok_url, fail_endpoint):
    usuario = request.form.get('usuario', '').strip()
    password = request.form.get('password', '').strip()

    if not usuario or not password:
        flash('Por favor completa todos los campos', 'danger')
        return redirect(url_for(fail_endpoint))

    conn = get_db_connection()
    try:
        admin = conn.execute("""
            SELECT * FROM usuarios
            WHERE usuario = %s AND password = %s
              AND rol IN ('Administrador', 'ClienteVFP')
        """, (usuario, password)).fetchone()

        if admin:
            tercero = conn.execute(
                "SELECT id FROM terceros WHERE tipo_tercero = 'admin' AND nombre = %s LIMIT 1",
                (admin['nombre'],)
            ).fetchone()
            if not tercero:
                tercero = conn.execute(
                    """INSERT INTO terceros (nombre, tipo_tercero)
                       VALUES (%s, 'admin') RETURNING id""",
                    (admin['nombre'],)
                ).fetchone()
                conn.commit()

            session.clear()
            session['usuario_id']      = admin['id']
            session['chat_tercero_id'] = tercero['id']
            session['nombre']          = admin['nombre']
            session['rol']             = admin['rol']
            session['dispositivo_id']  = admin.get('dispositivo_id', '')
            session.permanent          = True
            session.modified           = True
            if admin['rol'] == 'ClienteVFP':
                return redirect(url_for('admin_agent.consultas_page'))
            return redirect(ok_url)
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
            return redirect(url_for(fail_endpoint))
    finally:
        conn.close()


@bp.route('/admin/area')
@admin_required
def admin_area():
    return redirect('/inicio')


@bp.route('/admin/logout')
@bp.route('/logout')
def admin_logout():
    session.clear()
    flash('Has cerrado la sesión.', 'info')
    host = (request.host or '').split(':')[0].strip().lower()
    from ..dominios_negocio import slug_subdominio_publico
    if host == 'desk.tuc-tuc.co' or slug_subdominio_publico(host):
        return redirect(url_for('auth.entrar'))
    return redirect(url_for('auth.admin_login'))


@bp.route('/login')
def login_redirect():
    return redirect(url_for('auth.entrar'))
