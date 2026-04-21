from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify

bp = Blueprint('auth', __name__)


@bp.route('/admin/login', methods=['GET'])
def admin_login():
    if 'usuario_id' in session:
        return redirect(url_for('core.index'))
    return render_template('admin_login.html')


@bp.route('/admin/login', methods=['POST'])
def admin_login_post():
    # TODO: migrar lógica desde 1_medicamentos.py
    pass


@bp.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('auth.admin_login'))


@bp.route('/login')
def login_redirect():
    return redirect(url_for('auth.admin_login'))
