# Estado de Sesión Activa
_Actualizado: 2026-04-06_

## Módulo en trabajo
**VFP / SAR — Integración Alegra → Python directo a DBF**

---

## PRÓXIMA SESIÓN — Estado actual

### Versiones
- `alegra_daemon.py` → **v2.6**
- `configurar_allegra.py` → **v2.6**
- `interfaz_allegra.py` → **4 fases código listo — f_standar stub**

### Lo que está funcionando / implementado
- Daemon v2.6 corre cada N minutos: allegra_sync.py → allegra_pendientes.dbf → interfaz_allegra.py → PROD_FACT1
- `FASES_ACTIVAS = ['f_prod1', 'f_standar', 'f_costos', 'f_contab']` — las 4 fases declaradas; f_standar es stub
- f_costos + f_contab: código completo (sin probar en BD aún)
- Tab Configuracion con scroll vertical (Canvas+Scrollbar, mousewheel al hover)
- Combobox tipo doc muestra "013 — FACTURA VENTA POS" — filtra TIPO_DOC.ESTADO_INV=3 AND AUTO_EMP
- Combobox met_pago: valores fijos Alegra (cash, credit-card, debit-card, transfer, credit, check, online, bank-remittance)
- `leer_config()` nunca falla — devuelve defaults si tabla vacía o inexistente
- `guardar_config()` hace APPEND si la fila de empresa no existe — seguro en PC virgen
- `_met_coincide()` comparación exacta (ya no comma-split)

### Pendientes — próxima sesión
1. **PRIORIDAD: Prueba en backup** (`basedatosempresas_TEST`) — apuntar ruta.dbf, correr ciclo completo
2. Implementar `_standar()` real (REG_PROD + REG_PROD_SALDOS) — actualmente stub
3. UI mapeo vendedores (tab Configuracion)
4. Auto-refresh de grillas de Facturas y Terceros
5. Corregir `_sugerir_num_inicio`: debe leer MAX de PROD_FACT1, no de allegra_pendientes
6. `reiniciar_proceso` debe limpiar reg_costos_temporal + f_costos/f_contab

### Pasos para prueba en backup
1. En `ruta.dbf` → cambiar ruta al DBC de `basedatosempresas_TEST` (o via formulario si tiene opción)
2. En formulario: definir BD esperada → guardar
3. Verificar que allegra_config.dbf tiene los 5 campos nuevos (tip_doc_def, met_*)  — `_migrar_allegra_config` los crea
4. Configurar tipo doc y met_pago en tab Configuracion
5. Click "Sincronizar ahora" → revisar log completo
6. Verificar PROD_FACT1, REG_CTAS, SAL_DOC en el backup

---

### Estado de archivos

| Archivo | Estado |
|---|---|
| `s.a.r.prg` | ✅ Limpio — sin batch mode |
| `interfaz_allegra.prg` | ✅ Limpio — no se usa en automático |
| `alegra_timer.prg` | ⏸️ RETURN al inicio — desactivado |
| `fondo_menu_limpio.scx` | ✅ Sin cambios |
| `alegra_daemon.py` | ✅ v2.6 |
| `configurar_allegra.py` | ✅ v2.6 — UI contabilización por empresa |
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

### Control de TV vía red (Android TV Remote API)
- **TV**: Challenger 55" Smart TV (Android TV) — mantiene WiFi activo en standby
- **Método**: `androidtvremote2` (Python puro, puerto 6466, protocolo Google) — sin ADB, sin config extra en el TV
- **Funciones**: encender / apagar / (ampliable: volumen, fuente, etc.)
- **Pendiente**: IP fija por DHCP reservado + integrar en módulo domótica de TUC TUC igual que los demás dispositivos Tuya

---

## Flujo chat Rafael↔Merlin
`captura_watcher.ps1` → `__MERLIN__` → esta terminal
