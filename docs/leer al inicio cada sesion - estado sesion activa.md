# Estado de Sesión Activa
_Actualizado: 2026-04-21_

## Módulos en trabajo esta sesión
1. **TUC TUC V2** — refactorización en blueprints, desplegado en Render branch `v2` ✅ LIVE
2. **Administrator Web** — pendiente despliegue en PC Pilar (próxima sesión remota)
3. **Admin Agent** ✅ FUNCIONANDO (pendiente despliegue Pilar)
4. **Rockola** (2026-04-22 09:00) — núcleo técnico funcionando, salas + modo sync implementados ✅

---

## MÓDULO: Tuc Tuc Rockola (2026-04-22 09:00)

Docs: `docs/rockola_concepto.md` (concepto) + `docs/rockola_desarrollo.md` (técnico)

### Estado
- ✅ Subida MP3, cola, reproducción automática en Android — probado
- ✅ Salas independientes por `sala_id`
- ✅ Modo sync `/rockola/sync/<sala_id>` — todos reproductores
- ✅ Drag & drop cola, multi-archivo — implementado, pendiente prueba
- ⬜ Dashboard dueño, créditos, QR, PIN reproductor

### Commits clave 2026-04-22
- `cdb2213` — polling HTTP reemplaza WebSocket
- `deedbbb` — botón Activar fix autoplay móvil
- `008ccca` — salas, drag&drop, multi-archivo, modo sync

---

## MÓDULO: TUC TUC V2 (2026-04-21) ✅ EN PRODUCCIÓN

### Contexto
Render plan free (512MB) empezó a fallar por tamaño del monolito `1_medicamentos.py` (44.847 líneas).
Solución: refactorizar en blueprints Flask con lazy imports. V1 queda intacto en branch `main` como respaldo.

### Estructura
- Repo: `https://github.com/Rafaelolivares07/TUC-TUC.git` — branch `v2`
- Carpeta local: `C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\`
- Es un **git worktree** del repo de V1 — comparten `.git`
- Start command en Render: `gunicorn main:app --timeout 120 --workers 1 --preload`
- Entrada: `main.py` → `app/__init__.py` (app factory)

### Blueprints migrados
| Blueprint | Estado | Rutas clave |
|---|---|---|
| `auth` | ✅ | login, logout, admin_area |
| `core` | ✅ | index, empieza, negocios, backups, mantenimiento, switch-db, deploy webhook |
| `restaurantes` | ✅ | ~500 líneas, todas las rutas |
| `tiendas` | ✅ | CRUD productos, pedidos, cajeros, variantes |
| `admin_agent` | ✅ | checkin, ping, consultar, permisos |
| `crm` | ⏳ stub | chat, terceros, vendedores — pendiente |
| `domotica` | ⏳ stub | switches, automatizaciones — pendiente |

### Módulos NO migrados (intencional)
- Transporte — no se migra a V2
- Droguería/Medicamentos — no se migra a V2

### Decisiones técnicas clave
- **Lazy imports**: librerías pesadas (`tinytuya`, `anthropic`, `firebase`) se importan dentro de cada función, no al arranque
- **Connection pool**: `psycopg2.pool.ThreadedConnectionPool(min=1, max=3)` — lazy, no conecta al arrancar
- **`/api/version`** devuelve `commit` hash — permite al deploy_watcher detectar el live
- **Templates**: `url_for` corregidos a `blueprint.endpoint` — pendiente revisar conforme se navega
- **deploy_watcher.py** copiado a TucTucV2, hook post-commit heredado del worktree

### Pendientes V2
- Migrar `crm` — chat, terceros, vendedores, recordatorios (lazy import `anthropic`)
- Migrar `domotica` — switches, automatizaciones (lazy import `tinytuya`)
- Seguir corrigiendo `url_for` sin prefijo conforme se navega
- Verificar Telegram deploy notification (fix `"CONFIGURACION_SISTEMA"` con comillas)

### Commits clave sesión 2026-04-21
- `c674687` — estructura inicial V2
- `01d7cb4` — tiendas blueprint
- `f62c463` — core blueprint completo
- `eb2c4bb` — connection pool lazy + /api/version con commit
- `2f24285` — fix CONFIGURACION_SISTEMA + deploy webhook Telegram

---

## MÓDULO: Administrator Web (2026-04-20) ✅

### Concepto
Servidor Flask local (`localhost:5002`) que reemplaza formularios VFP con HTML moderno.
VFP abre el navegador vía menú (`formularios.dbf` → `RUN /N C:\S.A.R\abrir_web.bat <url>`).
Estrategia de migración: hoy lee DBF local → futuro cambia solo la capa de datos a PostgreSQL.

### Archivos
| Archivo | Ubicación | Descripción |
|---|---|---|
| `administrator_web.py` | `MiAppMedicamentos/` | Servidor Flask, todas las rutas |
| `adm_ventas_clientes.html` | `templates/` | Formulario ventas por clientes |
| `adm_consulta_cuentas.html` | `templates/` | Formulario consulta de cuentas REG_CTAS |
| `abrir_web.bat` | `C:\S.A.R\` | Lanzador: popup + python + browser |
| `popup_web.py` | `C:\S.A.R\` | Popup Tkinter "Abriendo en el navegador..." |

### Formularios disponibles
| URL | Formulario | Comando VFP |
|---|---|---|
| `/ventas_clientes` | Ventas por Clientes (PROD_FACT1) | `RUN /N C:\S.A.R\abrir_web.bat http://localhost:5002/ventas_clientes` |
| `/consulta_cuentas` | Consulta de Cuentas (REG_CTAS) | `RUN /N C:\S.A.R\abrir_web.bat http://localhost:5002/consulta_cuentas` |

