from flask import Flask
from .config import Config
from .db import init_db


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
    from .blueprints.vendedor import bp as vendedor_bp
    from .blueprints.inventarios import bp as inventarios_bp
    from .blueprints.contabilidad import bp as contabilidad_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(restaurantes_bp)
    app.register_blueprint(tiendas_bp)
    app.register_blueprint(domotica_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(admin_agent_bp)
    app.register_blueprint(vendedor_bp)
    app.register_blueprint(inventarios_bp)
    app.register_blueprint(contabilidad_bp)

    return app
