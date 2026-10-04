from apscheduler.schedulers.background import BackgroundScheduler


_scheduler = None


def get_scheduler():
    return _scheduler


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler()

    # Importaciones lazy — solo cuando el scheduler arranca
    with app.app_context():
        try:
            from .blueprints.domotica import job_verificar_switches
            _scheduler.add_job(
                job_verificar_switches,
                'interval', minutes=5,
                id='domotica_switches',
                replace_existing=True
            )
        except Exception as e:
            print(f'[SCHEDULER] error registrando domotica_switches: {e}')

        try:
            from .blueprints.crm import job_verificar_recordatorios
            _scheduler.add_job(
                job_verificar_recordatorios,
                'interval', minutes=5,
                id='crm_recordatorios',
                replace_existing=True
            )
        except Exception as e:
            print(f'[SCHEDULER] error registrando crm_recordatorios: {e}')

        try:
            from .blueprints.contabilidad import job_verificar_programaciones
            _scheduler.add_job(
                job_verificar_programaciones,
                'interval', minutes=10,
                id='contabilidad_programaciones',
                replace_existing=True
            )
        except Exception as e:
            print(f'[SCHEDULER] error registrando contabilidad_programaciones: {e}')

    if not _scheduler.running:
        _scheduler.start()
    print('[SCHEDULER] APScheduler inicializado con éxito')
    return _scheduler

