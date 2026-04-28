# Estado de Sesión Activa
_Actualizado: 2026-04-26 (sesión restaurantes + DB lock)_

## MÓDULO: TUC TUC — Restaurantes (sesión 2026-04-26)

### DB lock en tabla terceros — RESUELTO ✅
- **Causa**: `idle in transaction` del daemon Merlin (PC local) tenía ShareLock sobre `terceros` + 63 conexiones de código viejo con `ALTER TABLE terceros` encoladas → todo timeout
- **Fix**: killed 63 sesiones bloqueadas vía URL externa Render + `_tablas_listas = True` ya estaba en producción (commit `2cfb2ed`)
- **Referencia**: `docs/_memoria/project_db_lock_terceros.md` + `docs/_memoria/reference_render_db_externa.md`

### Sticky pedido activo — IMPLEMENTADO ✅
- Después de confirmar pedido, `#barra-pedir` no desaparece — cambia a modo "Tu pedido"
- Muestra TODOS los pedidos activos separados por `·` (ej: `Americana · Criolla`)
- Badge: amarillo "Preparando..." / verde "LISTO ✓" — se actualiza con el polling cada 10s
- Al recargar la página: si hay pedidos y carrito vacío, sticky se activa automáticamente
- Al agregar nuevo ítem: sticky vuelve a modo carrito
- Commits: `21bf5a4`, `cb212e8`, `23b3d2d`, `fcc1690`

### Pendientes restaurantes
- Landing page restaurantes — pendiente video Rafael con CapCut Android
- Prueba real con restaurante tipo `ambos` en todas las URLs

---

## Módulos en trabajo esta sesión
1. **Administrator Web** ✅ DEPLOYADO EN PILAR — reporte arranque_web automático
2. **Admin Agent** ✅ DEPLOYADO EN PILAR — reporte arranque_agent automático
3. **PilarSetup.exe** ✅ v2 en GitHub Releases — UAC automático + reportes remotos
4. **Merlin Chat** ✅ — Wizard SYSTEM_PROMPT corto, errores silenciosos, ANTHROPIC_API_KEY eliminada del env subprocess
5. **merlin_daemon + admin_agent_bp** ✅ — ciclo completo: Pilar reporta → servidor → chat_mensajes captura → Merlin se activa

## Sesión 2026-04-28 — Migración sin Render + UI arranque

### Infraestructura actual (sin Render)
- **Servidor**: Flask local (TucTucV2, puerto 5000) + ngrok
- **Dominio ngrok estático**: `https://outclass-zealous-secret.ngrok-free.dev` (permanente, cuenta `sar_colombia_valle@hotmail.com`)
- **BD**: PostgreSQL local `tuctuc_local` / `localhost:5432`

### tuctuc_links.pyw — arranque con un clic
- Acceso directo "TucTuc Links" en escritorio
- Arranca Flask + ngrok automáticamente
- Muestra enlaces Pilar + Restaurantes listos para copiar
- Publica URL en GitHub (`ngrok_url.txt`, branch main) como fallback

### Cambios código Pilar (sin Render)
- `pilar_setup.py` — sin checkin/reporte Render; ini con `servidor = ` vacío
- `admin_agent.py` — auto-descubre URL desde GitHub; cachea en ini
- `administrator_web.py` — `_reportar_arranque` lee ini; silencioso si vacío
- `restaurantes.py` — fix `sys.stdout.flush()` NoneType (Flask sin consola)
- `PilarSetup.exe` — reconstruido y subido a GitHub Releases `PilarSetup-v1.0`

### Estado Pilar
- EXE listo en GitHub Releases — pendiente que Pilar lo descargue y ejecute
- Cuando lo ejecute: instalación local completa (sin notificación a Merlin — Render eliminado)

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

### Despliegue Pilar ✅ (2026-04-24) — VÍA PilarSetup.exe
No requiere sesión remota. Pilar descarga y ejecuta `PilarSetup.exe` desde GitHub Releases (tag `PilarSetup-v1.0`).
El EXE hace todo: copia archivos, pip install, startup VBS, FORMULARIOS.DBF + permisos, check-in + reporte remoto.
Merlin recibe notificación automática via `__MERLIN__` cuando Pilar ejecuta el instalador.

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

### Estado Admin Agent ✅ COMPLETO (2026-04-24)
- Usuario Pilar `pilar/pilar2026 ClienteVFP` en BD V2 ✅
- Arranque automático en PC Pilar: VBS en shell:startup via PilarSetup.exe ✅
- `admin_agent.py` reporta arranque_agent al servidor después de checkin ✅
- Tabla `admin_agent_reportes` en BD V2 ✅
- Ciclo notificación Merlin: reporte → chat_mensajes captura → __MERLIN__ ✅

### Pendientes Admin Agent
- Ampliar consultas: PROD_FACT1, SAL_DOC
- WireGuard como alternativa directa (ver `docs/wireguard_setup.md`)
- Otros clientes además de Pilar

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
