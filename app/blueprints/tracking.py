from flask import Blueprint, request, jsonify, render_template

bp = Blueprint('tracking', __name__)

_posiciones = {}


@bp.route('/gps/<nombre>')
def tracker_page(nombre):
    return render_template('tracking_send.html', nombre=nombre)


@bp.route('/gps/<nombre>/seguir')
def seguir_page(nombre):
    return render_template('tracking_map.html', nombre=nombre)


@bp.route('/gps/<nombre>/track', methods=['POST'])
def track(nombre):
    _posiciones[nombre] = request.get_json(force=True)
    return '', 200


@bp.route('/gps/<nombre>/last')
def last(nombre):
    return jsonify(_posiciones.get(nombre))