### Singleton y auto-reload
- Lock en puerto 47836 — solo un proceso (no duplica)
- `WERKZEUG_RUN_MAIN` check — lock solo en proceso padre del reloader
- `debug=True, use_reloader=True` — recarga automática al guardar código

### Offsets DBF usados
**PROD_FACT1** (REC_SIZE=179): CANTIDAD@49, PRECIO@59, EMPRESA@91(C4), FECHAHORA@95(T→JulianDay), POR_IVA@103, CLIENTE@126
**TERCEROS** (REC_SIZE=739): COD_TER@1, NOMBRE@11(C50), IDENTIFICACION@61(C15) — leer en binario (IMAGEN C254 tarda)
**REG_CTAS** (REC_SIZE=345): CUENTA@11(C15), LAPSO@26(D→YYYYMMDD), TERCERO@42, EMPRESA@52(C10), TOT_DEB@108, TOT_CRE@118, ANULADO@344

### Despliegue pendiente en PC Pilar
Cuando Pilar avise (sesión remota):
1. Transferir vía panel archivos: `administrator_web.py`, `templates/adm_ventas_clientes.html`, `templates/adm_consulta_cuentas.html`, `abrir_web.bat`, `popup_web.py`
2. Terminal remota: `pip install flask openpyxl` (si no están)
3. Pilar agrega registros en `formularios.dbf` con los comandos VFP de la tabla anterior

---

## MÓDULO: Asistencia Remota (2026-04-20) — V1.3

### Cambios V1.3 (esta sesión)
- **Sin token**: visor solo pide código de 6 dígitos — token eliminado del formulario
- **Calibración de puntero**: botón 🎯 Calibrar en header del visor
  - Agente muestra pantalla negra fullscreen con 4 cruces numeradas (verde/azul/naranja/rojo)
  - Rafael hace clic en cada una desde el visor en orden 1→4
  - Regresión lineal calcula corrección sx/ox/sy/oy y guarda en localStorage
  - Se aplica a todos los clics/movimientos futuros
  - Persiste entre sesiones (localStorage)

### Release GitHub
- V1.3 en `https://github.com/Rafaelolivares07/TUC-TUC/releases/latest/download/AsistenciaTucTuc.exe`
- Pilar descarga desde botón en `/empieza` o admin

### Archivos modificados
- `remote-assist/server.py` — token removido + UI calibración + JS calibración
- `remote-assist/agente_cliente.py` — handlers `calibrate_show` / `calibrate_hide` (overlay Tkinter)
- `remote-assist/dist/AsistenciaTucTuc.exe` — recompilado V1.3

---

---

## MÓDULO: TUC TUC — Restaurantes (sesión 2026-04-17)

