from flask import Flask
from flask_socketio import SocketIO
from .config import Config
from .db import init_db
from .scheduler import init_scheduler

socketio = SocketIO()


def create_app():
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )
    app.config.from_object(Config)

    init_db(app)

    from .blueprints.core import bp as core_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.restaurantes import bp as restaurantes_bp
    from .blueprints.tiendas import bp as tiendas_bp
    from .blueprints.domotica import bp as domotica_bp
    from .blueprints.crm import bp as crm_bp
    from .blueprints.admin_agent_bp import bp as admin_agent_bp
    # from .blueprints.rockola import bp as rockola_bp, register_events  # DESHABILITADO — bloquea worker sync
    from .blueprints.vendedor import bp as vendedor_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(restaurantes_bp)
    app.register_blueprint(tiendas_bp)
    app.register_blueprint(domotica_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(admin_agent_bp)
    # app.register_blueprint(rockola_bp)  # DESHABILITADO
    app.register_blueprint(vendedor_bp)

    socketio.init_app(app, cors_allowed_origins='*', async_mode='gevent')
    # register_events(socketio)  # DESHABILITADO — rockola off

    init_scheduler(app)

    return app
