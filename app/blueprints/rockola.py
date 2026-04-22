from flask import Blueprint, render_template, request, jsonify, send_from_directory
import os, uuid, threading

bp = Blueprint('rockola', __name__, url_prefix='/rockola')

UPLOAD_BASE = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'rockola_tmp')
os.makedirs(UPLOAD_BASE, exist_ok=True)

_lock = threading.Lock()
# _salas[sala_id] = { 'cola': [{ id, nombre, owner }] }
_salas = {}


def _get_sala(sala_id):
    if sala_id not in _salas:
        _salas[sala_id] = {'cola': []}
    return _salas[sala_id]


def _upload_dir(sala_id):
    d = os.path.join(UPLOAD_BASE, sala_id)
    os.makedirs(d, exist_ok=True)
    return d


# ── páginas ──────────────────────────────────────────────

@bp.route('/cliente')
def cliente():
    return render_template('rockola_cliente.html', sala_id='default', modo='restaurante')

@bp.route('/reproductor')
def reproductor():
    return render_template('rockola_reproductor.html', sala_id='default')

@bp.route('/<sala_id>/cliente')
def cliente_sala(sala_id):
    return render_template('rockola_cliente.html', sala_id=sala_id, modo='restaurante')

@bp.route('/<sala_id>/reproductor')
def reproductor_sala(sala_id):
    return render_template('rockola_reproductor.html', sala_id=sala_id)

@bp.route('/sync/<sala_id>')
def sync(sala_id):
    return render_template('rockola_sync.html', sala_id=sala_id)


# ── API ──────────────────────────────────────────────────

@bp.route('/<sala_id>/subir', methods=['POST'])
def subir(sala_id):
    owner = request.form.get('owner', 'anon')
    files = request.files.getlist('archivo')
    if not files:
        return jsonify(ok=False, error='sin archivo'), 400

    agregadas = []
    upload_dir = _upload_dir(sala_id)
    with _lock:
        sala = _get_sala(sala_id)
        for f in files:
            ext = os.path.splitext(f.filename)[1].lower()
            nombre_id = str(uuid.uuid4()) + ext
            f.save(os.path.join(upload_dir, nombre_id))
            item = {'id': nombre_id, 'nombre': f.filename, 'owner': owner}
            sala['cola'].append(item)
            agregadas.append(item)

    return jsonify(ok=True, agregadas=agregadas)


@bp.route('/<sala_id>/cola')
def cola(sala_id):
    with _lock:
        sala = _get_sala(sala_id)
        return jsonify(ok=True, cola=list(sala['cola']))


@bp.route('/<sala_id>/siguiente', methods=['POST'])
def siguiente(sala_id):
    with _lock:
        sala = _get_sala(sala_id)
        if sala['cola']:
            sala['cola'].pop(0)
    return jsonify(ok=True)


@bp.route('/<sala_id>/reordenar', methods=['POST'])
def reordenar(sala_id):
    data = request.get_json()
    nuevo_orden = data.get('orden', [])   # lista de ids
    owner = data.get('owner')
    modo = data.get('modo', 'restaurante')

    with _lock:
        sala = _get_sala(sala_id)
        cola = sala['cola']
        por_id = {item['id']: item for item in cola}
        nueva_cola = []
        for id_ in nuevo_orden:
            if id_ in por_id:
                item = por_id[id_]
                # en restaurante solo mueves las tuyas
                if modo == 'sync' or item['owner'] == owner:
                    nueva_cola.append(item)
        # agregar las que no vinieron en el orden (seguridad)
        ids_nuevos = {i['id'] for i in nueva_cola}
        for item in cola:
            if item['id'] not in ids_nuevos:
                nueva_cola.append(item)
        sala['cola'] = nueva_cola

    return jsonify(ok=True)


@bp.route('/<sala_id>/archivo/<nombre_id>')
def archivo(sala_id, nombre_id):
    return send_from_directory(_upload_dir(sala_id), nombre_id)


def register_events(socketio):
    pass