### Rancho Dapa — nuevo restaurante
- Restaurante tipo carta, id=9, slug=`rancho-dapa`
- **86 ítems de menú** insertados en `opciones_menu` con categorías y precios
- **35 descripciones** cargadas para los ítems con descripción en la carta
- Categorías: Cazuelas, Sopas, Sancochos, Bandeja, Platos del día, Jugos, Bebidas calientes, Gaseosas, Agua

### Carta — orden drag-and-drop (admin)
- Nueva columna `orden INT DEFAULT 0` en `opciones_menu` — se agrega vía ALTER en `crear_tablas_restaurante`
- SortableJS 1.15.2 cargado desde CDN en `restaurante_admin.html`
- Drag-and-drop en categorías (reordena bloques) y dentro de cada categoría (reordena ítems)
- `_guardarOrden()`: recorre DOM, asigna ordinales secuenciales, POST a `/api/restaurante/<slug>/reordenar`
- Endpoint `POST /api/restaurante/<slug>/reordenar` — actualiza `orden` en BD

### Carta — auto-layout en vista cliente
- `cargarCartaCliente()` detecta por categoría: si algún ítem tiene imagen → grid 2 columnas con foto
- Si ningún ítem de la categoría tiene imagen → lista limpia (nombre + descripción + precio + controles cantidad), sin espacio para imagen
- El orden de categorías e ítems respeta el campo `orden` de la BD

### Mesero — fix error 500 en carta
- **Bug**: `mesa_nombre` llegaba como INTEGER desde JS (`seleccionarMesa(${m.numero})`); backend hacía `int.strip()` → AttributeError 500
- **Fix en `api_restaurante_pedido_crear`**: `str(data.get('mesa_nombre') or '').strip() or None` — convierte a string antes del strip
- `request.get_json(force=True)` para evitar fallo cuando Content-Type no es JSON

### Commits 2026-04-17
- `06aa856` — Rancho Dapa: 86 ítems insertados
- `68d5469` — Carta: orden drag-and-drop admin + auto-layout cliente
- `28dc0b6` — ALTER orden en crear_tablas_restaurante (self-healing)
- `5bf3e7a` — Fix mesero 500: str(mesa_nombre)

### Quitar imagen de ítem — RESUELTO 2026-04-18
- Botón "✕ quitar" debajo de miniatura cuando el ítem tiene imagen
- Endpoint `DELETE /opcion/<id>/imagen` — pone imagen=NULL en BD
- Fix auth en endpoint imagen (POST y DELETE): acepta restaurante_token además de usuario_id

### Drag-and-drop persistente — RESUELTO 2026-04-18
- Bug 1: `_initSortable()` creaba Sortables duplicados en cada `renderCatalogo()` → fix: destruir instancia previa
- Bug 2: endpoint `/reordenar` solo aceptaba `usuario_id` → 403 para admins de restaurante → fix: acepta `restaurante_token` también (mismo patrón que otros endpoints admin)

### Pendientes restaurantes
- Landing page restaurantes — pendiente video Rafael con CapCut Android

---

## Pendiente futuro — Migración a Oracle Cloud Free Tier

- **Objetivo**: reemplazar Render por Oracle Cloud (Always Free) — 1GB RAM mínimo garantizado, sin sleep por inactividad
- **Ventaja clave**: el doble de RAM que Render free (512MB) — resuelve los SIGKILL por memoria
- **Opción ARM**: hasta 4 OCPU + 24GB RAM gratis en instancias Ampere
- **Requiere**: configurar Ubuntu + nginx + gunicorn manualmente una vez
- **Retomar cuando**: la rockola u otro módulo pague el tiempo de migración

---

## Pendiente futuro — Agentes locales Ollama
- Idea: Ollama/Llama como agentes subordinados de Merlin (tareas paralelas, bridge usuarios, automatización)
- **Bloqueante**: PC actual tiene solo 4GB RAM + Intel UHD 605 — insuficiente para modelos útiles (mínimo 16GB)
- Retomar cuando haya hardware disponible (16GB RAM mínimo)

---

## MÓDULO: TUC TUC — Restaurantes tipo 'ambos'

