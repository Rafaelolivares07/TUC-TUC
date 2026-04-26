from apscheduler.schedulers.gevent import GeventScheduler


_scheduler = None


def get_scheduler():
    return _scheduler


def init_scheduler(app):
    global _scheduler
    _scheduler = GeventScheduler()

    # Importaciones lazy — solo cuando el scheduler arranca
    with app.app_context():
        from .blueprints.domotica import job_verificar_switches
        from .blueprints.crm import job_verificar_recordatorios

        _scheduler.add_job(
            job_verificar_switches,
            'interval', minutes=5,
            id='domotica_switches'
        )
        _scheduler.add_job(
            job_verificar_recordatorios,
            'interval', minutes=5,
            id='crm_recordatorios'
        )

    if not _scheduler.running:
        _scheduler.start()
    print('[SCHEDULER] APScheduler inicializado')
