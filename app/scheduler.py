from apscheduler.schedulers.background import BackgroundScheduler

from app.asegurar import reclamar_scheduler


_scheduler = None


def get_scheduler():
    return _scheduler


def _solo_lider(fn):
    """Solo el worker lider corre el job; los demas lo omiten. Si el lider
    muere, otro toma el mando en el proximo tick (ver app/asegurar.py)."""
    def run(*args, **kwargs):
        if reclamar_scheduler():
            return fn(*args, **kwargs)
    return run


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler()

    # Importaciones lazy â€” solo cuando el scheduler arranca
    with app.app_context():
        try:
            from .blueprints.domotica import job_verificar_switches
            _scheduler.add_job(
                _solo_lider(job_verificar_switches),
                'interval', minutes=5,
                id='domotica_switches',
                replace_existing=True
            )
        except Exception as e:
            print(f'[SCHEDULER] error registrando domotica_switches: {e}')

        try:
            from .blueprints.crm import job_verificar_recordatorios
            _scheduler.add_job(
                _solo_lider(job_verificar_recordatorios),
                'interval', minutes=5,
                id='crm_recordatorios',
                replace_existing=True
            )
        except Exception as e:
            print(f'[SCHEDULER] error registrando crm_recordatorios: {e}')

        try:
            from .blueprints.contabilidad import job_verificar_programaciones
            _scheduler.add_job(
                _solo_lider(job_verificar_programaciones),
                'interval', minutes=10,
                id='contabilidad_programaciones',
                replace_existing=True
            )
        except Exception as e:
            print(f'[SCHEDULER] error registrando contabilidad_programaciones: {e}')
        try:
            from .blueprints.facturacion_mensual import job_facturacion_mensual
            _scheduler.add_job(
                _solo_lider(job_facturacion_mensual),
                'interval', hours=1,
                id='facturacion_mensual',
                replace_existing=True
            )
        except Exception as e:
            print(f'[SCHEDULER] error registrando facturacion_mensual: {e}')

    if not _scheduler.running:
        _scheduler.start()
    print('[SCHEDULER] APScheduler inicializado con Ã©xito')
    return _scheduler