### Qué se implementó
- Nuevo valor `tipo_restaurante = 'ambos'` — restaurante con carta Y menú del día
- **Backend**: `'ambos'` válido en creación; pedido detecta flujo por payload (`platos`=carta, `tipo`=menu_dia); endpoint `POST /api/restaurante/<slug>/tipo-restaurante` (acepta usuario_id O restaurante_token)
- **Admin** (`restaurante_admin.html`):
  - Tab "Carta/Menú" (nombre dinámico: "Menú" para menu_dia, "Carta" para carta/ambos)
  - Tab "Opciones menú del día" — visible solo para `ambos` — formulario sopa/proteína/principio
  - Tab "Menú del día" — visible para `menu_dia` y `ambos`
  - Selector "Tipo de carta" en tab Personalizar → guarda sin recargar, actualiza tabs al instante
  - Todas las pestañas siempre en DOM, visibilidad controlada por `hidden`
- **Cliente** (`restaurante_cliente.html`): tabs Carta / Menú del día para `ambos`; `activarModo()` recarga contenido; `enviarPedido` distingue por `modoActual`
- **Mesero** (`restaurante_mesero.html`): `paso-modo` con botones Carta/Menú del día para `ambos`; botones Volver dinámicos

### Estado pestañas admin por tipo
| tipo | Tabs visibles |
|---|---|
| `menu_dia` | Menú + Menú del día |
| `carta` | Carta |
| `ambos` | Carta + Opciones menú del día + Menú del día |

### Pendientes restaurantes
- ✅ Fix persistencia tipo_restaurante — reload tras guardar + verificación en endpoint
- ✅ Preview de pestañas al seleccionar tipo (onchange)
- Prueba real con restaurante tipo `ambos` en todas las URLs

### Landing page restaurantes — PENDIENTE
- **Precio definido:** $6.000/día · $150.000/mes · $1.500.000/año (anual = "pagas 10, te regalamos 2")
- **Estructura acordada (mobile-first):**
  1. Hero: nombre/logo + frase grande + botón "Ver demo"
  2. Frase gancho: *"El cliente escanea. Tú cocinas. Sin más."*
  3. Video: grabar pantallas reales (cliente → mesero → cocina) con CapCut — Rafael lo graba con Android
  4. Precio
  5. CTA: "Quiero esto para mi restaurante"
- **Pendiente Rafael:** grabar el video con grabador de pantalla Android + CapCut
- **Pendiente Merlin:** construir la landing en Flask cuando Rafael tenga el video listo

---

## MÓDULO: VFP / SAR — Alegra

### Versiones
- `alegra_daemon.py` → **v2.8** (intervalo en segundos, recompilado 2026-04-14)
- `configurar_allegra.py` → **v2.8** (4 paneles facturas, intervalo segundos, UI mejorada)
- `interfaz_allegra.py` → **4 fases ACTIVAS Y COMPLETAS** + procesamiento parcial con alertas
- `allegra_sync.py` → campo `fecha_hora T` — datetime exacto de Alegra

### Lo que está funcionando (2026-04-14)
- **4 fases completas**: f_prod1, f_standar, f_costos, f_contab — todas activas y probadas en ciclos reales
- **f_standar**: `_standar()` lee TRANS_MAT (kits), inserta REG_PROD, actualiza REG_PROD_SALDOS — NO es stub
- **Multi-pagos**: campo `pagos` JSON con todos los payments de Alegra — asientos contables cuadrados
- **NITs auto-creados**: toggle auto_nit — crea tercero en TERCEROS.dbf automáticamente
- **Equivalencia vendedores**: seller_id Alegra → vendedor Administrator (MESEROS.dbf); guarda en alegra_vendedores.dbf
- **Reinicio seguro**: diálogo post-reinicio sugiere MIN(borrado)-1 por empresa; bloquea Reanudar/Un ciclo hasta confirmar
- **CDX fix en reinicio**: `_vfp_delete_en_tabla()` usa VFP COM para DELETE — actualiza CDX
- **fecha_hora en PROD_FACT1**: FECHAHORA toma el datetime exacto de Alegra (`factura["datetime"]`), no la medianoche
- **_max_consecutivo()**: escanea todos los registros no borrados — correcto post-reinicio
- **Procesamiento parcial con alertas**: overflow en `_standar()` o productos sin cuenta grupo=0 no bloquean la factura — se marca como "procesada con alerta"
- **4 paneles en grilla facturas**: Pendientes / Con inconsistencias / Procesadas / Procesadas con alertas
- **Intervalo en segundos**: campo `intervalo N(4,0)` — era minutos, ahora segundos

