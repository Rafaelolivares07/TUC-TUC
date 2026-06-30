import os
from flask import Flask, request
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
    from .blueprints.compras import bp as compras_bp
    from .blueprints.contabilidad import bp as contabilidad_bp, ejecutar_programaciones_job
    from .blueprints.tracking import bp as tracking_bp
    from .blueprints.watch import bp as watch_bp
    from .blueprints.pautas import bp as pautas_bp
    from .blueprints.agenda import bp as agenda_bp
    from .blueprints.chat import bp as chat_bp
    from .blueprints.negocios import bp as negocios_bp, init_config_negocio
    from .blueprints.backup import bp as backup_bp
    from .blueprints.rockola import bp as rockola_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(restaurantes_bp)
    app.register_blueprint(tiendas_bp)
    app.register_blueprint(domotica_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(admin_agent_bp)
    app.register_blueprint(vendedor_bp)
    app.register_blueprint(inventarios_bp)
    app.register_blueprint(compras_bp)
    app.register_blueprint(contabilidad_bp)
    app.register_blueprint(tracking_bp)
    app.register_blueprint(watch_bp)
    app.register_blueprint(pautas_bp)
    app.register_blueprint(agenda_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(negocios_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(rockola_bp)

    # Crear tabla config_negocio al arrancar (fuera de request handlers)
    try:
        from .db import get_db_connection
        from .dominios_negocio import asegurar_tabla_dominios_negocio
        _conn = get_db_connection()
        init_config_negocio(_conn)
        asegurar_tabla_dominios_negocio(_conn)
        _conn.close()
    except Exception as _e:
        print(f'[negocios] init: {_e}')

    @app.before_request
    def _cliente_subdominio():
        host_limpio = (request.host or '').split(':')[0].strip().lower().rstrip('.')
        if host_limpio == 'rockola.tuc-tuc.co':
            from .blueprints.rockola import entrada, sync, cliente_sala, reproductor_sala

            if request.path.startswith('/api/') or request.path.startswith('/static/'):
                return
            partes = [p for p in request.path.strip('/').split('/') if p]
            if not partes:
                return entrada()
            if partes[0] == 'rockola':
                if len(partes) == 1:
                    return entrada()
                if len(partes) == 2:
                    return cliente_sala(partes[1])
                return
            if partes[0] in ('emisora', 'sync') and len(partes) >= 2:
                return sync(partes[1])
            if partes[0] == 'cliente' and len(partes) >= 2:
                return cliente_sala(partes[1])
            if partes[0] == 'reproductor' and len(partes) >= 2:
                return reproductor_sala(partes[1])
            return entrada()

        from .dominios_negocio import resolver_negocio_por_host

        negocio_host = resolver_negocio_por_host(request.host)
        if not negocio_host:
            return
        slug = negocio_host['slug']
        tipo_negocio = negocio_host.get('tipo_negocio')
        from .blueprints.restaurantes import (
            restaurante_publico, restaurante_mesero, restaurante_cocina,
            mi_restaurante, restaurante_cliente, cobrar_mesa_page
        )
        from .blueprints.tiendas import tienda_publica, mi_tienda, tienda_caja, solar_proyecto_publico_desde_slugs
        from .db import get_db_connection

        # Detectar tipo de negocio una sola vez
        try:
            conn = get_db_connection()
            if tipo_negocio:
                es_tienda = tipo_negocio == 'tienda'
            else:
                es_tienda = conn.execute(
                    "SELECT 1 FROM tiendas WHERE slug = %s LIMIT 1", (slug,)
                ).fetchone()
            conn.close()
        except Exception:
            es_tienda = None

        # No interceptar llamadas API ni estáticos — dejar que Flask las enrute normal
        if request.path.startswith('/api/') or request.path.startswith('/static/') or request.path.startswith('/pagar/') or request.path.startswith('/proyecto/') or request.path.startswith('/solar/proyecto/'):
            return

        if es_tienda:
            _MAP_TIENDA = {
                '/admin': mi_tienda,
                '/caja':  tienda_caja,
            }
            fn = _MAP_TIENDA.get(request.path)
            if fn:
                return fn(slug)
            partes = [p for p in request.path.strip('/').split('/') if p]
            if len(partes) >= 2:
                respuesta_proyecto = solar_proyecto_publico_desde_slugs(slug, partes[0], '/'.join(partes[1:]))
                if respuesta_proyecto is not None:
                    return respuesta_proyecto
            return tienda_publica(slug)
        else:
            _MAP_REST = {
                '/mesero': restaurante_mesero,
                '/cocina': restaurante_cocina,
                '/admin':  mi_restaurante,
            }
            fn = _MAP_REST.get(request.path)
            if fn:
                return fn(slug)
            if request.path.startswith('/mesa/'):
                mesa_nombre = request.path[len('/mesa/'):]
                if mesa_nombre:
                    return restaurante_cliente(slug, mesa_nombre)
            if request.path.startswith('/cobrar-mesa/'):
                mesa_id = request.path[len('/cobrar-mesa/'):]
                if mesa_id:
                    return cobrar_mesa_page(slug, mesa_id)
            return restaurante_publico(slug)

    # scheduler contabilidad desactivado — colgaba el worker de gunicorn
    # reactivar cuando se confirme que las tablas existen y no hay locks
    # if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    #     from apscheduler.schedulers.background import BackgroundScheduler
    #     scheduler = BackgroundScheduler(daemon=True)
    #     scheduler.add_job(ejecutar_programaciones_job, 'interval', minutes=1,
    #                       args=[app], id='programaciones_contables')
    #     scheduler.start()

    return app
