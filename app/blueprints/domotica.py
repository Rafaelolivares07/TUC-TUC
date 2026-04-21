from flask import Blueprint

bp = Blueprint('domotica', __name__)

# TODO: migrar rutas /admin/domotica, /api/domotica


def job_verificar_switches():
    """Tarea APScheduler — importa tuyaapi lazy aquí adentro"""
    pass