### Despliegue PC Pilar — 2026-04-14 ✅

- Scripts v2.8 instalados en `C:\S.A.R\` vía relay AsistenciaTucTuc
- BD real: `\\192.168.1.104\BASEDATOSEMPRESAS\` (share de red, no C:\D\)
- `instalar_allegra_bd.py` corrido — tablas Alegra creadas
- Configurado por Rafael + Pilar: tip_doc, met_pago, num_inicio, vendedores, intervalo
- Ciclo manual probado → todas las fases OK en Administrator
- Startup: `AlegraDaemon.bat` en shell:startup
- Acceso directo "Alegra Config" en escritorio Pilar

### Upgrade Staging — 2026-04-17 ✅ COMPLETAMENTE OPERATIVO

- Arquitectura staging desplegada en PC Pilar vía relay AsistenciaTucTuc (sesión 184576)
- BD reindexada con REINDEXADOR.EXE antes del upgrade
- 5 archivos transmitidos: `alegra_daemon.py`, `AlegraDaemon.exe` (v2.8), `interfaz_allegra.py`, `instalar_allegra_bd.py`, `PROCESADOR_STAGING.EXE`
- 8 tablas `stg_*` creadas en `\\192.168.1.104\BASEDATOSEMPRESAS\`
- Ciclo manual OK — 2 facturas procesadas, 0 errores
- Administrator verificado — registros visibles, filtros por fecha funcionan
- **AlegraDaemon.exe v2.8 corriendo en producción** — Python NO escribe directo en tablas productivas

---

### Cambios sesión 2026-04-14

#### Bugs corregidos en interfaz_allegra.py
- **UnboundLocalError var_consecutivo**: variable inicializada antes del for loop (antes estaba dentro, skip por grupo=0 la dejaba sin definir)
- **DataOverflowError _standar()**: productos con SAL_EXI/VAL_EXI_CO fuera de rango → wrapeado per-item en try/except → costo=0.0 + alerta; factura continúa procesándose
- **_costo_ventas_contabiliza() retornaba None**: función era void → añadidos `return sin_cuentas` y `return []`; productos grupo=0 se reportan como alerta
- **Except principal sin _marcar_motivo**: facturas que lanzaban excepción quedaban en pendientes sin motivo → añadido `_marcar_motivo(fid, f"FALLA: {e}")`

#### Nueva categoría "Procesadas con alertas"
- `_marcar_completo_con_alerta(factura_id, motivo)` — setea `procesado=True` con `motivo` no vacío
- Clasificación en `_leer_facturas()`: `procesado=True AND motivo != ''` → `con_alerta`
- 4to panel `tree_alerta` en pestaña Facturas (naranja `#996600`)
- Barra estado: `f"Pendientes: {np} | Con inconsistencias: {ne} | Procesadas: {nr} | Con alertas: {na}"`

#### Intervalo cambiado de minutos a segundos
- `alegra_config.dbf`: campo `intervalo N(3,0)` migrado a `N(4,0)` — migración automática al abrir
- Daemon: `time.sleep(intervalo)` (antes `intervalo * 60`); `timeout_ciclo = max(1800, intervalo_cfg)` (antes `* 60`)
- UI: label "Pausa entre ciclos (seg, 0=manual)"; spinbox to=9999; textos actualizados
- **Daemon recompilado** a `AlegraDaemon.exe` con PyInstaller --clean

#### Mejoras UI configurar_allegra.py
- **Tamaño ventana**: `alto_max = sh - 60` — se adapta a cualquier resolución de pantalla
- **Título eliminado**: se quitó el label "ADMINISTRATOR INTERFASES" flotante sobre todos los elementos
- **Botón "Revertir fases seleccionada" eliminado** del panel Procesadas
- **"Reiniciar proceso" movido** a pestaña Estado & Log (junto a Borrado DBF) — era demasiado peligroso en la barra principal
- **"Borrado DBF" deshabilitado** cuando el daemon está activo; se habilita solo al pausar
- **"Reiniciar proceso" también deshabilitado** cuando el daemon no está pausado — misma lógica que Borrado DBF; ambos botones comparten estado: `normal` si `PAUSA_FILE` existe, `disabled` si no

