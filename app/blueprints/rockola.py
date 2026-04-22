from flask import Blueprint, render_template, request, current_app
from flask_socketio import emit
import base64

bp = Blueprint('rockola', __name__, url_prefix='/rockola')


@bp.route('/cliente')
def cliente():
    return render_template('rockola_cliente.html')


@bp.route('/reproductor')
def reproductor():
    return render_template('rockola_reproductor.html')


def register_events(socketio):
    @socketio.on('subir_cancion')
    def subir_cancion(data):
        # data: { nombre: str, tipo: str, datos: base64 }
        emit('nueva_cancion', data, broadcast=True, include_self=False)
