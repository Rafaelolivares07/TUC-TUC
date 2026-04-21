from flask import Blueprint, jsonify, redirect, url_for

bp = Blueprint('core', __name__)


@bp.route('/')
def index():
    return redirect(url_for('auth.admin_login'))


@bp.route('/api/version')
def api_version():
    return jsonify({'version': '2.0.0', 'ok': True})