### CDX APPEND — RESUELTO 2026-04-16 (arquitectura staging)

Python ya NO escribe en tablas productivas directamente. Nuevo flujo:
1. `interfaz_allegra.py` calcula todo y escribe en tablas `stg_*` (sin CDX relevante)
2. `PROCESADOR_STAGING.EXE` (VFP compilado) lee `stg_*` y hace APPEND en tablas reales — VFP actualiza CDX automáticamente

**Tablas staging creadas** (en carpeta BD):
- `stg_lotes.dbf` — control de lotes por factura
- `stg_prod_fact1.dbf`, `stg_reg_prod.dbf`, `stg_reg_prod_sal.dbf`
- `stg_reg_ctas.dbf`, `stg_sal_doc.dbf`, `stg_nota.dbf`

**Archivos modificados**:
- `C:\S.A.R\interfaz_allegra.py` — redirige APPENDs a staging, llama al procesador
- `C:\S.A.R\alegra_daemon.py` — agrega paso procesador en correr_sync()
- `C:\S.A.R\instalar_allegra_bd.py` — crea tablas staging en instalación
- `C:\S.A.R\PROYECTO\procesador_staging.prg` — **NUEVO** — PRG VFP a compilar como EXE

**Pendiente crítico**: compilar `procesador_staging.prg` → `C:\S.A.R\PROCESADOR_STAGING.EXE`
```
SET DEFAULT TO C:\S.A.R\PROYECTO
BUILD EXE "C:\S.A.R\PROCESADOR_STAGING" FROM procesador_staging
```

### Pendientes SAR — próxima sesión
1. **Auditar bolsa** — verificar cuenta 240807 cuadrada con fix ln_bolsa
2. **Auditar vendedores** — verificar VENDEDOR ≠ 0 en PROD_FACT1
3. **Bug cosmético fases UI** — f_standar/f_costos/f_contab no reportan "hecho" en la interfaz
4. **Progreso sync en tiempo real** — mostrar facturas descargándose en grilla Pendientes

### Estado de archivos SAR

| Archivo | Estado |
|---|---|
| `s.a.r.prg` | ✅ Limpio — sin batch mode |
| `interfaz_allegra.prg` | ✅ Limpio — no se usa en automático |
| `alegra_timer.prg` | ⏸️ RETURN al inicio — desactivado |
| `fondo_menu_limpio.scx` | ✅ Sin cambios |
| `alegra_daemon.py` | ✅ v2.8 — llama PROCESADOR_STAGING.EXE en cada ciclo |
| `AlegraDaemon.exe` | ✅ v2.8 — corriendo en PC Pilar (shell:startup) |
| `configurar_allegra.py` | ✅ v2.8 — 4 paneles, intervalo segundos, UI adaptativa |
| `interfaz_allegra.py` | ✅ staging completo — escribe solo en stg_*, incluye stg_terceros |
| `allegra_sync.py` | ✅ campo fecha_hora T — datetime exacto de Alegra |
| `PROCESADOR_STAGING.EXE` | ✅ compilado 2026-04-16 — mueve stg_* a tablas reales, abre DBC para TERCEROS |

**Administrator abre sin inconvenientes para usuarios normales.** ✅

---

### Contexto técnico fijo

