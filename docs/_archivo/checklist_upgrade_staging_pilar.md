# Checklist Upgrade Staging — PC Pilar Peralta
_Versión: 2026-04-16 — Arquitectura staging (Python → stg_* → PROCESADOR_STAGING.EXE → tablas reales)_
_**COMPLETADO: 2026-04-17** — Upgrade ejecutado en PC Pilar exitosamente_

---

## QUÉ CAMBIA CON ESTE UPGRADE

**Problema que resuelve:** Python escribía directamente en tablas DBF productivas sin actualizar índices CDX → consultas por fecha/filtros en Administrator devolvían vacío.

**Solución:** Python ahora escribe en tablas de staging (`stg_*`). Un EXE VFP compilado (`PROCESADOR_STAGING.EXE`) lee el staging y hace los APPEND en las tablas reales — VFP actualiza CDX automáticamente. Los terceros nuevos van por `stg_terceros` → PROCESADOR abre TERCEROS via DBC (`datos_sar`).

---

## ARCHIVOS A TRANSMITIR A C:\S.A.R\ EN PILAR

### Reemplazar (ya existen):
| Archivo | Cambio |
|---|---|
| `alegra_daemon.py` | Agrega llamada a PROCESADOR_STAGING.EXE en cada ciclo |
| `AlegraDaemon.exe` | Recompilado desde alegra_daemon.py actualizado |
| `interfaz_allegra.py` | Staging completo + stg_terceros para NITs nuevos |
| `allegra_sync.py` | Lee facturas de Alegra y llena allegra_pendientes.dbf |
| `instalar_allegra_bd.py` | Crea tablas stg_* incluyendo stg_terceros |

### Nuevos (no existen en Pilar):
| Archivo | Descripción |
|---|---|
| `PROCESADOR_STAGING.EXE` | Mueve staging → tablas reales (VFP, actualiza CDX). Procesa stg_terceros via DBC. |

> Todos estos archivos están listos en `C:\S.A.R\dist_interfaz\`

---

## CHECKLIST DE UPGRADE

### PASO 0 — Verificaciones previas (en PC Rafael, antes de ir)

- [x] Pruebas locales OK — ciclo completo corrió sin errores (2026-04-16) ✅
- [x] `AlegraDaemon.exe` recompilado — v2.8 ✅
- [x] `PROCESADOR_STAGING.EXE` compilado con stg_terceros + OPEN DATABASE datos_sar ✅
- [x] `dist_interfaz\` actualizado con todos los archivos de hoy ✅
- [x] Versión AlegraDaemon.exe: **v2.8** ✅

---

### PASO 1 — Preparar la sesión remota

- [x] Conectar vía AsistenciaTucTuc ✅
- [x] Verificar que Administrator está cerrado en todos los PCs ✅
- [x] **PAUSAR el daemon** — creado `alegra_daemon_pausa.txt` vía comando remoto ✅

---

### PASO 1B — Reindexar BD de Pilar

> La versión anterior escribía directo en DBFs sin actualizar CDX — los índices pueden estar dañados.
> Este paso es obligatorio antes de activar el nuevo sistema.

- [x] Confirmar que Administrator está cerrado en TODOS los PCs ✅
- [x] Ejecutar `REINDEXADOR.EXE` desde Desktop — ejecutado vía Enter remoto ✅
- [x] Finalizó sin errores ✅

---

### PASO 2 — Transmitir archivos a C:\S.A.R\

Transmitir vía relay AsistenciaTucTuc desde `C:\S.A.R\dist_interfaz\`:

- [x] `alegra_daemon.py` → `C:\S.A.R\alegra_daemon.py` ✅
- [x] `AlegraDaemon.exe` → `C:\S.A.R\AlegraDaemon.exe` ✅
- [x] `interfaz_allegra.py` → `C:\S.A.R\interfaz_allegra.py` ✅
- [x] `instalar_allegra_bd.py` → `C:\S.A.R\instalar_allegra_bd.py` ✅
- [x] `PROCESADOR_STAGING.EXE` → `C:\S.A.R\PROCESADOR_STAGING.EXE` ✅

---

### PASO 3 — Crear tablas staging en la BD de Pilar

```cmd
python C:\S.A.R\instalar_allegra_bd.py
```

Verificar en la salida:
- [x] `stg_lotes.dbf` ✅
- [x] `stg_prod_fact1.dbf` ✅
- [x] `stg_reg_prod.dbf` ✅
- [x] `stg_reg_prod_sal.dbf` ✅
- [x] `stg_reg_ctas.dbf` ✅
- [x] `stg_sal_doc.dbf` ✅
- [x] `stg_nota.dbf` ✅
- [x] `stg_terceros.dbf` ✅

> Las tablas se crean en `\\192.168.1.104\BASEDATOSEMPRESAS\`

---

### PASO 4 — Prueba con un ciclo manual

- [x] Ciclo manual ejecutado vía línea de comandos remoto ✅
- [x] `PROCESADOR_STAGING.EXE completado OK` — empresa 02 y LP ✅
- [x] 2 facturas procesadas, 0 inconsistencias ✅
- [x] Administrator abierto — registros visibles ✅
- [x] Filtros por fecha funcionando ✅
- [x] Sin duplicados ✅

---

### PASO 5 — Reanudar daemon

- [x] Daemon reiniciado por Pilar manualmente ✅
- [x] AlegraDaemon.exe corriendo en producción ✅

---

## ROLLBACK (si algo falla)

Si el upgrade falla y hay que volver a la versión anterior:

1. Pausar daemon
2. Restaurar archivos anteriores (deben estar guardados antes de reemplazar)
3. Las tablas `stg_*` no afectan al sistema anterior — pueden quedar o borrarse
4. `PROCESADOR_STAGING.EXE` simplemente no se llama si el daemon es el anterior

---

## DATOS CLAVE

| Concepto | Valor |
|---|---|
| BD cliente | `\\192.168.1.104\BASEDATOSEMPRESAS\` |
| Scripts | `C:\S.A.R\` |
| Dist local Rafael | `C:\S.A.R\dist_interfaz\` |
| Log daemon | `C:\S.A.R\alegra_daemon.log` |
| Archivo pausa | `C:\S.A.R\alegra_daemon_pausa.txt` |
