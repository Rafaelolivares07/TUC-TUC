# Estado de Sesión Activa
_Actualizado: 2026-04-07_

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
- `alegra_daemon.py` → **v2.6**
- `configurar_allegra.py` → **v2.7**
- `interfaz_allegra.py` → **4 fases código listo — f_standar stub**

### Cambios sesión 2026-04-08 — configurar_allegra.py v2.7
- **Splash screen** al abrir: ventana visible inmediata con mensajes de progreso, init diferido
- **Dynamic input states**: bordes verde/gris según si el tipo_doc seleccionado tiene configurados los inputs contables en AYUDA + CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR
- **kw_bolsa**: campo global C(40) en allegra_config.dbf — el usuario define la keyword que identifica el ítem bolsa (default "BOLSA") — configurable desde tab Configuracion
- **num_inicio per-empresa**: auto-populated desde PROD_FACT1 — `_sugerir_num_inicio()` filtra por `tip_fac` = tipo_doc seleccionado, retorna MAX `cod_fac` por empresa; label "Sugerido: X" en verde
- **Combobox tipo_doc expandido**: frame_top con pack layout (`fill="x", expand=True`) — ancho máximo del texto más largo
- **Barra inferior fija** (fuera del scroll): botón "Guardar configuracion" + indicador "Hay cambios sin guardar"
- **JSON monitoreo completo**: incluye `tip_doc_def`, `met_*`, `kw_bolsa`, estado ventana (`ventana.abierta`)
- **Bug crítico corregido**: `_migrar_allegra_config` — descartado `add_fields` + backup/restore frágil; ahora RECREA la tabla completa desde cero cuando hay campos nuevos, preservando todos los datos con `os.replace` atómico

### Lo que está funcionando
- Daemon v2.6 corre cada N minutos: allegra_sync.py → allegra_pendientes.dbf → interfaz_allegra.py → PROD_FACT1
- `FASES_ACTIVAS = ['f_prod1', 'f_standar', 'f_costos', 'f_contab']` — f_standar es stub
- f_costos + f_contab: código completo (sin probar en BD real aún)
- Tab Configuracion con scroll vertical; Combobox tipo doc expandido; bordes dinámicos por tipo_doc
- `leer_config()` nunca falla; `guardar_config()` APPEND si empresa no existe; PC virgen safe
- `estado_proceso.json` captura estado completo del formulario (útil para diagnóstico por Merlin)

### Pendientes SAR — próxima sesión
1. **PRIORIDAD 0: Verificar que datos persisten** — abrir form, configurar, guardar, cerrar, reabrir y confirmar que tip_doc_def + met_* se mantienen (fix v2.7 aplicado)
2. **PRIORIDAD 1: Correr ciclo completo** — Click "Sincronizar ahora", revisar log
3. Implementar `_standar()` real (REG_PROD + REG_PROD_SALDOS) — actualmente stub
4. UI mapeo vendedores (tab Configuracion)
5. Auto-refresh grillas Facturas y Terceros cada 30s
6. `reiniciar_proceso` debe limpiar reg_costos_temporal + f_costos/f_contab

### Estado de archivos SAR

| Archivo | Estado |
|---|---|
| `s.a.r.prg` | ✅ Limpio — sin batch mode |
| `interfaz_allegra.prg` | ✅ Limpio — no se usa en automático |
| `alegra_timer.prg` | ⏸️ RETURN al inicio — desactivado |
| `fondo_menu_limpio.scx` | ✅ Sin cambios |
| `alegra_daemon.py` | ✅ v2.6 |
| `configurar_allegra.py` | ✅ **v2.7** — splash, dynamic inputs, kw_bolsa, num_inicio sugerido, fix persistencia |
| `interfaz_allegra.py` | ✅ 4 fases código listo (f_standar stub) |
| `allegra_sync.py` | ✅ Incluye nomb_cli desde Alegra API |

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

## Flujo chat Rafael↔Merlin
`captura_watcher.ps1` → `__MERLIN__` → esta terminal
