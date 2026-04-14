# Estado de Sesión Activa
_Actualizado: 2026-04-14_

## Módulos en trabajo esta sesión
1. **TUC TUC — Restaurantes**: tipo `'ambos'` (carta + menú del día)
2. **VFP / SAR — Alegra**: separación met_tarjet en met_tdebito + met_tcredit

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

### CDX APPEND — análisis técnico (pendiente)
- `SELECT * FROM PROD_FACT1` (sin WHERE) muestra todos los registros incluidos los de la interfaz ✅
- `SELECT ... WHERE FECHAHORA >= fecha` no los muestra ❌ — Rushmore usa CDX que Python no actualizó
- VFP COM (`VisualFoxPro.Application.7`) requiere VFP IDE instalado — cliente solo tiene runtime
- **Solución pendiente**: PRG compilado (.fxp) que Administrator pueda llamar, o rutina interna REINDEX

### Pendientes SAR — próxima sesión
1. **Despliegue PC Pilar** — sesión 2026-04-14 ~3pm — checklist en `docs/checklist_despliegue_pilar.md`
2. **CDX APPEND fix** — solución sin VFP IDE en cliente
3. **Auditar bolsa** — verificar cuenta 240807 cuadrada con fix ln_bolsa (precio×cantidad)
4. **Auditar vendedores** — verificar VENDEDOR ≠ 0 en PROD_FACT1
5. **Progreso sync en tiempo real** — mostrar facturas descargándose en grilla Pendientes

### Estado de archivos SAR

| Archivo | Estado |
|---|---|
| `s.a.r.prg` | ✅ Limpio — sin batch mode |
| `interfaz_allegra.prg` | ✅ Limpio — no se usa en automático |
| `alegra_timer.prg` | ⏸️ RETURN al inicio — desactivado |
| `fondo_menu_limpio.scx` | ✅ Sin cambios |
| `alegra_daemon.py` | ✅ v2.8 — intervalo en segundos, recompilado 2026-04-14 |
| `configurar_allegra.py` | ✅ v2.8 — 4 paneles, intervalo segundos, UI adaptativa, Borrado DBF + Reiniciar deshabilitados si no pausado |
| `interfaz_allegra.py` | ✅ 4 fases + alertas parciales — 4 bugs corregidos 2026-04-14 |
| `allegra_sync.py` | ✅ campo fecha_hora T — datetime exacto de Alegra |

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
