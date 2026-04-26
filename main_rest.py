from flask import Flask
from app.config import Config
from app.db import init_db


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)
    init_db(app)

    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.restaurantes import bp as restaurantes_bp
    from app.blueprints.core import bp as core_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(restaurantes_bp)
    app.register_blueprint(core_bp)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
