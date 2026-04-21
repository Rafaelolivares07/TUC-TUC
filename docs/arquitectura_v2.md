# Arquitectura TUC TUC V2
_Actualizado: 2026-04-21_

## Contexto
V1 (`MiAppMedicamentos/`, branch `main`) era un monolito de 44.847 líneas que reventaba la memoria de Render (512MB free).
V2 es un **git worktree** del mismo repo en branch `v2`, refactorizado en blueprints Flask con lazy imports.

## Repo y Deploy
- **GitHub:** `https://github.com/Rafaelolivares07/TUC-TUC.git` — branch `v2`
- **Local:** `C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\`
- **Render:** `tuc-tuc.onrender.com` — start command: `gunicorn main:app --timeout 120 --workers 1 --preload`
- **Worktree:** comparte `.git` con V1 — hooks post-commit heredados automáticamente

## Estructura de carpetas

```
TucTucV2/
│
├── main.py                  # Entrada WSGI — solo: from app import create_app; app = create_app()
├── Procfile                 # gunicorn main:app --timeout 120 --workers 1 --preload
├── requirements.txt
├── deploy_watcher.py        # Monitor deploy Render — notifica PC + Telegram
├── deploy_estado.json       # Estado del último deploy (generado automáticamente)
├── admin_agent.py           # Agente local para consultas DBF remotas (PC cliente)
├── admin_agent.ini          # Nombre del equipo para el agente
├── administrator_web.py     # Servidor Flask local para formularios VFP (puerto 5002)
│
├── app/                     # Paquete principal
│   ├── __init__.py          # create_app() — registra blueprints, init_db, init_scheduler
│   ├── config.py            # Config desde .env (SECRET_KEY, DATABASE_URL, etc.)
│   ├── db.py                # Connection pool lazy (max=3), get_db_connection()
│   ├── scheduler.py         # APScheduler — jobs de domotica y crm
│   │
│   └── blueprints/
│       ├── auth.py          # ✅ login, logout, admin_area, admin_required, solo_admin
│       ├── core.py          # ✅ index, empieza, negocios, backups, mantenimiento, Telegram webhook
│       ├── restaurantes.py  # ✅ ~1.600 líneas — admin, cliente, mesero, cocina, pedidos, mesas
│       ├── tiendas.py       # ✅ ~2.000 líneas — admin, cliente, caja, cajeros, variantes, inventario
│       ├── admin_agent_bp.py# ✅ checkin, ping, consultar, resultado, permisos
│       ├── crm.py           # ⏳ stub — chat, terceros, vendedores (pendiente migración)
│       └── domotica.py      # ⏳ stub — switches, automatizaciones (pendiente migración)
│
├── templates/               # Jinja2 — compartidos entre blueprints
│   ├── admin_login.html
│   ├── admin_menu.html
│   ├── admin_negocios.html
│   ├── admin_backups.html
│   ├── admin_mantenimiento.html
│   ├── admin_parametros.html
│   ├── admin_taller_lista.html
│   ├── admin_inmobiliaria_lista.html
│   ├── admin_compraventa_lista.html
│   ├── admin_hospedaje_lista.html
│   ├── empieza.html
│   ├── restaurante_admin.html
│   ├── restaurante_cliente.html
│   ├── restaurante_mesero.html
│   ├── restaurante_cocina.html
│   ├── tienda_admin.html
│   ├── tienda_cliente.html
│   ├── tienda_caja.html
│   ├── domotica.html        # template existe, blueprint pendiente
│   ├── chat.html            # template existe, blueprint pendiente
│   └── ... (resto de templates V1 copiados, se usan conforme se migran)
│
├── static/                  # Imágenes, JS
│   └── JS/
│       ├── bienvenida.js
│       └── modal_tareas_revision.js
│
├── docs/                    # Documentación técnica y manuales
│   ├── leer al inicio cada sesion - estado sesion activa.md  ← LEER AL INICIAR
│   ├── leer al inicio cada sesion - reglas de trabajo.md
│   ├── arquitectura_v2.md   ← este archivo
│   ├── convenios_desarrollo.md
│   ├── restaurante_desarrollo.md
│   ├── tienda_desarrollo.md
│   ├── domotica_desarrollo.md
│   ├── vendedor_crm_desarrollo.md
│   ├── vfp_administrator_pilar.md
│   └── ...
│
├── remote-assist/           # Módulo Asistencia Remota
└── .env                     # Variables de entorno (no en git)
```

## Blueprints — detalle de rutas

### auth
| Ruta | Método | Función |
|---|---|---|
| `/admin/login` | GET | Formulario login |
| `/admin/login` | POST | Procesa login |
| `/admin/area` | GET | Dashboard admin (requiere sesión) |
| `/admin/logout`, `/logout` | GET | Cierra sesión |
| `/admin`, `/login` | GET | Redirects |

### core
| Ruta | Descripción |
|---|---|
| `/` | Redirect a login o admin/area |
| `/empieza`, `/empieza/<ref>` | Landing page captación negocios |
| `/api/prospecto` | Guardar prospecto |
| `/api/registro-rapido` | Crear restaurante/tienda desde landing |
| `/admin/acceso/<codigo>` | Acceso directo con código `tuctuc2025` |
| `/admin/menu`, `/admin_menu` | Menú principal admin |
| `/admin/parametros` | Página parámetros |
| `/admin/mantenimiento` | Panel mantenimiento BD |
| `/admin/negocios` | Submenú negocios |
| `/admin/taller` | Lista talleres |
| `/admin/inmobiliaria` | Lista inmobiliarias |
| `/admin/compraventa` | Lista compraventas |
| `/admin/hospedaje` | Lista hospedajes |
| `/admin/switch-database` | Cambiar modo BD (producción/local) |
| `/admin/backups` | Lista backups |
| `/api/admin/backup/crear` | Crear backup SQL |
| `/api/admin/backup/<n>/descargar` | Descargar backup |
| `/api/admin/db/tablas` | Lista tablas BD |
| `/api/admin/db/tabla/<n>/estructura` | Estructura de tabla |
| `/api/version` | Versión + commit hash (para deploy_watcher) |
| `/api/webhook/render-deploy` | Recibe notificación deploy → manda Telegram |

### restaurantes
Todas las rutas de carta, menú del día, pedidos, mesas, mesero, cocina, admin, QR.

### tiendas
Todas las rutas de productos, variantes, inventario, pedidos, cajeros, métodos de pago.

### admin_agent
Relay para consultas DBF remotas desde browser a PC cliente.

## Módulos NO migrados (intencional)
- **Transporte** — no aplica en V2
- **Droguería/Medicamentos** — no aplica en V2

## Convenciones técnicas V2

### Lazy imports
Librerías pesadas NO van al inicio del archivo:
```python
# MAL — al inicio del blueprint
import tinytuya

# BIEN — dentro de la función que lo usa
def toggle_switch(sid):
    import tinytuya
    ...
```

### Connection pool
```python
# db.py — pool lazy, max=3 conexiones
# Siempre hacer conn.close() o usar with conn:
conn = get_db_connection()
try:
    result = conn.execute("SELECT ...", (params,)).fetchall()
    conn.commit()
finally:
    conn.close()
```

### url_for en templates
Siempre con prefijo de blueprint:
```html
<!-- MAL -->
{{ url_for('admin_menu') }}
<!-- BIEN -->
{{ url_for('core.admin_menu') }}
{{ url_for('auth.admin_logout') }}
{{ url_for('restaurantes.admin_restaurante_lista') }}
```

### Respuestas API
```python
return jsonify({'ok': True, ...datos})
return jsonify({'ok': False, 'error': 'mensaje'}), 400
```

## Deploy watcher
- `deploy_watcher.py` corre en background después de cada `git push` (hook post-commit)
- Chequea `/api/version` cada 20s comparando el commit hash
- Notifica: balloon Windows + Telegram vía `/api/webhook/render-deploy`
- Timeout: 30 minutos
