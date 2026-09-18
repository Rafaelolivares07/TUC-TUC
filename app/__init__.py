import os
from flask import Flask, request
from .config import Config
from .db import init_db



def create_app():
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    for lower_dir, upper_dir in [('js', 'JS'), ('css', 'CSS')]:
        l_path = os.path.join(static_dir, lower_dir)
        u_path = os.path.join(static_dir, upper_dir)
        if not os.path.exists(l_path) and os.path.exists(u_path):
            try:
                os.symlink(upper_dir, l_path)
            except Exception:
                pass

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
    from .blueprints.reportes_bp import bp as reportes_bp

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
    app.register_blueprint(reportes_bp)

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
    def _reconocer_dispositivo_global():
        from flask import session
        if session.get('usuario_id'):
            return
        dev = request.cookies.get('tuctuc_device', '')
        if len(dev) < 8:
            return
        try:
            from .db import get_db_connection
            conn = get_db_connection()
            row = conn.execute("""
                SELECT d.tercero_id, t.nombre
                FROM terceros_dispositivos d JOIN terceros t ON t.id = d.tercero_id
                WHERE d.dispositivo_id = %s AND d.last_seen >= NOW() - INTERVAL '90 days'
                LIMIT 1
            """, (dev,)).fetchone()
            if row:
                conn.execute("UPDATE terceros_dispositivos SET last_seen = NOW() WHERE dispositivo_id = %s", (dev,))
                conn.commit()
                session['usuario_id'] = row['tercero_id']
                session['chat_tercero_id'] = row['tercero_id']
                session['nombre'] = row['nombre'] or ''
                if not session.get('rol'):
                    session['rol'] = 'Vendedor'
                session['dispositivo_id'] = dev
                session.permanent = True
            conn.close()
        except Exception:
            try: conn.close()
            except: pass

    @app.before_request
    def _cliente_subdominio():
        host_limpio = (request.host or '').split(':')[0].strip().lower().rstrip('.')
        if host_limpio == 'rockola.tuc-tuc.co':
            from .blueprints.rockola import entrada, sync, cliente_sala, reproductor_sala, control_sala

            if request.path.startswith('/api/') or request.path.startswith('/static/'):
                return
            partes = [p for p in request.path.strip('/').split('/') if p]
            if not partes:
                return entrada()
            if partes[0] == 'rockola':
                if len(partes) == 1:
                    return entrada()
                if len(partes) == 2 and partes[1] == 'salas':
                    return
                if len(partes) == 2:
                    return cliente_sala(partes[1])
                return
            if partes[0] in ('emisora', 'sync') and len(partes) >= 2:
                return sync(partes[1])
            if partes[0] == 'cliente' and len(partes) >= 2:
                return cliente_sala(partes[1])
            if partes[0] == 'reproductor' and len(partes) >= 2:
                return reproductor_sala(partes[1])
            if partes[0] == 'control' and len(partes) >= 2:
                return control_sala(partes[1])
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

    @app.after_request
    def add_no_cache_headers(response):
        if not request.path.startswith('/static/'):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.context_processor
    def inject_global_vars():
        return dict(
            APP_VERSION="v2.4.2"
        )

    return app
