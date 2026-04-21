from flask import Blueprint, jsonify, redirect, url_for, render_template, session

bp = Blueprint('core', __name__)


@bp.route('/')
def index():
    if session.get('rol') == 'Administrador':
        return redirect(url_for('auth.admin_area'))
    return redirect(url_for('auth.admin_login'))


@bp.route('/api/version')
def api_version():
    return jsonify({'version': '2.0.0', 'ok': True})


@bp.route('/admin/acceso/<codigo>')
def admin_acceso(codigo):
    # TODO: migrar lógica de acceso por código
    return redirect(url_for('auth.admin_login'))