- BD Pilar (PROD): `C:\D\Pilar Peralta\basedatosempresas\`
- Scripts Python Alegra: `C:\S.A.R\`
- PRGs VFP: `C:\S.A.R\PROYECTO\`
- Referencia técnica completa: `docs/vfp_administrator_pilar.md`

---

## Planes futuros — domótica

### Control local Tuya sin suscripción (relay PC → dispositivo)
- **Objetivo**: eliminar dependencia de Tuya cloud — control 100% local vía tinytuya
- **Arquitectura**: Render → POST relay (tuc-tuc-remote) → agente_domotica.py en PC → tinytuya LAN → dispositivo
- **Bloqueante**: necesitamos los `local_key` de los 3 dispositivos (IDs conocidos, keys vencidas)
- **Dispositivos**: `ebe4f458f0427bc8a08lgy` (10.164.254.80), `eb3825efd880cdf31e9wlv` (10.164.254.79), `ebf14bbe0ab5339fbfufnw` (10.164.254.125) — todos v3.3
- **Para obtener keys**: renovar plan IoT Core en Tuya (trial ya usado, requiere pago) O capturar con Wireshark durante reemparejamiento del dispositivo
- **Estado actual**: suscripción Tuya vencida desde 2026-03-31 — comandos cloud bloqueados con error 28841002

### Control de TV vía red (Android TV Remote API)
- **TV**: Challenger 55" Smart TV (Android TV) — mantiene WiFi activo en standby
- **Método**: `androidtvremote2` (Python puro, puerto 6466, protocolo Google) — sin ADB, sin config extra en el TV
- **Funciones**: encender / apagar / (ampliable: volumen, fuente, etc.)
- **Pendiente**: IP fija por DHCP reservado + integrar en módulo domótica de TUC TUC

---

---

## MÓDULO: Admin Agent — Acceso remoto DBF desde browser (2026-04-19) ✅

### Arquitectura
- `admin_agent.py` corre en el PC del cliente (donde está Administrator VFP)
- Lee `C:\S.A.R\RutaBaseDatos\ruta.dbf` para auto-descubrir la BD activa
- Lee `admin_agent.ini` para nombre descriptivo del equipo (ej. "Oficina Rafael")
- Detecta IP local automáticamente con `socket`
- Hace check-in en Render con nombre + ip_local + ruta_bd
- Consultas se procesan en **thread separado** — ping loop no se bloquea
- Render actúa como relay; consultas se borran de BD después de entregarse (cero acumulación)

### Arranque agente
```
cd "C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos"
python admin_agent.py --cliente rafael
```
El nombre visible viene de `admin_agent.ini`:
```ini
[agent]
nombre = Oficina Rafael
```

### Flujo de uso
1. PC cliente: editar `admin_agent.ini` con nombre descriptivo, correr agente
2. Browser: `https://tuc-tuc.onrender.com/admin/consultas`
3. **Paso 1** — buscar tercero por NIT o nombre (autocomplete 3 chars, spinner mientras busca)
4. **Paso 2** — buscar cuenta por código o nombre (solo TIPO='D')
5. **Paso 3** — Desde/Hasta lapso, empresa, límite → Consultar

### Selector de agente
- Dropdown muestra todos los agentes visibles para el usuario logueado (✅/❌)
- Muestra nombre del equipo + ruta BD activa
- Administrador ve todos; ClienteVFP ve solo los asignados
- Refresca cada 15s automáticamente

### Gestión de permisos — `/admin/agentes`
- Tabla de agentes registrados (nombre, ip, ruta_bd, estado)
- Por cada usuario ClienteVFP: checkboxes de agentes autorizados
- Guardar → escribe en tabla `admin_agent_permisos`

### Consultas disponibles
| tipo | descripción |
|---|---|
| `reg_ctas` | Movimientos contables con filtros Desde/Hasta/empresa/cuenta/tercero |
| `buscar_nit` | Autocomplete tercero por NIT o nombre → devuelve cod_ter |
| `buscar_cuenta` | Autocomplete cuenta por código o nombre (solo TIPO='D') |

### Rendimiento REG_CTAS (1.3M registros)
- numpy vectorizado: 0.62s total
- Rango lapso YYYYMM vectorizado (yr_int*100+mn_int)
- TERCEROS: binario directo (evita IMAGEN/DESCRIPCIO C(254))
- CUENTA: dbf lib (sin campos grandes, más simple)

### Campos DBF clave — REG_CTAS (record_size=345)
| Campo | Tipo | Offset | Len |
|---|---|---|---|
| CONSECUTIV | N | 1 | 10 |
| CUENTA | C | 11 | 15 |
| LAPSO | D | 26 | 8 — "YYYYMMDD" |
| FECHAHORA | T | 34 | 8 — Julian Day + ms |
| TERCERO | N | 42 | 10 |
| EMPRESA | C | 52 | 10 |
| TOT_DEB | N | 108 | 10 |
| TOT_CRE | N | 118 | 10 |

