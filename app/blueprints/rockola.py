from flask import Blueprint, render_template, request, jsonify, send_from_directory
from flask_socketio import emit
import os, uuid

bp = Blueprint('rockola', __name__, url_prefix='/rockola')

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp')
os.makedirs(UPLOAD_DIR, exist_ok=True)


@bp.route('/cliente')
def cliente():
    return render_template('rockola_cliente.html')


@bp.route('/reproductor')
def reproductor():
    return render_template('rockola_reproductor.html')


@bp.route('/subir', methods=['POST'])
def subir():
    f = request.files.get('archivo')
    if not f:
        return jsonify(ok=False, error='sin archivo'), 400
    ext = os.path.splitext(f.filename)[1].lower()
    nombre_id = str(uuid.uuid4()) + ext
    f.save(os.path.join(UPLOAD_DIR, nombre_id))
    return jsonify(ok=True, id=nombre_id, nombre=f.filename)


@bp.route('/archivo/<nombre_id>')
def archivo(nombre_id):
    return send_from_directory(UPLOAD_DIR, nombre_id)


def register_events(socketio):
    @socketio.on('cancion_lista')
    def cancion_lista(data):
        # data: { id, nombre }
        emit('nueva_cancion', data, broadcast=True, include_self=False)
