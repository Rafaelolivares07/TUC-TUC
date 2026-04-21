from functools import wraps
from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, flash, jsonify)
from ..db import get_db_connection

bp = Blueprint('auth', __name__)


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'rol' not in session or session['rol'] not in ('Administrador', 'ClienteVFP'):
            if (request.is_json or
                    request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                    'application/json' in request.headers.get('Accept', '')):
                return jsonify({'ok': False, 'error': 'No autenticado'}), 401
            return redirect(url_for('auth.admin_login'))
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
    if session.get('rol') == 'Administrador':
        return redirect(url_for('auth.admin_area'))
    return redirect(url_for('auth.admin_login'))


@bp.route('/admin/login', methods=['GET'])
def admin_login():
    if session.get('rol') in ('Administrador', 'ClienteVFP'):
        return redirect(url_for('auth.admin_area'))
    return render_template('admin_login.html')


@bp.route('/admin/login', methods=['POST'])
def admin_login_post():
    usuario = request.form.get('usuario', '').strip()
    password = request.form.get('password', '').strip()

    if not usuario or not password:
        flash('Por favor completa todos los campos', 'danger')
        return redirect(url_for('auth.admin_login'))

    conn = get_db_connection()
    try:
        admin = conn.execute("""
            SELECT * FROM usuarios
            WHERE usuario = %s AND password = %s
              AND rol IN ('Administrador', 'ClienteVFP')
        """, (usuario, password)).fetchone()

        if admin:
            session.clear()
            session['usuario_id']   = admin['id']
            session['nombre']       = admin['nombre']
            session['rol']          = admin['rol']
            session['dispositivo_id'] = admin.get('dispositivo_id', '')
            session.permanent       = True
            session.modified        = True

            if admin['rol'] == 'ClienteVFP':
                return redirect(url_for('admin_agent.consultas_page'))
            return redirect(url_for('auth.admin_area'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
            return redirect(url_for('auth.admin_login'))
    finally:
        conn.close()


@bp.route('/admin/area')
@admin_required
def admin_area():
    return render_template('admin_menu.html',
                           nombre=session['nombre'],
                           device_id=session.get('dispositivo_id', ''))


@bp.route('/admin/logout')
@bp.route('/logout')
def admin_logout():
    session.clear()
    flash('Has cerrado la sesión.', 'info')
    return redirect(url_for('auth.admin_login'))


@bp.route('/login')
def login_redirect():
    return redirect(url_for('auth.admin_login'))