### Campos DBF clave — TERCEROS (record_size=739)
- COD_TER N(10) offset=1, NOMBRE C(50) offset=11, IDENTIFICACION C(15) offset=61
- NO leer con dbf lib (IMAGEN/DESCRIPCIO C(254) tardan 16s)

### Campos DBF clave — CUENTA
- CODIGO C(15), NOMBRE C(40), CUENTAPADRE C(15), NATURALEZA C(1), TIPO C(1)
- Filtrar solo TIPO='D' para autocomplete
- Leer con dbf lib (sin campos grandes)

### Tablas BD Render
- `admin_agent_sesiones` — token, activo, nombre, ip_local, ruta_bd, ultimo_ping
- `admin_agent_consultas` — tipo, parametros, respuesta, estado (se borra al entregar)
- `admin_agent_permisos` — usuario_id, cliente_id (m-m)

### Endpoints Render
- `POST /api/admin-agent/checkin` — agente se registra con nombre/ip/ruta_bd
- `POST /api/admin-agent/ping` — ping + actualiza ruta_bd + recibe consulta pendiente
- `POST /api/admin-agent/respuesta` — agente entrega resultado
- `POST /api/admin-agent/consultar` — browser encola consulta
- `GET /api/admin-agent/resultado/<id>` — browser polling (borra consulta al entregar)
- `GET /api/admin-agent/agentes` — lista agentes visibles para usuario actual
- `GET/POST /api/admin-agent/permisos/usuario/<uid>` — gestión permisos

### Autenticación
- `rol='Administrador'`: ve todos los agentes, accede a `/admin/agentes`
- `rol='ClienteVFP'`: ve solo agentes en `admin_agent_permisos` para su usuario_id
- Auto-migra `admin_cliente_id` existente → tabla permisos al primer arranque

### Pendientes Admin Agent
- Crear usuario ClienteVFP para Pilar en BD Render (SQL directo)
- Configurar arranque automático en PC Pilar (Task Scheduler o Startup)
- Empaquetar `admin_agent.py` como `.exe` con ícono en escritorio
- Ampliar consultas: PROD_FACT1, SAL_DOC, etc.
- WireGuard como alternativa directa (ver `docs/wireguard_setup.md`)

---

## Flujo chat Rafael↔Merlin — Merlin Daemon v1.0

**2026-04-11**: `captura_watcher.ps1` + `chat_merlin_bridge.py` fusionados en un solo daemon.

### Proceso único: `merlin_daemon.py`
- Ruta: `C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\merlin_daemon.py`
- Startup: `TucTuc_MerlinDaemon.vbs` (vbHide=0, sin ventana)
- Lock port: 47835
- Log: `C:\Users\RAFAEL OLIVARES\merlin_daemon.log`

### Tres responsabilidades en un loop:
| Loop | Cada | Qué hace |
|---|---|---|
| A — Bridge usuarios | 2s | Atiende conversaciones de usuarios con Merlin (tabla `conversaciones`+`mensajes`) |
| B — Captura watcher | 10s | Detecta mensajes de Rafael en `chat_mensajes canal='captura'`, activa Claude Code via SendKeys (pywin32) |
| C — Heartbeat | 60s | Reporta idle/cursor/audio a `/api/domotica/heartbeat` |

### Flujo Rafael → Merlin:
1. Rafael escribe en `/chat` → `chat_mensajes` con `canal='captura'`
2. Daemon detecta (cada 10s) → activa terminal Claude Code con `__MERLIN__` via pywin32 SendKeys
3. Claude Code lee BD, responde, inserta en `chat_mensajes (rol='assistant')`
4. Frontend polling muestra la respuesta

### Archivos eliminados (2026-04-11):
- `captura_watcher.ps1` — reemplazado por merlin_daemon.py
- `TucTuc_CapturaWatcher.vbs` y `TucTuc_CapturaWatcher.bat` — del Startup
- `tuctuc_merlin_bridge.bat` — del Startup
(el archivo `chat_merlin_bridge.py` se conserva como referencia pero ya no corre)

### Startup Windows activo:
- `TucTuc_MerlinDaemon.vbs` — lanza `merlin_daemon.py` oculto
- `monitor_tuctuc_b4e14ba7.vbs` — monitor heartbeat independiente
- `AlegraDaemon.exe` — daemon Alegra VFP
