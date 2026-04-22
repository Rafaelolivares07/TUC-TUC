from flask import Blueprint, render_template, request, jsonify, send_from_directory
import os, uuid, threading

bp = Blueprint('rockola', __name__, url_prefix='/rockola')

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp')
os.makedirs(UPLOAD_DIR, exist_ok=True)

_lock = threading.Lock()
_cola = []  # [{ id, nombre }]


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
    with _lock:
        _cola.append({'id': nombre_id, 'nombre': f.filename})
    return jsonify(ok=True, id=nombre_id, nombre=f.filename)


@bp.route('/cola')
def cola():
    with _lock:
        return jsonify(ok=True, cola=list(_cola))


@bp.route('/siguiente', methods=['POST'])
def siguiente():
    with _lock:
        if _cola:
            _cola.pop(0)
    return jsonify(ok=True)


@bp.route('/archivo/<nombre_id>')
def archivo(nombre_id):
    return send_from_directory(UPLOAD_DIR, nombre_id)


def register_events(socketio):
    pass  # ya no se usa WebSocket
