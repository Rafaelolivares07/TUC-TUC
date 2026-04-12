# Estado de Sesión Activa
_Actualizado: 2026-04-11_

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
- `alegra_daemon.py` → **v2.8** (timeout 1800s mínimo basado en intervalo)
- `configurar_allegra.py` → **v2.8** (branding ADMINISTRATOR INTERFASES, CDX fix VFP COM, diagnóstico error real)
- `interfaz_allegra.py` → **4 fases ACTIVAS Y COMPLETAS** (fix ln_bolsa, fix ventas doble resta)
- `allegra_sync.py` → fix punto y coma ESTRUCTURA_DBF (creación tabla post-reinicio)

### Lo que está funcionando (2026-04-12)
- **4 fases completas**: f_prod1, f_standar, f_costos, f_contab — todas activas y probadas en ciclos reales
- **f_standar**: `_standar()` lee TRANS_MAT (kits), inserta REG_PROD, actualiza REG_PROD_SALDOS — NO es stub
- **Multi-pagos**: campo `pagos` JSON con todos los payments de Alegra — asientos contables cuadrados para facturas con mezcla de métodos (cash+tarjeta+CxC)
- **NITs auto-creados**: toggle auto_nit (Canvas píldora) — si ON, crea tercero en TERCEROS.dbf automáticamente y marca como 'creado' en alegra_nits_pend
- **Equivalencia vendedores**: sección en tab Configuracion — seller_id Alegra → vendedor Administrator (MESEROS.dbf internamente, nunca "mesero" en UI); guarda en alegra_vendedores.dbf
- **Reinicio seguro**: diálogo post-reinicio sugiere MIN(borrado)-1 por empresa como nuevo num_inicio; bloquea Reanudar/Un ciclo hasta confirmar
- **CDX fix en reinicio**: `_reiniciar_trabajo()` usa VFP COM (`VisualFoxPro.Application.7`) para DELETE en tablas Administrator — VFP DELETE actualiza CDX; Python dbf.delete() no lo hace
- **Timeout dinámico daemon**: `max(300, max_fact × 90)` — nunca corta ciclo válido
- **Bloqueo configuración inválida**: no guarda si `max_fact × 90s > intervalo × 60s`
- **Label estimado**: muestra duración estimada local/servidor/timeout en tiempo real
- **Scroll bloqueado en todos los comboboxes**: met_pago, tipo_doc, vendedores — `<MouseWheel>` → `"break"`
- **codepage cp1252** explícito en TODOS los `dbf.Table()` del daemon y formulario
- **met_pago comboboxes siempre `state="readonly"`** — nunca `disabled`
- **guardar() valida tip_doc en cod_map** — no guarda si display inválido

### Cambios sesión 2026-04-12
- **Branding**: UI renombrada a "ADMINISTRATOR INTERFASES" — título, splash, header, mensajes. Variables técnicas y mapeos sin cambio.
- **Diagnóstico fuente**: `_consultar_alegra()` captura error real por empresa en `_alegra_error` dict — muestra "Error: ..." en lugar de "..." cuando falla API empresa 02
- **CDX fix — root cause y solución**:
  - Causa: Python `dbf.delete()` marca 0x2A en DBF pero NO actualiza el CDX estructural
  - Consecuencia: al filtrar por fecha 10-abr en `contabilidad_resumen_por_documentos.scx`, VFP Rushmore encontraba registros borrados de 10-abr (con FECHAHORA del procesamiento = 11-abr) vía entradas obsoletas del CDX
  - Solución: nuevo método `_vfp_delete_en_tabla()` — crea PRG temporal + ejecuta vía COM `VisualFoxPro.Application.7` en SHARED mode; VFP DELETE actualiza CDX correctamente
  - Aplica a pasos 5-9 del reinicio: PROD_FACT1, REG_PROD, REG_CTAS, SAL_DOC, reg_ctas_notas_documentos
  - Pasos 3-4 (allegra_pendientes, alegra_nits_pend) siguen con Python dbf.delete() — son tablas propias sin CDX estructural

### Pendientes SAR — próxima sesión
1. **Probar reinicio con VFP COM** — verificar que `_vfp_delete_en_tabla()` no genera error al correr con Administrator activo; confirmar CDX limpio post-reinicio
2. **Auditar bolsa** — verificar cuenta 240807 cuadrada con fix ln_bolsa (precio×cantidad)
3. **Auditar vendedores** — verificar VENDEDOR ≠ 0 en PROD_FACT1
4. **Diálogo post-reinicio** — probar que aparece centrado y operable
5. **Label "Próximo ciclo"** — corregir para mostrar tiempo real (inicio_ciclo + duración + intervalo)
6. **Progreso sync en tiempo real** — mostrar facturas descargándose en grilla Pendientes durante primer sync

### Estado de archivos SAR

| Archivo | Estado |
|---|---|
| `s.a.r.prg` | ✅ Limpio — sin batch mode |
| `interfaz_allegra.prg` | ✅ Limpio — no se usa en automático |
| `alegra_timer.prg` | ⏸️ RETURN al inicio — desactivado |
| `fondo_menu_limpio.scx` | ✅ Sin cambios |
| `alegra_daemon.py` | ✅ v2.8 — timeout basado en intervalo (mín 1800s) |
| `configurar_allegra.py` | ✅ v2.8 — branding ADMINISTRATOR INTERFASES, CDX fix VFP COM en reinicio, diagnóstico error real |
| `interfaz_allegra.py` | ✅ 4 fases ACTIVAS — fix bolsa (precio×cantidad), fix ventas (no doble resta), multi-pagos JSON |
| `allegra_sync.py` | ✅ fix ESTRUCTURA_DBF punto y coma (todos los campos) |

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
