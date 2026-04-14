# Proyecto VFP — Administrator (SAR) — Contexto y Pendientes
_Actualizado: 2026-04-14 (sesión 7) — v2.8: 4 bugs interfaz_allegra, alertas parciales, intervalo segundos, 4 paneles facturas, UI adaptativa, recompile daemon._

---

## ⚡ ESTADO ACTUAL — 2026-04-14

### Arquitectura vigente
Python reemplaza VFP batch mode completamente. `interfaz_allegra.py` (Python) es el motor de procesamiento. Daemon v2.8 orquesta todo.

### Estado de archivos

| Archivo | Estado | Notas |
|---|---|---|
| `s.a.r.prg` | ✅ LIMPIO | Sin batch mode |
| `interfaz_allegra.prg` | ✅ LIMPIO | Solo referencia |
| `alegra_timer.prg` | ⏸️ DESACTIVADO | `RETURN` al inicio |
| `fondo_menu_limpio.scx` | ✅ Sin cambios | Timer presente pero retorna inmediatamente |
| `alegra_daemon.py` | ✅ **v2.8** | Intervalo en segundos; timeout `max(1800, intervalo_cfg)` — recompilado 2026-04-14 |
| `configurar_allegra.py` | ✅ **v2.8** | 4 paneles facturas, intervalo segundos N(4,0), UI adaptativa sh-60, Reiniciar en tab Estado |
| `interfaz_allegra.py` | ✅ **4 fases + alertas parciales** | 4 bugs corregidos 2026-04-14; _marcar_completo_con_alerta |
| `allegra_sync.py` | ✅ | campo fecha_hora T — datetime exacto de Alegra |

**Administrator abre sin inconvenientes para usuarios normales.** ✅

---

### Arquitectura multi-fase — interfaz_allegra.py

```python
FASES_ACTIVAS = ['f_prod1', 'f_standar', 'f_costos', 'f_contab']
# Las 4 fases están ACTIVAS y completas — probadas en ciclos reales
```

- `procesado=True` SOLO se setea cuando TODOS los campos en `FASES_ACTIVAS` están en True
- `_marcar_fases(fid, {'f_prod1': True})` — setea solo la fase, no toca `procesado`
- `_marcar_completo(fid)` — setea `procesado=True` + limpia `motivo` — solo cuando todo listo
- `procesar_empresa(empresa, max_por_ciclo)` — lee `max_fact` de allegra_config.dbf, limita el loop
- `main()` llama `procesar_empresa(empresa, max_por_ciclo=_leer_max_fact(empresa))` para cada empresa
- `procesar_empresa` marca las 4 fases juntas: `f_prod1`, `f_standar`, `f_costos`, `f_contab`
- Facturas con fases parcialmente hechas se retoman automáticamente en el próximo ciclo

### Fases implementadas en interfaz_allegra.py

| Fase | Función | Estado | Tablas escritas |
|---|---|---|---|
| f_prod1 | `_f_prod1()` | ✅ ACTIVO | PROD_FACT1 |
| f_standar | `_standar()` | ✅ ACTIVO | REG_PROD, REG_PROD_SALDOS — lee TRANS_MAT (kits), inserta REG_PROD, actualiza saldos |
| f_costos | `_reg_costos_temporal()` + `_costo_ventas_contabiliza()` | ✅ ACTIVO | reg_costos_temporal, REG_CTAS (2 filas/producto) |
| f_contab | `_contabilizar()` | ✅ ACTIVO | REG_CTAS (asientos), SAL_DOC (cuentas DOC_CRUZE=1) |

### Flujo f_costos — _costo_ventas_contabiliza()
- Replica `costo_ventas_contabiliza.prg` de VFP
- Carga `GRUPOS` → dict `{cod_grupo → (cuenta_inv, cuenta_cos)}`
- Carga `PRODUCTOS` → dict `{codigo → grupo}`
- Lee `reg_costos_temporal` (registros no eliminados)
- Por cada registro: lookup producto → grupo → cuentas → toma +2 de `REGCTA_CONSE`
- Inserta 2 filas en `REG_CTAS`: crédito inventario (tot_cre=costo) + débito costo ventas (tot_deb=costo)

### Flujo f_contab — _contabilizar()
- Parámetros: `tip_fac, num_doc, empresa, bodega, cod_ter_cliente, items_efectivos, val_pago, met_pago, ln_bolsa, fecha`
- Lee `met_efect/met_tarjet/met_transf/met_cxc` desde allegra_config.dbf para la empresa
- Gate check: `CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA` — si doc no configurado, aborta
- Carga `AYUDA` → dict `{consecutivo → objeto}` (objeto = nombre input VFP: TXT_ABONA_EFECTIVO, etc.)
- Calcula: `subtotal`, `iva`, `bolsas`, `ventas = subtotal` (bolsas ya excluidas de `items_efectivos` — NO restar de nuevo), `total = val_pago`
- `pvar[1]` = ventas (siempre; fila con DOCUMENTO_='' no tiene link AYUDA)
- Para filas con `DOCUMENTO_ > 0`: `AYUDA[DOCUMENTO_].OBJETO` → `_val_por_objeto()` → `pvar[var_con_pr]`
- `_val_por_objeto(objeto)`: mapea input VFP → valor según met_pago del usuario en allegra_config
  - TXT_IVA_DEFINITIVO → iva
  - TXT_BOLSA_IMPUESTO → bolsas
  - TXT_DESCUENTO_DEFINITIVO → 0
  - TXT_ABONA_EFECTIVO → total si met_pago == met_efect (exacto)
  - TXT_TARJETA_RECIBIDO → total si met_pago coincide con met_tdebito OR met_tcredit OR met_tarjet (legacy)
  - TXT_CONSIGNA_TRASFIERE → total si met_pago == met_transf (exacto)
  - TXT_COBRAR_CLIENTE → total si met_pago == met_cxc (exacto)
- `_met_coincide(met_pago, config_met)`: comparación exacta case-insensitive — NO comma-split
- Valores posibles de `met_pago` desde Alegra API: `cash`, `credit-card`, `debit-card`, `transfer`, `credit`, `check`, `online`, `bank-remittance`
- Maneja filas DIFERENCIA (balance)
- Inserta en REG_CTAS (+1 REGCTA_CONSE por asiento)
- Para cuentas DOC_CRUZE=1: INSERT/UPDATE SAL_DOC (cartera 130505)

### configurar_allegra.py — 4 tabs

1. **Configuracion** (con scroll vertical — Canvas+Scrollbar, mousewheel activo al hover):
   - BD esperada, max_fact, intervalo (spinboxes font 13, flechas visibles), num_inicio por empresa
   - **Diagnóstico Alegra** (debajo del intervalo): tabla dinámica con última factura en Alegra por empresa, num_inicio configurado y facturas estimadas a bajar. Se calcula al abrir la tab y al cambiar num_inicio. Llama `GET /invoices?limit=1&start=0` (~1s por empresa).
   - **Validación en tiempo real** (`_actualizar_estimado`): al cambiar max_fact o intervalo, muestra estimado local/servidor/timeout. Si `max_fact×90s ≥ 3600s` → label rojo "⚠ SUPERA EL TIMEOUT". Si `max_fact×90s > intervalo×60s` → naranja "⚠ supera el intervalo". `guardar()` bloquea si supera límites.
   - **Sección Contabilización** per empresa (LabelFrame "02 TV & Video" + "LP J&P"):
     - **Combobox tipo de documento** (readonly, width=40): muestra `"013 — FACTURA VENTA POS"`. Filtra `TIPO_DOC WHERE ESTADO_INV=3` (campo es `ESTADO_INV`, no `ESTADO_INVE`) AND `CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA` para la empresa. Mismo criterio que `facturar_cancelar.scx verifica_tipos_venta`. Guarda solo el código en allegra_config.
     - **Tabla emparejamiento met_pago**: 5 filas (todos comboboxes con scroll bloqueado):
       - Efectivo → `met_efect` (ej. `cash`)
       - Tarjeta débito → `met_tdebito` (ej. `debit-card`) — cuotas=0 → F_PAGO_TDEBITO
       - Tarjeta crédito → `met_tcredit` (ej. `credit-card`) — cuotas>0 → F_PAGO_TCREDITO
       - Transferencia → `met_transf` (ej. `transfer`)
       - Cobrar cliente → `met_cxc` (ej. `credit`)
   - Campos en `allegra_config.dbf`: `tip_doc_def C(10)`, `met_efect C(30)`, `met_tarjet C(30)` (legacy), `met_tdebito C(30)`, `met_tcredit C(30)`, `met_transf C(30)`, `met_cxc C(30)` — `_migrar_allegra_config()` los agrega si no existen; migra `met_tarjet` → `met_tcredit` automáticamente
   - `guardar_config(cfg_path, max_fact, intervalo, num02, numLP, per_empresa={})` — UPDATE si fila existe, APPEND si no existe — nunca falla en PC virgen
   - `leer_config()` — devuelve defaults para empresas faltantes, nunca lanza excepción — formulario siempre abre
   - `_asegurar_filas_config()` — inserta filas para 02/LP si allegra_config.dbf está vacío
   - **Todos los comboboxes** bloqueados contra scroll (`<MouseWheel>` → `"break"`) — previene desconfiguración silenciosa
   - **guardar()** valida que tip_doc sea un valor válido del combobox — bloquea save si valor inválido (eliminado fallback peligroso)

2. **Facturas**: 3 grillas expandibles (PanedWindow) — Pendientes / Con inconsistencias / Procesadas (con fases)
   - Panel "Procesadas" muestra columnas: PROD_FACT1 | REG_PROD | Costos | Contabilidad (SI / -)
   - Botón **"Revertir fases seleccionada"**: abre `_DialogRevertirFases` con checkboxes por fase
     - Resetea f_prod1/f_standar/f_costos/f_contab a False + procesado=False + limpia motivo
     - Factura vuelve a "Pendientes" y el daemon la retoma
     - Aviso especial si revierte f_prod1: usuario debe eliminar registros de PROD_FACT1 manualmente en Administrator
3. **Terceros**: NITs no en TERCEROS — Empresa | NIT | Nombre cliente | Facturas | Acción (Crear/Ignorar/Pendiente)
   - **Crear en Administrator**: diálogo con nombre pre-llenado desde Alegra → escritura binaria a TERCEROS.dbf → próximo ciclo procesa automático
4. **Estado & Log**: indicador daemon, tabla fases, log último ciclo, Pausar + Compactar DBF

### Tablas DBF del módulo (en carpeta BD activa)
| Tabla | Descripción |
|---|---|
| `allegra_config.dbf` | Config por empresa: max_fact, intervalo, num_inicio, ultimo_log (memo), tip_doc_def, met_efect, met_tarjet (legacy), met_tdebito, met_tcredit, met_transf, met_cxc |
| `allegra_pendientes.dbf` | Items pendientes — campos fase: f_prod1, f_standar, f_costos, f_contab (L); motivo C(100); nomb_cli C(60) |
| `alegra_tiposdoc.dbf` | Mapeo tipo_doc Alegra → TIP_ADMIN |
| `alegra_nits_pend.dbf` | NITs no encontrados — nit, empresa, nombre C(60), num_docs, accion (pendiente/ignorar/creado) |
| `alegra_vendedores.dbf` | Mapeo seller_id Alegra → cod_ter Administrator |
| `reg_costos_temporal.dbf` | Tabla temporal costos — se marca deleted al inicio de cada factura (NUNCA PACK desde Python) |

### Tablas Administrator que escribe Python (fases costos/contab)
| Tabla | Fase | Acceso |
|---|---|---|
| `PROD_FACT1` | f_prod1 | READ_WRITE |
| `REG_CTAS` | f_costos + f_contab | READ_WRITE (INSERT) |
| `REGCTA_CONSE` | f_costos + f_contab | READ_WRITE (+2 costos, +1 contab) |
| `SAL_DOC` | f_contab (DOC_CRUZE=1) | READ_WRITE (INSERT/UPDATE cartera) |
| `reg_costos_temporal` | f_costos | READ_WRITE (delete + append, sin PACK) |

### Tablas Administrator que solo lee Python
| Tabla | Para qué |
|---|---|
| `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR` | Template de asientos por tipo doc + empresa |
| `CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA` | Gate check: ¿el doc tiene contabilización automática? |
| `AYUDA` | Mapeo CONSECUTIVO → OBJETO (nombre input VFP) para pvar dinámico |
| `GRUPOS` | Cuentas inv/cos por grupo de producto |
| `PRODUCTOS` | Grupo de cada producto |
| `TIPO_DOC` | Tipos de doc — ESTADO_INVE=3 = documentos de venta |

### Técnica clave — escritura binaria a TERCEROS.dbf
TERCEROS tiene .fpt huérfano → librería `dbf` no puede abrir en READ_WRITE.
Solución: `_crear_tercero_bin()` en `configurar_allegra.py` escribe directamente:
1. Lee estructura header + campos con `struct`
2. Calcula MAX(COD_TER) leyendo todos los registros en binario
3. Construye registro de 739 bytes con campos N/C/T/L
4. Append al final del archivo + actualiza contador en header (bytes 4-7)
5. Campo T (datetime VFP): Julian Day = `ordinal + 1721425`, ms = segundos × 1000

### Técnica clave — AYUDA como puente pvar dinámico
`CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR.DOCUMENTO_` (entero) → `AYUDA.CONSECUTIVO` → `AYUDA.OBJETO` (nombre del input VFP en facturar_cancelar.scx).  
Así `_contabilizar()` no hardcodea qué input va en qué pvar — lo resuelve dinámicamente igual que VFP.

### Técnica clave — filtro tipos de documento de venta
`facturar_cancelar.scx` usa: `TIPO_DOC WHERE ESTADO_INV = 3 AND CODIGO IN (CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR WHERE EMPRESA = empresa)`.  
`_tipos_doc_automaticos(empresa)` replica este doble filtro: `TIPO_DOC.ESTADO_INV=3` (campo truncado a 10 chars — NO `ESTADO_INVE`) AND en `CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA` para la empresa.  
Retorna `(display_list, cod_map)`: `display_list` = `["013 — FACTURA VENTA POS", ...]`, `cod_map` = `{"013 — FACTURA VENTA POS": "013", ...}`.  
Resultado real BD Pilar — empresa 02: `012, 013, 015, 022, 030` | empresa LP: `011, 012, 013, 014, 016, 018, 023, 029, 908`.

### Revertir fases — flujo completo
```
Usuario selecciona fila en grilla "Procesadas"
→ clic "Revertir fases seleccionada"
→ _revertir_ui(): busca factura_id en allegra_pendientes por num_doc+empresa
→ _DialogRevertirFases: checkboxes f_prod1 / f_standar / f_costos / f_contab
→ _revertir_fases_dbf(carpeta, factura_id, empresa, fases_sel):
    - resetea campos fase a False
    - procesado = False
    - motivo = ""
→ factura aparece en "Pendientes" → daemon la retoma próximo ciclo
→ Si f_prod1 revertido: aviso manual en Administrator para eliminar PROD_FACT1
```

### Detalles técnicos adicionales — sesión 2026-04-11

**Multi-pagos**: campo `pagos` JSON en allegra_pendientes.dbf C(200) — almacena todos los payments de Alegra. `_contabilizar()` usa el payment correcto para cuadrar asientos (tarjeta débito vs crédito separados).

**Bolsa plástica**: item en Alegra con `nombre` ⊃ keyword configurada. `val_iva = 0`, `precio` = valor del impuesto. `ln_bolsa = sum(precio × cantidad)`. `items_efectivos` excluye bolsa → `ventas = subtotal` (sin restar). Cuenta en Administrator: 240807.

**NITs auto-creados**: toggle `auto_nit` (Canvas píldora) — si ON, crea tercero en TERCEROS.dbf automáticamente y marca como 'creado' en alegra_nits_pend. Escritura binaria (`.fpt` huérfano — ver técnica clave).

**Equivalencia vendedores**: sección en tab Configuracion — seller_id Alegra → vendedor Administrator. Guardado en `alegra_vendedores.dbf`. Internamente usa tabla MESEROS.dbf pero la UI nunca dice "mesero".

**Reinicio seguro**: diálogo post-reinicio sugiere `MIN(borrado)-1` por empresa como nuevo num_inicio. Bloquea Reanudar/Un ciclo hasta confirmar. Diálogo con `attributes("-topmost", True)` + `lift()` + `focus_force()` para que aparezca sobre otras ventanas.

**_programar_refresh()**: en modo automático (Reanudar), llama `_refresh()` + `_refrescar_facturas()` + `_refrescar_terceros()` — las 3 juntas para que grillas se actualicen en tiempo real.

---

### Despliegue en PC Pilar — sesión 2026-04-14 ~3pm

Checklist completo en: `docs/checklist_despliegue_pilar.md`

**Requisitos verificar remotamente:**
- Python + paquetes `dbf` y `requests`
- `C:\S.A.R\` con scripts y `AlegraDaemon.exe` v2.8
- `C:\S.A.R\RutaBaseDatos\ruta.dbf` apuntando a BD Pilar
- `C:\S.A.R\bd_esperada.txt` con ruta correcta
- `AlegraDaemon.exe` en `shell:startup`
- `allegra_config.dbf` y `alegra_tiposdoc.dbf` en carpeta BD

**Procedimiento (8 pasos en checklist):**
1. Verificar requisitos
2. Copiar archivos actualizados
3. `instalar_allegra_bd.py` si faltan tablas
4. Configurar tip_doc, met_pago, num_inicio, vendedores por empresa
5. Prueba con "Un ciclo" manual
6. Verificar en Administrator (inventario + contabilidad)
7. Activar modo automático
8. Confirmar que Pilar sabe operar

### Pendientes — próximas sesiones
- **CDX APPEND fix** — solución sin VFP IDE en cliente (registros no aparecen en filtros WHERE FECHAHORA)
- **Auditar bolsa** — verificar cuenta 240807 cuadrada con fix ln_bolsa (precio×cantidad)
- **Auditar vendedores** — verificar VENDEDOR ≠ 0 en PROD_FACT1
- **Progreso sync en tiempo real** — mostrar facturas descargándose en grilla Pendientes

---

---

## 1. Contexto del cliente: Pilar Peralta

### Situación actual
- Pilar Peralta usa **dos sistemas en paralelo**:
  1. **Allegra** — software comercial de facturación. Paga **$90.000/mes**. Límite: hasta $40 millones en facturas/mes. Si supera ese monto, cobran adicional según escalas.
  2. **Administrator** — aplicativo VFP de SAR (Rafael). Cubre: inventarios, compras, contabilidad integrada.

- **En los equipos del cliente NO está instalado VFP** — solo los ejecutables compilados de Administrator.
- El Command window de VFP no está disponible ni en modo ejecución ni en el ejecutable compilado.
- Rafael escribe código y guarda el archivo → los cambios quedan sin necesidad de compilar (en desarrollo). Para producción hay que compilar y generar el `.exe`.

### Rutas clave
| Recurso | Ruta |
|---|---|
| BD cliente (VFP) | `C:\D\Pilar Peralta\basedatosempresas\` |
| Archivo `prod_fact1.dbf` | Existe en la ruta anterior — **propósito desconocido**. Fue etiquetado incorrectamente como "tabla de facturas Allegra" en una sesión anterior sin base real. No asumir nada hasta verificar. |
| Proyecto VFP | `C:\S.A.R\PROYECTO\` |
| Scripts de trabajo Python | `C:\S.A.R\` |

---

## 2. Trabajo realizado — Columna NIT en grilla de movimientos contables

### Objetivo
Agregar columna **NIT/CÉDULA** al formulario `contabilidad_movimiento_cuentas_terceros.scx` que muestra los movimientos contables por tercero. El NIT debe obtenerse cruzando con la tabla `CR_TERCEROS` usando el código del tercero activo en el formulario (`THISFORM.TXT_CODIGO_TERCERO.VALUE`).

### Técnica usada
Los archivos `.scx` / `.SCT` son binarios — no se pueden editar como texto. Se desarrollaron scripts Python que modifican el binario directamente:
- **`.scx`** = DBF que describe la estructura del formulario y sus controles
- **`.SCT`** = FPT (memo file) que almacena el código de los métodos (`METHODS`)

Los scripts leen el METHODS del registro FORM, inyectan o modifican procedimientos, y reescriben el bloque en el SCT.

### Scripts desarrollados (en `C:\S.A.R\`)

| Script | Qué hace |
|---|---|
| `restaurar_agregar_nit.py` | Restaura desde backup `_bak5` e inyecta `PROCEDURE agregar_nit` (v1) |
| `restaurar_agregar_nit_v2.py` | Igual pero con query SQL corregida con `;` continuador de línea |
| `preparar_nit.py` | Prepara el archivo `agregar_nit.txt` para ejecutar vía `.prg` en VFP |
| `PROYECTO/agregar_nit_txt.prg` | PRG que se lanza desde VFP Command: `DO C:\S.A.R\PROYECTO\agregar_nit_txt.prg` |
| `fix_agregar_nit_final.py` | Limpia el bloque DIAG (MESSAGEBOX de depuración) y corrige COLUMNORDER |
| `fix_agregar_nit_join.py` | Intento alternativo con JOIN en la query |
| `leer_*.py` / `ver_*.py` / `debug_*.py` | Herramientas de inspección y diagnóstico del SCX/SCT |

### Lógica del PROCEDURE agregar_nit (última versión estable — v2)
```foxpro
PROCEDURE agregar_nit
LPARAMETERS lcCursor
LOCAL lcNit
lcNit = ''
SELECT CR_TERCEROS
GO TOP
SCAN
    IF CR_TERCEROS.COD_TER = THISFORM.TXT_CODIGO_TERCERO.VALUE
        lcNit = ALLTRIM(CR_TERCEROS.IDENTIFICACION)
        EXIT
    ENDIF
ENDSCAN
SELECT *, SPACE(30) AS NIT;
FROM &lcCursor;
INTO CURSOR &lcCursor READWRITE
SELECT &lcCursor
REPLACE ALL NIT WITH lcNit
IF THISFORM.GRID1.COLUMNCOUNT = 10
    THISFORM.GRID1.COLUMNCOUNT = 11
    THISFORM.GRID1.COLUMN11.COLUMNORDER = 6
    THISFORM.GRID1.COLUMN11.WIDTH = 120
    THISFORM.GRID1.COLUMN11.HEADER1.CAPTION = 'NIT/CEDULA'
    THISFORM.GRID1.COLUMN11.CONTROLSOURCE = 'NIT'
ENDIF
ENDPROC
```

### Historial de problemas y resoluciones

| # | Problema | Estado |
|---|---|---|
| 1 | `SELECT *, SPACE(30) AS NIT FROM &lcCursor` — "Falta una cláusula necesaria" | ✅ Resuelto con continuador `;` en cada línea |
| 2 | Columna NIT (posición 11) movida a posición 6 — se achicaba después de ejecutar la consulta | ⚠️ Pendiente confirmar si quedó estable con WIDTH=120 |
| 3 | COLUMNORDER = 11 en vez de 6 | ✅ Corregido en `fix_agregar_nit_final.py` |
| 4 | Bloque DIAG con MESSAGEBOX quedó en producción | ✅ Eliminado en `fix_agregar_nit_final.py` |
| 5 | 14 errores de `.bmp` al abrir el proyecto en VFP | ℹ️ Imágenes faltantes — no bloqueante. Se creó `crear_bmps2.ps1` y `crear_imagenes_vfp.bat` |
| 6 | SEEK con TERCERO / TER_COD no encontraba el NIT | ✅ Reemplazado con SCAN/IF/EXIT |

### Estado actual (2026-03-21)
- **Backup limpio**: `_bak5` — es el punto de restauración sin ninguna modificación NIT
- **Última versión activa**: `restaurar_agregar_nit_v2.py` + `fix_agregar_nit_final.py`
- **Pendiente**: verificar que la columna NIT queda en posición 6 y ancho estable. Si el ancho sigue achicándose, puede ser un problema de `DynamicWidth` en el grid o de que el cursor reconstruido pierde el schema visual.

---

## 3. Interfaz Allegra ↔ Administrator — ESQUELETO COMPLETO (2026-03-21)

### Objetivo
Conectar los datos de facturación de Allegra (que Pilar usa para facturar) con los dos formularios clave de Administrator, para que los registros queden integrados en inventarios, costos y contabilidad automáticamente.

### Los formularios involucrados

| Formulario | Ruta | Función | Rol en interfaz |
|---|---|---|---|
| `facturar_basica.scx` / `.SCT` | `C:\S.A.R\PROYECTO\` | Captura datos del cliente y productos — entrada de la factura | Contexto/referencia — no es el foco |
| `facturar_cancelar.scx` / `.SCT` | `C:\S.A.R\PROYECTO\` | Finaliza todos los registros: costos, inventarios, contabilidad | **EL formulario clave para la interfaz** |
| `facturar_cancelar_1.scx` | `C:\S.A.R\PROYECTO\` | Backup desactualizado | Ignorar |

### Análisis de `facturar_basica.scx`
Formulario de **captura de ítems**. El vendedor busca cliente y productos, los agrega a `PROD_FACT` (tabla temporal). Al terminar llama a `facturar_cancelar` vía `DO FORM`.

**Tablas principales**: `PRODUCTOS`, `PRODUCTOS_VENTA`, `REG_PROD_SALDOS`, `TERCEROS`, `PROD_FACT`, `EMPRESAS`

**Cursor central**: `cr_prod_fact_multiusuario` (en memoria) → persiste en `PROD_FACT`

**Variables globales clave**:
- `VAR_CODIGO_EMPRESA_USUARIO` — empresa del usuario
- `VAR_CODIGO_TERCERO_CONSULTAS` — código del cliente seleccionado
- `VAR_CODIGO_TERCERO_VENDEDOR` — código del vendedor

**Flujo**: seleccionar cliente → buscar productos → capturar ítems → `Btn_cancelar` → DO FORM `facturar_cancelar.SCX`

---

### Análisis detallado de `facturar_cancelar.scx` ← FOCO DE LA INTERFAZ ALLEGRA

**Propósito**: Cierre y cobro de la factura. Recibe los ítems de `PROD_FACT`, calcula totales con descuentos/IVA/retenciones, selecciona tipo de documento, registra en `PROD_FACT1`, contabiliza, imprime y cierra.

#### Controles clave (los que interesan para la interfaz)
| Control | Tipo | Función |
|---|---|---|
| `txt_recibido` | textbox | **Valor recibido — Enter aquí dispara todo el proceso de cierre** |
| `CMBTIPOVENTA` | combobox | Selector tipo de documento (factura, ticket, etc.) |
| `txt_numero_factura` | textbox | Número de factura (consecutivo) |
| `txt_cedula_o_nit` | textbox | NIT/cédula del cliente |
| `txt_nombre_tercero` | textbox | Nombre del cliente |
| `txt_total` | textbox | Total a cobrar |
| `txt_descuento` | textbox | Monto descuento |
| `txt_por_dto` | textbox | % descuento |
| `txt_iva` | textbox | IVA total |
| `txt_subtotal` | textbox | Subtotal sin IVA |
| `txt_valor_rtefte` | textbox | Valor retención en la fuente |
| `txt_valor_rteiva` | textbox | Valor retención IVA |
| `txt_tarjeta_recibido` | textbox | Valor recibido por tarjeta |
| `txt_consigna_trasfiere` | textbox | Valor por consignación/transferencia |
| `txt_abona_efectivo` | textbox | Abono en efectivo |
| `txt_orden_compra` | textbox | Número orden de compra |
| `edt_desc_factura` | editbox | Descripción/notas de la factura |

#### Flujo de cierre (cadena que dispara Enter en txt_recibido)
```
1. REGISTRA_PROD_FACT1
   - Lee ítems de PROD_FACT para el cliente
   - Llama STANDAR (movimiento de inventario)
   - INSERT INTO PROD_FACT1 (registro definitivo de ventas)
   - INSERT INTO reg_ctas_notas_documentos

2. CONTABILIZAR
   - Genera asientos contables (GENERAR_VARIABLES)
   - Cruza con tabla AYUDA
   - Maneja saldos y abonos en REG_CTAS

3. IMPRIMIR_FACTURA
   - REPORT FORM según configuración de empresa

4. Limpieza
   - DELETE ALL en PROD_FACT (limpia ítems temporales)
   - UPDATE CONSECUTIVOS (incrementa número de factura)
   - Cierra y regresa a facturar_basica
```

#### Tablas físicas que toca `facturar_cancelar`
| Tabla | Operación | Descripción |
|---|---|---|
| `PROD_FACT` | SELECT + DELETE ALL | Origen ítems → limpia al cerrar |
| `PROD_FACT1` | INSERT | **Registro DEFINITIVO de ventas** |
| `CONSECUTIVOS` | SELECT + UPDATE | Consecutivo de factura |
| `REG_CTAS` | APPEND BLANK + REPLACE | **Asientos contables — tabla principal de contabilidad** |
| `SAL_DOC` | APPEND BLANK + REPLACE | Saldos por documento (usado en contabilización de comisión vendedor) |
| `reg_ctas_notas_documentos` | INSERT | Notas asociadas al documento contable |
| `reg_costos_temporal` | APPEND BLANK + REPLACE + DELETE ALL | **Tabla de paso de costos** (física en disco, se vacía al cerrar) |
| `REG_PROD` | Abierta en Init / cerrada en Unload | **Movimientos de inventario** — este formulario la abre pero NO escribe directamente; la escribe `costo_ventas_contabiliza.prg` |
| `TIPO_DOC` | SELECT | Tipos de documento disponibles |
| `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR` | SELECT | Config. contable |
| `EMPRESA_CONFIGURAR` | SELECT | Config. por empresa/máquina |
| `TERCEROS` | SELECT | Datos del cliente |
| `TELEFONOS` | SELECT | Teléfono del cliente |
| `VENTAS_VENDEDOR` | SELECT | Comisiones |
| `FACTURAR_CONFIGURAR` | SELECT + UPDATE + INSERT | Config. ticket/impresión |
| `facturas_entregas` | INSERT | Despachos |
| `FACTURAR_PERSONAS_FACTURA` | INSERT | Propina/personas (restaurante) |
| `productos_reservas` | SELECT + REPLACE | Liberar reservas |

---

#### Análisis profundo de tablas por módulo — extraído del SCT (2026-03-21)

> ✅ = confirmado directamente en el código del SCT
> 🔍 = suposición de análisis — posibilidad razonable, no confirmada desde este formulario

---

##### INVENTARIO

**Tabla `PROD_FACT1`** ✅
- `INSERT INTO PROD_FACT1` con campos: `consecutivo, cod_pro, cantidad, precio, cod_fac, descuento, usuario, empresa, fechahora, por_iva, sector, vendedor, cliente, tip_fac, conse_reg_pro, conse_origen, costo, comision`
- Es el **registro definitivo** de cada ítem vendido. Se escribe en `REGISTRA_PROD_FACT1`.

**Tabla `PROD_FACT`** ✅
- Solo se lee (SELECT) y al final se vacía: `DELETE ALL` — limpia los ítems temporales del cliente o sector al cerrar la factura.

**Procedimiento `STANDAR`** ✅ (PRG externo)
- Llamado así desde `registra_prod_fact1`:
  ```foxpro
  DO STANDAR WITH LCTIP_FAC, LNUMERO, LLAPSO, LNCANTIDAD, UPPER(ALLTRIM(LCPRODUCTO)), LNCOSTO
  ```
- Devuelve `LNCONSE` (consecutivo del registro creado) y `vncosto` (costo calculado).
- **El formulario NO sabe qué tablas escribe STANDAR** — eso está en `standar.prg`.
- 🔍 **Suposición**: `STANDAR` probablemente actualiza saldos de stock (tabla como `REG_PROD_SALDOS` o similar), pero no está confirmado desde aquí.

**Tabla `REG_PROD`** ✅ (apertura confirmada) / 🔍 (escritura no confirmada desde aquí)
- `PROC_ABRIR_TABLA("REG_PROD")` en el Init del formulario — se abre al cargar.
- Cerrada con `USE` en el Unload.
- Este formulario NO tiene INSERT/APPEND/REPLACE sobre `REG_PROD` en su código.
- 🔍 **Suposición**: `costo_ventas_contabiliza.prg` (PRG externo llamado desde este formulario) la escribe con el movimiento de inventario — pero esto no se confirmó leyendo ese PRG.

---

##### CONTABILIDAD

**Tabla `REG_CTAS`** ✅ — tabla principal de asientos contables

Dos rutas de escritura confirmadas:

**Ruta A — venta (automática)**:
```foxpro
INSERTAR_REG_CTAS_AUTOMATICO(LDLAPSO, LCTIPODOC, LCNUMTER, LNNUMDOC)
```
Función externa en `busquedad_registros.prg`. El comentario en el código dice explícitamente: `** LLAMA AL PROCEDIMIENTO QUE INSERTA LA INFORMACION EN LA TABLA REG_CTAS`.

**Ruta B — comisión del vendedor (directa)**:
```foxpro
APPEND BLANK
REPLACE TIP_DOC, NUM_DOC, COD_CUE ("613502"), NAT_CUE ("D"), FEC_DOC, EMP, ...
APPEND BLANK
REPLACE TIP_DOC, NUM_DOC, COD_CUE ("233520"), NAT_CUE ("C"), FEC_DOC, EMP, ...
```
- Débito: cuenta `613502` (gasto de comisión de ventas)
- Crédito: cuenta `233520` (comisión por pagar al vendedor)

**Tabla `SAL_DOC`** ✅ — saldos por documento
```foxpro
PROC_ABRIR_TABLA("SAL_DOC")
APPEND BLANK
REPLACE TIP_DOC, NUM_DOC, COD_CUE ("233520"), COD_TER, NAT_CUE ("C"), FEC_DOC, EMP, FEC_HOR, USU, VALOR
```
Escrita en el mismo procedimiento de comisión vendedor.

**Tabla `reg_ctas_notas_documentos`** ✅
```foxpro
INSERT INTO reg_ctas_notas_documentos (tipo, numero, empresa, tercero, nota, ...)
```
Notas asociadas a cada documento contable.

---

##### COSTOS

**Tabla `reg_costos_temporal`** ✅ — tabla de paso física (confirmada como física, no cursor)

Flujo completo confirmado:
1. `PROC_ABRIR_TABLA("reg_costos_temporal")` — se abre como tabla física en disco
2. `DELETE ALL` — se limpia antes de usar (asegura que esté vacía para esta factura)
3. Por cada producto: `APPEND blank` + `REPLACE cod_pro, cantidad, cod_fac, usuario, empresa, tipo_doc, tercero, costo`
4. `DO costo_ventas_contabiliza` — PRG externo que lee esta tabla y genera los asientos de costo
5. Al cerrar el formulario: si `VAR_SALIR_COMPLETO_COSTOS = 1` → `DELETE ALL` (vacía para próxima factura)

🔍 **Suposición**: `costo_ventas_contabiliza.prg` probablemente escribe en `REG_CTAS` (asientos de costo de ventas) y en `REG_PROD` (movimiento de inventario) — pero no se confirmó leyendo ese PRG.

---

##### PRGs EXTERNOS — LEÍDOS Y ANALIZADOS (2026-03-21)

---

###### `standar.prg` ✅

Parámetros de entrada: `PTIPO, PNUMERO, PLAPSO, CANT_ENTRADA, LCCODPRO, LNCOSTO, LNVALOR_IVA`

Modo controlado por `LNESTADOINVEN` (viene de `TIPO_DOC.TIPO_INVE`):

**Modo 3 — Producción** (entrada de producto terminado + salida de materias primas):
- Lee la receta/composición del producto desde `TRANS_MAT` y `TRANS_MAT_UNO`
- Por cada materia prima: `INSERT INTO REG_PROD` (salida) + `UPDATE REG_PROD_SALDOS`
- Para el producto terminado: `INSERT INTO REG_PROD` (entrada) + `UPDATE REG_PROD_SALDOS`

**Modo 1 — Entrada con costo** (compras a proveedores, devoluciones de clientes):
- `INSERT INTO REG_PROD` con campos: `VAL_ENT, CONSECUTIVO, TIP_DOC, NUM_DOC, LAP, CAN_ENT, COS_ENT, COD_PRO, FEC, USU, TER_COM, EMP, ENT_BOD, SAL_EXI, VAL_EXI_CON, COS_UND_CON, COD_ORI, CONCEPTO`
- `UPDATE REG_PROD_SALDOS` (o INSERT si no existe): actualiza saldo existencias y costo unitario promedio
- También puede actualizar `CUAL_PROD_TERC` (precio de compra por producto-proveedor)

**Tablas escritas por `standar.prg`** ✅:
| Tabla | Operación | Descripción |
|---|---|---|
| `REG_PROD` | INSERT INTO | **Movimiento de inventario** — cada línea = un movimiento (entrada o salida) |
| `REG_PROD_SALDOS` | UPDATE + INSERT | **Saldo por producto/bodega** — existencias actuales + costo unitario ponderado |
| `CUAL_PROD_TERC` | UPDATE + INSERT | Precio de compra por producto y proveedor (solo en modo compra) |

**Tablas solo leídas por `standar.prg`**:
- `TIPO_DOC` — para determinar el modo (`TIPO_INVE`)
- `REG_PROD_SALDOS` — para calcular nuevo costo unitario promedio
- `TRANS_MAT` / `TRANS_MAT_UNO` — receta/composición del producto (modo producción)
- `TRANS_MAT_TEMP` — receta temporal (cotizaciones)

---

###### `costo_ventas_contabiliza.prg` ✅

Condición: solo ejecuta si `VAR_EMPRESA_COSTEA = 1`.

Lee `reg_costos_temporal` (tabla de paso llenada por `facturar_cancelar`) y por cada producto:
1. Busca en `PRODUCTOS` el grupo del producto
2. Busca en `GRUPOS` las cuentas contables: `cuenta_inve` (inventario) y `cuenta_cos` (costo de ventas)
3. Obtiene consecutivo de `REGCTA_CONSE`
4. Escribe **DOS asientos en `REG_CTAS`**:
   - Asiento 1 (crédito inventario): `cuenta = cuenta_inve`, `tot_cre = costo`, `tot_deb = 0`
   - Asiento 2 (débito costo de ventas): `cuenta = cuenta_cos`, `tot_deb = costo`, `tot_cre = 0`

**Tablas escritas por `costo_ventas_contabiliza.prg`** ✅:
| Tabla | Operación |
|---|---|
| `REG_CTAS` | APPEND BLANK + REPLACE (2 registros por producto) |
| `REGCTA_CONSE` | REPLACE (actualiza consecutivo) |

**Tablas solo leídas**: `reg_costos_temporal`, `PRODUCTOS`, `GRUPOS`

---

###### `busquedad_registros.prg` → `INSERTAR_REG_CTAS_AUTOMATICO` ✅

Parámetros: `LDPARAMDLAPSO, LCPARAMTIPODOC, LCPARAMNUMTER, LNPARAMNUMDOC`

Lee el cursor `TMP_REG_CTAS_FINAL` (pre-construido por la lógica de `CONTABILIZAR`) y por cada fila:
1. Obtiene consecutivo de `REGCTA_CONSE`
2. Si la cuenta tiene `DOC_CRUZE = 1`: llama `PROC_SAL_DOC` → escribe en `SAL_DOC`
3. `APPEND BLANK` + REPLACE en `REG_CTAS` con: `LAPSO, FECHAHORA, TIPO, CONSECUTIVO, CUENTA, TERCERO, TER_COD, DOCUMENTO, EMPRESA, USUARIO, BODEGA, TOT_DEB, TOT_CRE, TIP_DOC_CRU, NUM_DOC_CRU`
4. Actualiza `REG_CTAS_SALDOS` (saldo acumulado por cuenta): si existe → `REPLACE SALDO WITH SALDO + delta`; si no → INSERT

**Tablas escritas** ✅:
| Tabla | Operación |
|---|---|
| `REG_CTAS` | APPEND BLANK + REPLACE |
| `REG_CTAS_SALDOS` | UPDATE SALDO + INSERT si no existe |
| `SAL_DOC` | vía `PROC_SAL_DOC` (cuentas con documento cruce) |
| `REGCTA_CONSE` | REPLACE (consecutivo) |

---

##### MAPA COMPLETO DE TABLAS — CICLO DE VENTA (2026-03-21)

```
PROD_FACT (staging ítems)
  ↓ facturar_cancelar: SELECT → CRPRODFACTURARC_AUX
  ↓
  ├── INSERT INTO PROD_FACT1                    (registro definitivo ventas)
  │
  ├── DO STANDAR (por cada ítem)
  │     ├── INSERT INTO REG_PROD               (movimiento inventario)
  │     └── UPDATE/INSERT REG_PROD_SALDOS      (saldo existencias)
  │
  ├── APPEND/REPLACE reg_costos_temporal       (tabla de paso costos)
  │     ↓ DO costo_ventas_contabiliza
  │         └── APPEND REG_CTAS × 2           (crédito inventario + débito costo ventas)
  │
  ├── INSERTAR_REG_CTAS_AUTOMATICO             (contabilidad de la venta)
  │     ├── APPEND REG_CTAS                   (por cada línea contable configurada)
  │     ├── UPDATE/INSERT REG_CTAS_SALDOS     (saldo acumulado por cuenta)
  │     └── PROC_SAL_DOC → SAL_DOC            (cuentas con documento cruce)
  │
  └── DELETE ALL PROD_FACT                     (limpia staging)
```

**Tabla auxiliar de consecutivos**: `REGCTA_CONSE` — contador global de asientos contables.

#### Queries SQL clave
```sql
-- Ítems de la factura para registrar en PROD_FACT1
SELECT A.CONSECUTIVO, A.COD_PRO, ALLTRIM(STR(A.COD_FAC)) AS COD_FAC, A.CANTIDAD, A.PRECIO,
  A.DESCUENTO, A.USUARIO, A.EMPRESA, A.FECHAHORA, A.POR_IVA, A.VAL_IVA, A.VAL_CON_IVA,
  A.VENDEDOR, A.FECHA_HORA_FINAL, A.CLIENTE, A.SECTOR, A.CONSEALQ, A.CONREGPRO,
  VAL_CON_IVA, A.SEC_ORI, A.COMISION
FROM PROD_FACT A, PRODUCTOS
WHERE ALLTRIM(COD_PRO) == ALLTRIM(CODIGO)
  AND CLIENTE = VAR_CODIGO_TERCERO_CONSULTAS
  AND ALLTRIM(A.EMPRESA) == ALLTRIM(VAR_CODIGO_EMPRESA_USUARIO)
ORDER BY FECHAHORA DESC
INTO CURSOR CRPRODFACTURARC_AUX READWRITE

-- Totales de la factura
SELECT SUM((((PRECIO*CANTIDAD)-DESCUENTO)+(VAL_IVA*CANTIDAD))) AS SUBTOTAL
FROM PROD_FACT WHERE CLIENTE = VAR_CODIGO_TERCERO_CONSULTAS
  AND ALLTRIM(EMPRESA) == ALLTRIM(VAR_CODIGO_EMPRESA_USUARIO)
GROUP BY CONSECUTIVO INTO CURSOR CR_FAC_TOTAL_AUX READWRITE

-- Tipos de documento permitidos (cruzando configuración contable)
SELECT NOMBRE, CODIGO, TIPO_INVE FROM TIPO_DOC
WHERE ESTADO_INVE = 3
  AND ALLTRIM(CODIGO) IN (SELECT ALLTRIM(DOCUMENTO)
    FROM CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR
    WHERE ALLTRIM(EMPRESA) == ALLTRIM(VAR_CODIGO_EMPRESA_USUARIO))
INTO CURSOR CRTIPOVENTA READWRITE
```

#### Variables globales clave en `facturar_cancelar`
- `VAR_TIPO_DOCUMENTO` / `VAR_TIPO_DOC` — código del documento (FV, TK, etc.)
- `VAR_TIPO_INVE` — controla si se mueve inventario (0=no mover)
- `VAR_CODIGO_BODEGA_ACTUAL` — bodega activa
- `PVNOMBRE_MAQUINA` — nombre del equipo (para config. por máquina)
- `VAR_FACTURA_ENVIO_EMAIL_CLIENTE` — flag de envío por email

---

### Fuente de datos: Alegra (antes escrito "Allegra")
- **Alegra** es el software SaaS de facturación que usa Pilar (alegra.com). Paga $90.000/mes.
- **API:** `https://api.alegra.com/api/v1/` — Auth HTTP Basic `base64(email:token)`
- **Token ubicación en Alegra:** app.alegra.com → Configuración → Integración manual → API

#### Dos empresas de Pilar — credenciales completas (2026-03-28)

| Empresa | Propietario | Email | Contraseña | Token API | Código Admin |
|---|---|---|---|---|---|
| ELECTRONICAS J&P | Jose Luis Chaparro Ninco | electronicajyp@hotmail.com | nataJUAN*0525 | aabde447e95a29efb773 | LP |
| ELECTRONICAS TV & VIDEO | Maria del Pilar Peralta Mosquera | electronicastvyvideo@hotmail.com | NATAJUAn-0525 | ade8e319ce85985fb47c | 02 |

- Token location en Alegra: `app.alegra.com → Configuración → Integración manual → API`
- Tokens extraídos automáticamente con Selenium (2026-03-28) — no se los pedimos a Pilar

#### Estructura API real (campos confirmados)
- `invoices` endpoint: `GET /invoices?limit=30&date-start=YYYY-MM-DD` (máximo 30 por llamada)
- Factura: `id`, `date`, `client.identification` (NIT), `numberTemplate.fullNumber` (num), `numberTemplate.documentType` (tipo Alegra), `payments[].paymentMethod`, `payments[].amount`
- Ítem: `reference` (= cod_pro Administrator), `name` (contiene código al inicio cuando reference=None), `quantity`, `price` (sin IVA), `tax[0].percentage`, `tax[0].amount`, `discount`
- Costo: NO disponible en Alegra — se deja en 0 en el DBF
- Métodos de pago confirmados: `cash`, `transfer` (y presumiblemente `credit-card`/`debit-card`)

#### Hallazgos importantes (2026-03-28 / 2026-03-31)
- **La bolsa** (`0. impuesto al consumo bolsa plastica`, precio $73): referencia vacía en Alegra, nombre siempre contiene "bolsa". En Administrator NO es producto — es impuesto separado (`TXT_BOLSA_IMPUESTO`). Se detecta por `'BOLSA' $ UPPER(nombre)`, se acumula en `LN_BOLSA` y se contabiliza vía el slot `TXT_BOLSA_IMPUESTO` en `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR`, NO va a PROD_FACT ni inventario.
- **Códigos en el nombre**: cuando `reference=None`, el código está al inicio del campo `name` antes de `...` o `…`. Función `_extraer_cod_pro()` lo resuelve. Algunos ítems S/REF reales (como la bolsa) no tienen código — se detectan por nombre.
- **Tipos de documento**: 120 facturas recientes revisadas = todas `saleTicket`. Mapeo en `alegra_tiposdoc.dbf` (configurable).
- **AYUDA table**: el campo `OBJETO` contiene el nombre del control VFP asociado a cada slot contable. `DOCUMENTO_` en `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR` referencia `AYUDA.CONSECUTIV`.

#### Mapeo OBJETO → concepto (documento '013', empresa '02') — confirmado 2026-03-31
| VAR_CON_PR | OBJETO | Cuenta | Concepto |
|---|---|---|---|
| 1 | TXT_SUBTOTAL | 413548 C | Subtotal sin IVA |
| 2 | TXT_IVA_DEFINITIVO | 240801 C | IVA por pagar |
| 3 | TXT_DESCUENTO_DEFINITIVO | 530535 D | Descuento |
| 4 | TXT_BOLSA_IMPUESTO | 240807 C | Impuesto bolsa plástica |
| 5 | TXT_TARJETA_RECIBIDO | 11100503 D | Recaudo tarjeta |
| 6 | TXT_ABONA_EFECTIVO | 110505 D | Recaudo efectivo |
| 7 | TXT_COBRAR_CLIENTE | 130505 D CRUZE=1 | Cartera/CxC saldo pendiente |
| 8 | TXT_CONSIGNA_TRASFIERE | 111002 D | Recaudo transferencia |

> **Principio**: los slots se asignan dinámicamente — `interfaz_allegra.prg` lee `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR` + `AYUDA` y usa macro-sustitución. Ningún número de cuenta ni slot está hardcodeado en el PRG.

#### allegra_sync.py — OPERATIVO y probado
`C:\S.A.R\allegra_sync.py` — v3 2026-03-31:
- Ruta BD dinámica desde `ruta.dbf` — igual que el ejecutable. Sin MODO_TEST. Antes de pruebas: backup de `basedatosempresas`.
- Autentica en las dos empresas, trae facturas, extrae código del nombre cuando `reference=None`
- **Nuevos campos en `allegra_pendientes.dbf`**: `nombre C(60)` (nombre ítem), `met_pago C(20)` ⚠️ (no `metodo_pago` — confirmado 2026-04-02), `val_pago N(12,2)` (total pagado en la factura)
- Probado: 224 registros correctos, 0 S/REF, empresas LP y 02 correctas

#### alegra_tiposdoc.dbf — NUEVA (2026-03-31)
`C:\D\Pilar Peralta\basedatosempresas\alegra_tiposdoc.dbf`
- Campos: `tip_alegra C(20)`, `tip_admin C(10)`, `empresa C(5)` (**máx 10 chars en DBF VFP**)
- Mapea tipo de documento Alegra (`saleTicket`, `invoice`, `creditNote`) al código en Administrator (`013`, `FV`, `NC`, etc.)
- `interfaz_allegra.prg` la lee en PASO 3B para resolver `PLNTIPODOC` — no hardcodeado
- Rows por defecto: `saleTicket→013` para empresas 02 y LP; `invoice` y `creditNote` vacíos (completar según cliente)
- Se crea con `instalar_allegra_bd.py` (PASO 4) o manualmente con Python dbf

---

### Arquitectura — COMPLETA Y CONECTADA (2026-03-21)

**Principio de diseño**: Todo vive dentro del mundo Administrator. Las dos tablas de estado (`allegra_config.dbf` y `allegra_pendientes.dbf`) están dentro de la BD de Pilar. El usuario nunca sale de Administrator para operar la interfaz.

**Decisión de diseño**: NO se usa `facturar_cancelar.scx` como intermediario. La interfaz llama directamente a los PRGs. Esto permite procesamiento automático sin abrir formularios visuales.

```
Administrator arranca
  └─ DO agregar_menu_allegra.prg         ← agrega pad "Allegra" al menú VFP

Usuario → Allegra → "Configurar / Sincronizar"
  └─ configurar_allegra.prg              ← formulario VFP (dentro de Administrator UI)
       ├─ Guardar  → allegra_config.dbf  (C:\D\Pilar Peralta\basedatosempresas\)
       └─ Sincronizar ahora
            ├─ SHELL: allegra_sync.py
            │    ├─ Lee  allegra_config.dbf (max_fact, desde_ult, ultima_sin)
            │    └─ Escribe allegra_pendientes.dbf (misma carpeta BD Pilar)
            └─ DO interfaz_allegra.prg
                 ├─ Lee  allegra_config.dbf → max_fact (límite de lote)
                 ├─ Lee  allegra_pendientes.dbf → facturas a procesar
                 ├─ Ciclo por factura (hasta max_fact):
                 │    ├─ Resolver NIT → TERCEROS.COD_TER (campo IDENTIFICACION vía DBC)
                 │    ├─ Llenar PROD_FACT con los ítems
                 │    ├─ DO STANDAR → REG_PROD + REG_PROD_SALDOS
                 │    ├─ INSERT PROD_FACT1
                 │    ├─ Llenar reg_costos_temporal
                 │    ├─ DO costo_ventas_contabiliza → REG_CTAS (costos)
                 │    ├─ DO contabilizar → REG_CTAS + REG_CTAS_SALDOS + SAL_DOC
                 │    ├─ INSERT reg_ctas_notas_documentos
                 │    ├─ REPLACE allegra_pendientes.procesado = .T.
                 │    └─ Limpiar PROD_FACT + reg_costos_temporal
                 └─ Actualiza allegra_config: ultima_sin + total_proc

Usuario → Allegra → "Ver pendientes"
  └─ ver_allegra_pendientes.prg          ← BROWSE de allegra_pendientes.dbf
```

---

### Archivos de la interfaz — ESTADO ACTUAL (2026-04-05)

#### Python (automatización + configuración)

| Archivo | Ruta | Estado |
|---|---|---|
| `allegra_sync.py` | `C:\S.A.R\` | ✅ OPERATIVO — motor de sync, fix `field_names` 2026-04-01 |
| `configurar_allegra.py` | `C:\S.A.R\` | ✅ **v2.2** — auto-restart daemon, auto-refresh log 30s, BD esperada, num_inicio inteligente |
| `alegra_daemon.py` | `C:\S.A.R\` | ✅ **v2.2** — escribe PID file, logs comprehensivos con config+timing, subprocess sync+interfaz |
| `interfaz_allegra.py` | `C:\S.A.R\` | ✅ NUEVO — fase 1 activa (PROD_FACT1 + nota + marcar). Invocado por daemon. |
| `instalar_cliente.ps1` | `C:\S.A.R\` | ✅ NUEVO — instala todo en PC cliente (Python, pip, archivos, acceso directo, startup) |
| `instalar_allegra_bd.py` | `C:\S.A.R\` | ✅ Simplificado — solo crea allegra_config.dbf y alegra_tiposdoc.dbf |
| `crear_form_allegra_v2.py` | `C:\S.A.R\` | ⛔ OBSOLETO — fue intento SCT, abandonado. Ignorar. |

#### VFP (procesamiento en Administrator)

| Archivo | Ruta | Estado |
|---|---|---|
| `interfaz_allegra.prg` | `C:\S.A.R\PROYECTO\` | ✅ — acepta parámetro empresa, bodega dinámica, multi-empresa |
| `alegra_timer.prg` | `C:\S.A.R\PROYECTO\` | ✅ — loop por ambas empresas desde allegra_config.dbf |
| `alegra_get_bd.prg` | `C:\S.A.R\PROYECTO\` | ✅ — `PUBLIC LC_ALEGRA_BD` desde `ruta.dbf` |
| `agregar_menu_allegra.prg` | `C:\S.A.R\PROYECTO\` | ✅ — agrega pad "Allegra" al menú + activa ON TIMER |
| `alegra_forzar_sync.prg` | `C:\S.A.R\PROYECTO\` | ✅ — sincronización manual desde menú |
| `ver_allegra_pendientes.prg` | `C:\S.A.R\PROYECTO\` | ✅ — BROWSE de pendientes |
| `configurar_allegra.prg` | `C:\S.A.R\PROYECTO\` | ⚠️ Actualizar para lanzar `configurar_allegra.py` en vez del SCX |
| `s.a.r.prg` | `C:\S.A.R\PROYECTO\` | ✅ Startup compilado en .exe — timer ya NO está aquí (está en fondo_menu_limpio.scx) |
| `fondo_menu_limpio.scx` | `C:\S.A.R\PROYECTO\` | ✅ Pantalla principal — contiene objeto `tmrAllegra` con Init + Timer event |

#### DBFs en BD Pilar

| Archivo | Estado |
|---|---|
| `allegra_config.dbf` | ✅ Estructura con `empresa`, 2 registros (02 y LP) |
| `allegra_pendientes.dbf` | ✅ Se crea al correr `allegra_sync.py` por primera vez |
| `alegra_tiposdoc.dbf` | ✅ `saleTicket→013` para empresas 02 y LP |

---

### Arquitectura de automatización — DEFINITIVA (2026-04-05)

**Capa Python reemplaza la capa VFP para el procesamiento automático.**
`alegra_timer.prg` desactivado (RETURN al inicio). `interfaz_allegra.py` hace todo.

```
AlegraDaemon v2.2  (shell:startup — AlegraDaemon.bat)
  └─ alegra_daemon.py — bucle cada N minutos
       ├─ al arrancar: escribe alegra_daemon.pid (PID + "2.2")
       ├─ correr_sync():
       │    ├─ header log: BD activa, BD esperada, estado BD, intervalo, proximo ciclo
       │    │              config empresas (num_inicio, max_fact, total_proc)
       │    ├─ _verificar_bd() → compara ruta.dbf vs bd_esperada.txt
       │    ├─ subprocess → allegra_sync.py   → allegra_pendientes.dbf
       │    ├─ subprocess → interfaz_allegra.py → PROD_FACT1, notas, marcado
       │    └─ guarda log completo en allegra_config.dbf (ultimo_log, hasta 8000 chars)
       └─ duerme N minutos, repite

configurar_allegra.py  (tkinter, acceso directo en escritorio)
  ├─ Al abrir: _asegurar_daemon()
  │    ├─ lee alegra_daemon.pid → (PID, version)
  │    ├─ si version != "2.2" o proceso muerto:
  │    │    ├─ matar viejo: taskkill PID + PowerShell WMI (pythonw/alegra_daemon) + AlegraDaemon.exe
  │    │    └─ iniciar nuevo: Popen pythonw alegra_daemon.py (DETACHED)
  │    └─ indicador "Daemon: Activo v2.2 (PID XXXX)" en el formulario
  ├─ Auto-crea allegra_config.dbf y alegra_tiposdoc.dbf si no existen
  ├─ Valida BD activa vs BD esperada (bd_esperada.txt)
  ├─ Sugiere/actualiza num_inicio desde PROD_FACT1 (filtrado por prefijo PTV/PJP)
  ├─ Log (ultimo_log) se refresca automaticamente cada 30 segundos
  └─ Botones: [Guardar] / [Sincronizar ahora] / [Cerrar]
```

**Formato del log comprehensivo (ultimo_log en allegra_config.dbf):**
```
=== CICLO 2026-04-05 12:00:01 (daemon v2.2) ===
BD activa:   C:\D\PILAR PERALTA\BASEDATOSEMPRESAS\DATOS_SAR.DBC
BD esperada: C:\D\PILAR PERALTA\BASEDATOSEMPRESAS\DATOS_SAR.DBC
Estado BD:   OK
Intervalo:   1 min  |  Proximo aprox: 12:01:01
Config 02:   num_inicio=PTV21200  max_fact=30  total_proc=45
Config LP:   num_inicio=PJP15780  max_fact=30  total_proc=38

=== allegra_sync ===  ...salida...
=== interfaz_allegra ===  ...salida...
=== FIN CICLO 12:00:15 ===
```

#### Bodegas confirmadas (BD Pilar)
| Empresa | COD_BOD | NOMBRE |
|---|---|---|
| 02 (TV & Video) | 2 | PRINCIPAL |
| LP (J&P) | 1 | PRINCIPAL |

`interfaz_allegra.prg` busca la bodega dinámicamente con SCAN sobre BODEGA WHERE COD_EMP_AS == empresa. Fallback hardcodeado: LP=1, 02=2.

#### interfaz_allegra.prg — firma
```foxpro
LPARAMETERS LC_EMP_PARAM   && "02" o "LP" — default "02" si no se pasa
```
`VAR_CODIGO_EMPRESA_USUARIO` se setea desde el parámetro. `VAR_CODIGO_BODEGA_ACTUAL` se busca en BODEGA.

#### Timer en fondo_menu_limpio.scx (2026-04-02 — arquitectura ACTUALIZADA)

⚠️ **El timer NO está en `s.a.r.prg` — está en `fondo_menu_limpio.scx`**, la pantalla principal de Administrator.

**Objeto:** `tmrAllegra`

**Init del form** — lee config y activa el timer:
```foxpro
DO C:\S.A.R\PROYECTO\alegra_get_bd.prg   && → PUBLIC LC_ALEGRA_BD
LOCAL lc_cfg, ln_seg
lc_cfg = LC_ALEGRA_BD + "allegra_config.dbf"
IF FILE(lc_cfg)
    USE (lc_cfg) IN 0 ALIAS _tmr_cfg SHARED
    SELECT _tmr_cfg
    GO TOP
    ln_seg = IIF(_tmr_cfg.intervalo > 0, _tmr_cfg.intervalo * 60000, 0)
    USE IN _tmr_cfg
    IF ln_seg > 0
        ThisForm.tmrAllegra.Interval = ln_seg
        ThisForm.tmrAllegra.Enabled  = .T.
    ELSE
        ThisForm.tmrAllegra.Enabled = .F.
    ENDIF
ELSE
    ThisForm.tmrAllegra.Enabled = .F.
ENDIF
```

**Timer event** (trazas activas — quitar antes de prod):
```foxpro
MESSAGEBOX("Timer Allegra va a disparar", 64, "Traza")   && ← QUITAR EN PROD
DO C:\S.A.R\PROYECTO\alegra_timer.prg
MESSAGEBOX("Timer Allegra disparó", 64, "Traza")          && ← QUITAR EN PROD
```

**Pendiente investigar:** timer dispara dos veces casi simultáneamente en pruebas. Causa desconocida — pospuesto.

#### s.a.r.prg es el startup compilado
- **`s.a.r.prg`** = archivo de inicio principal → se compila en el `.exe` de Administrator.
- Los PRGs llamados con `DO path_completo.prg` en runtime deben existir como archivos en disco en `C:\S.A.R\PROYECTO\`.

**Mecanismo de ruta de BD:**
- `C:\S.A.R\RutaBaseDatos\ruta.dbf` campo `RUTA` = ruta al `.DBC` activo
- PRGs: `alegra_get_bd.prg` → `PUBLIC LC_ALEGRA_BD`
- Python: `get_bd_path()` en `configurar_allegra.py` / `_leer_ruta_bd()` en `allegra_sync.py`
- **NUNCA hardcodear rutas de BD**

**Backup BD Pilar**: `C:\D\Pilar Peralta\basedatosempresas_BAK_20260321` — punto de restauración seguro.

---

---

## INVENTARIO COMPLETO DE ARCHIVOS — C:\S.A.R\

### Archivos activos del proceso Alegra

| Archivo | Rol | Invocado por |
|---|---|---|
| `allegra_sync.py` | Baja facturas de API Alegra → `allegra_pendientes.dbf` | daemon (subprocess) |
| `alegra_daemon.py` | **v2.2** — Orquesta ciclo, verifica BD, logs comprehensivos, PID file | Windows startup (AlegraDaemon.bat) |
| `interfaz_allegra.py` | Procesa pendientes → PROD_FACT1, notas, marcar. Fase 1 activa. | daemon (subprocess) |
| `configurar_allegra.py` | **v2.2** — Formulario tkinter, auto-restart daemon, auto-refresh log 30s | Acceso directo escritorio |
| `instalar_allegra_bd.py` | Crea allegra_config.dbf y alegra_tiposdoc.dbf si no existen | Subsumido por configurar_allegra.py |
| `instalar_cliente.ps1` | Instala Python, paquetes, archivos, acceso directo, startup | Rafael via terminal remota TUC TUC |
| `merlin_remote.py` | API local para que Merlin opere el PC remotamente | `python merlin_remote.py <codigo>` |
| `AlegraDaemon.exe` | Daemon compilado para distribución (no requiere Python visible) | Obsoleto — reemplazado por AlegraDaemon.bat |

### Archivos de configuración/runtime

| Archivo | Descripción |
|---|---|
| `RutaBaseDatos\ruta.dbf` | Campo `RUTA` → ruta al `.DBC` activo. Lo mantiene Administrator. |
| `bd_esperada.txt` | Ruta DBC esperada para el proceso Alegra. Lo define el usuario en el formulario. |
| `alegra_daemon.log` | Log histórico del daemon (append). Informativo — cada ciclo escribe aqui. |
| `alegra_daemon.pid` | `<PID>\n<VERSION>` — usado por configurar_allegra.py para detectar version y estado. |
| `alegra_daemon.lock` | **Obsoleto** — reemplazado por pid file. Puede eliminarse. |
| `interfaz_allegra.log` | **Obsoleto** — el log ahora va a stdout → ultimo_log en allegra_config.dbf. Puede eliminarse. |
| `alegra_vfp.log` | **Obsoleto** — era del VFP batch mode. Puede eliminarse. |
| `batch_test.log` | **Obsoleto** — era de pruebas batch mode VFP. Puede eliminarse. |

### Archivos de build (PyInstaller)

| Archivo/Carpeta | Descripción |
|---|---|
| `AlegraDaemon.spec` | Spec de PyInstaller para compilar el daemon |
| `build\`, `build_tmp\`, `dist\` | Carpetas de build. No se deben copiar al cliente. |

### Scripts de desarrollo — OBSOLETOS (pueden eliminarse)

Todos los archivos con prefijo `fix_`, `ver_`, `leer_`, `debug_`, `patch_`, `restaurar_`, `revert_`, `crear_` fueron scripts de un solo uso durante el desarrollo. Ya no tienen función activa:

`fix_batch_mode*.py`, `fix_ontimer*.py`, `fix_sct_v*.py`, `fix_interfaz_*.py`, `fix_*.py` (todos),
`ver_*.py`, `leer_*.py`, `debug_scx*.py`, `patch_*.py`, `restaurar_*.py`, `revert_*.py`,
`crear_form_allegra_v2.py`, `crear_bmps2.ps1`, `crear_imagenes_vfp.bat`,
`aplicar_cambios_multisesion.py`, `add_trazas*.py`, `preparar_nit.py`, `limpiar_strtofile.py`,
`rexec.py`, `read_scx.py`, `info_destino.prg`, `leer_boton.prg`, `test_class.prg`

### Archivos VFP activos (en C:\S.A.R\PROYECTO\)

Ver sección PRGs analizados más abajo. Los `.scx/.sct` en `C:\S.A.R\` raíz son copias de trabajo — los activos están en `PROYECTO\`.

---

## FASE PYTHON — interfaz_allegra.py (PRÓXIMO PASO)

### Objetivo
`C:\S.A.R\interfaz_allegra.py` — reemplaza `interfaz_allegra.prg` para el procesamiento automático. Lee `allegra_pendientes.dbf` y escribe en los DBF de Administrator directamente con la librería `dbf`.

---

### interfaz_allegra.prg — ANALIZADO ✅ (2026-04-04)

El PRG tiene **11 pasos** documentados. Este es el mapa completo que Python debe replicar:

#### PASO 0 — Variables PUBLIC
Python no usa variables PUBLIC de VFP, pero estas son las que el PRG setea y que Python debe tener como constantes/parámetros:

| Variable VFP | Valor | Equivalente Python |
|---|---|---|
| `VAR_CODIGO_EMPRESA_USUARIO` | parámetro (02 / LP) | parámetro de función |
| `VAR_CODIGO_TERCERO_USUARIO` | 1 (Rafael, COD_TER=1) | constante |
| `VAR_CODIGO_TERCERO_VENDEDOR` | 0 | constante |
| `VAR_EMPRESA_COSTEA` | 1 (sí costea) | constante — activa costo_ventas_contabiliza |
| `VAR_SALIR_COMPLETO_COSTOS` | 1 (limpia reg_costos_temporal al terminar) | limpiar la tabla al final de cada factura |
| `PVNOMBRE_MAQUINA` | "DESKTOP-B2T06N0" | no aplica en Python |
| `PLNTIPODOC` | dinámico por factura (de alegra_tiposdoc.dbf) | leer de la tabla por factura |
| `VP_CONSECUTIVO_FORMULARIO` | VAL(num_doc de Allegra) | int(num_doc) |

#### PASO 0B — Leer allegra_config.dbf
Lee `max_fact` (default 50). Python respeta ese límite por ejecución.

#### PASO 1 — Tablas que abre
`PROD_FACT`, `PROD_FACT1`, `REG_PROD`, `REG_PROD_SALDOS`, `reg_costos_temporal`, `REG_CTAS`, `REG_CTAS_SALDOS`, `CONSECUTIVOS`, `TERCEROS`, `PRODUCTOS`, `GRUPOS`, `REGCTA_CONSE`, `SAL_DOC`, `reg_ctas_notas_documentos`, `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR`, `AYUDA`

#### PASO 2 — Leer facturas pendientes
```sql
SELECT DISTINCT factura_id, nit_cli, tipo_doc, num_doc, fecha, empresa, met_pago, val_pago
FROM allegra_pendientes
WHERE NOT procesado AND ALLTRIM(empresa) == empresa_param
```
Agrupa por factura. Una factura puede tener múltiples ítems.

⚠️ **DISCREPANCIA DE CAMPOS**: el PRG usa `factura_id`, `nit_cli`, `tipo_doc`, pero `allegra_sync.py` puede usar nombres distintos (`nit`, `tip_doc_alegra`, etc.). **Verificar nombres reales en allegra_pendientes.dbf antes de codificar.**

#### PASO 3 — Resolver cliente: NIT → cod_ter en TERCEROS
```
TERCEROS.IDENTIFICACION == nit_cli → VAR_CODIGO_TERCERO_CONSULTAS = TERCEROS.COD_TER
```
Si no se encuentra el NIT → log + skip factura (no abortar todo).

#### PASO 3B — Resolver tipo documento: Alegra → Administrator
Lee `alegra_tiposdoc.dbf` filtrando por `tip_alegra == tipo_doc_alegra AND empresa == empresa_param`.
Resultado: `PLNTIPODOC` (ej: '013').
Si no hay mapeo → log + skip factura.

#### PASO 4 — Consecutivo
**Opción A (la que usa el PRG):** usar `num_doc` de Allegra tal cual como número de factura en Administrator. No incrementa `CONSECUTIVOS`.

#### PASO 5 — Pre-llenar PROD_FACT + detectar bolsa
Por cada ítem de la factura (`allegra_pendientes` filtrado por `factura_id`):
- Si `'BOLSA' $ UPPER(nombre)` → acumular en `LN_BOLSA`, NO insertar en PROD_FACT ni inventario
- Si el producto no existe en PRODUCTOS → log + skip ítem

Campos escritos en PROD_FACT:
`COD_PRO, CANTIDAD, PRECIO, POR_IVA, VAL_IVA, DESCUENTO, VAL_CON_IVA=(PRECIO*CANTIDAD)-DESCUENTO+(VAL_IVA*CANTIDAD), CLIENTE, EMPRESA, USUARIO, VENDEDOR, FECHAHORA, FECHA_HORA_FINAL, COD_FAC=int(num_doc)`

#### PASO 6 — Por cada ítem en PROD_FACT: STANDAR + PROD_FACT1 + reg_costos_temporal

**6a — STANDAR (inventario)**
Llamado con: `PLNTIPODOC, int(num_doc), DATE(), cantidad, cod_pro, costo`
⚠️ El PRG calcula: `LN_COSTO_SCAN = PROD_FACT.precio * PROD_FACT.CANTIDAD` — usa precio×cantidad como costo (no el campo `costo` de allegra_pendientes, porque Alegra no lo expone).

**6b — PROD_FACT1 (registro definitivo de ventas)**
```sql
INSERT INTO PROD_FACT1 (CONSECUTIVO, COD_PRO, COD_FAC, CANTIDAD, PRECIO,
  DESCUENTO, USUARIO, EMPRESA, FECHAHORA, POR_IVA, VAL_IVA, VAL_CON_IVA,
  VENDEDOR, FECHA_HORA_FINAL, CLIENTE, SECTOR, CONSEALQ, CONREGPRO,
  SEC_ORI, COMISION, COSTO, TIP_FAC)
VALUES (0, cod_pro, int(num_doc), cantidad, precio,
  descuento, cod_ter_usuario, empresa, NOW(),
  por_iva, val_iva, val_con_iva,
  cod_ter_vendedor, NOW(), cod_ter_cliente,
  '', 0, 0, 0, 0, precio*cantidad, PLNTIPODOC)
```
⚠️ PENDIENTE: confirmar campos `SECTOR, CONSEALQ, CONREGPRO, SEC_ORI, COMISION` — el PRG los deja en 0/vacío.

**6c — reg_costos_temporal (tabla de paso)**
```
APPEND BLANK + REPLACE: cod_pro, cantidad, cod_fac, usuario, empresa, tipo_doc, tercero, costo
```

#### PASO 7 — costo_ventas_contabiliza (costos de ventas)
Solo si `VAR_EMPRESA_COSTEA = 1` (siempre True para Pilar).
Lee `reg_costos_temporal`, busca cuentas en PRODUCTOS → GRUPOS, escribe 2 asientos en REG_CTAS por producto:
- Crédito inventario: `cuenta = grupos.cuenta_inve`
- Débito costo ventas: `cuenta = grupos.cuenta_cos`
Actualiza `REGCTA_CONSE`.

#### PASO 8 — contabilizar (asientos contables principales)
**PRGs involucrados — TODOS ANALIZADOS ✅ (2026-04-04):**
`contabilizar.prg` → `valores_insertar.prg` → `inserta_reg_ctas.prg`

**8a — Calcular totales desde PROD_FACT:**
```
LNTOTAL    = SUM(VAL_CON_IVA)
LNIVA      = SUM(VAL_IVA * CANTIDAD)
LNSUBTOTAL = SUM((PRECIO*CANTIDAD) - DESCUENTO)
LNDESCUENTO = SUM(DESCUENTO)
LNTOTAL_REAL = LNTOTAL + LN_BOLSA
```

**8b — Calcular por método de pago:**
```
LN_EFECTIVO = val_pago si met_pago == 'cash' else 0
LN_TARJETA  = val_pago si 'card' in met_pago else 0
LN_TRANSFER = val_pago si met_pago == 'transfer' else 0
LN_CXC      = max(LNTOTAL_REAL - val_pago, 0)
```

**8c — Asignar PVAR_CON_PRO1..9** (dinámico via `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR` + `AYUDA` — ver mapeo sección anterior):
```
PVAR_CON_PRO1 = LNSUBTOTAL       (TXT_SUBTOTAL)
PVAR_CON_PRO2 = LNIVA             (TXT_IVA_DEFINITIVO)
PVAR_CON_PRO3 = LNDESCUENTO       (TXT_DESCUENTO_DEFINITIVO)
PVAR_CON_PRO4 = LN_BOLSA          (TXT_BOLSA_IMPUESTO)
PVAR_CON_PRO5 = LN_TARJETA        (TXT_TARJETA_RECIBIDO)
PVAR_CON_PRO6 = LN_EFECTIVO       (TXT_ABONA_EFECTIVO)
PVAR_CON_PRO7 = LN_CXC            (TXT_COBRAR_CLIENTE)
PVAR_CON_PRO8 = LN_TRANSFER       (TXT_CONSIGNA_TRASFIERE)
```

**8d — contabilizar.prg** (wrapper):
1. Verifica que `PLNTIPODOC` existe en `CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA` para la empresa — si no, no contabiliza nada (**gate crítico**)
2. Pasa PVAR_CON_PRO1..9 como parámetros
3. Llama `DO VALORES_INSERTAR`
4. Llama `DO INSERTA_REG_CTAS WITH lapso, tipo_doc, cod_ter_cliente, num_doc`

**8e — valores_insertar.prg** (construye el cursor con los valores a grabar):
1. Lee `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR` filtrado por `PLNTIPODOC` + empresa, ordenado por ORDEN, DIFERENCIA → cursor `CRREG_CTAS_FINAL`
2. Por cada fila determina `LNVALOR_A_GRABAR`:
   - Si `VAR_CON_PRO > 0`: toma `PVAR_CON_PRO[n]`
   - Si `VALOR_FIJO > 0`: usa ese valor fijo
   - Si `PORCENTAJE > 0`: calcula % sobre cuenta BASE
   - Si `DIFERENCIA = 1`: calcula `LNTOTALDEBITOS - LNTOTALCREDITOS` acumulados
3. Si `DEBITO = 1` → va a `TOTAL_DEBITOS`; si no → `TOTAL_CREDITOS`
4. Si valor > 0 → `ACTUALIZO = 1`
5. Llama `DO VALOR_POR_GRUPOS` (desconocido — probablemente irrelevante para tickets normales)

Campos clave de `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR`:
`DOCUMENTO, EMPRESA, ORDEN, DIFERENCIA, VAR_CON_PRO, DOCUMENTO_CRUZE, DEBITO, VALOR_FIJO, PORCENTAJE, BASE, VALOR_BASE, CUENTA, TERCERO_CUENTA, TERCERO, CCOSTOS`

**8f — inserta_reg_ctas.prg** (escribe en DBF):
Lee `CRREG_CTAS_FINAL` donde `ACTUALIZO = 1`, por cada fila:
1. Incrementa `REGCTA_CONSE.NUM_REG_CTA` → `VAR_CONSECUTIVO`
2. Resuelve tercero según `TERCERO_CUENTA`: 1=tercero del doc, 2=tercero de cuenta base, otro=tercero del registro
3. Busca `DOC_CRUZE` en CUENTAS
4. Si `DOC_CRUZE = 1` → llama `SALDOS_DOCUMENTOS` → escribe `SAL_DOC`
5. INSERT en `REG_CTAS`: `LAPSO, FECHAHORA, TIPO, CONSECUTIVO, CUENTA, TERCERO, TIP_DOC_CRU, NUM_DOC_CRU, VALOR=0, DOCUMENTO, EMPRESA, USUARIO, TER_COD, BODEGA=VAR_CODIGO_BODEGA_ACTUAL, TOT_DEB, TOT_CRE`
6. UPDATE/INSERT `REG_CTAS_SALDOS`: key=CUENTA+EMPRESA+BODEGA, `SALDO += TOT_DEB - TOT_CRE`
7. UPDATE `CONSECUTIVOS` con el número de documento

⚠️ **Variable nueva**: `VAR_CODIGO_BODEGA_ACTUAL` — va al campo BODEGA de REG_CTAS y REG_CTAS_SALDOS. Para empresa 02 → bodega 2, LP → bodega 1. **Setear antes de llamar a este paso.**

#### PASO 9 — Nota del documento
```sql
INSERT INTO reg_ctas_notas_documentos (tipo, numero, empresa, tercero, nota)
VALUES (PLNTIPODOC, num_doc, empresa, cod_ter_cliente, 'Importado de Allegra - ' + factura_id)
```
⚠️ PENDIENTE: confirmar estructura exacta de `reg_ctas_notas_documentos`.

#### PASO 10 — Limpiar y marcar procesado
- `DELETE FROM PROD_FACT WHERE CLIENTE = cod_ter_cliente AND EMPRESA = empresa`
- `DELETE ALL FROM reg_costos_temporal`
- `UPDATE allegra_pendientes SET procesado = True WHERE factura_id = factura_id`

#### PASO 11 — Actualizar allegra_config
`UPDATE allegra_config SET ultima_sin = NOW(), total_proc = total_proc + fact_procesadas WHERE empresa = empresa_param`

---

### Campos de allegra_pendientes.dbf (fuente)
Campos que el PRG lee (nombres exactos del PRG):
`factura_id C(20)`, `nit_cli C(20)`, `tipo_doc C(10)`, `num_doc C(20)`, `fecha D`, `empresa C(5)`, `met_pago C(?)`, `val_pago N(12,2)`, `cod_pro C(20)`, `nombre C(60)`, `cantidad N(10,2)`, `precio N(12,2)`, `por_iva N(5,2)`, `val_iva N(12,2)`, `descuento N(12,2)`, `costo N(12,2)`, `procesado L`

⚠️ **Verificar contra allegra_sync.py** — puede que los nombres difieran (`nit` vs `nit_cli`, `tip_doc_alegra` vs `tipo_doc`, etc.).

### Mapeo de cuentas (documento '013', empresa '02') — confirmado
| VAR_CON_PR | OBJETO | Concepto |
|---|---|---|
| 1 | TXT_SUBTOTAL | Crédito ventas (413548) |
| 2 | TXT_IVA_DEFINITIVO | Crédito IVA (240801) |
| 3 | TXT_DESCUENTO_DEFINITIVO | Débito descuento (530535) |
| 4 | TXT_BOLSA_IMPUESTO | Crédito bolsa (240807) |
| 5 | TXT_TARJETA_RECIBIDO | Débito recaudo tarjeta (11100503) |
| 6 | TXT_ABONA_EFECTIVO | Débito recaudo efectivo (110505) |
| 7 | TXT_COBRAR_CLIENTE | Débito cartera CxC (130505, CRUZE=1) |
| 8 | TXT_CONSIGNA_TRASFIERE | Débito transferencia (111002) |

> Este mapeo se lee dinámicamente de `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR` + `AYUDA` — no hardcodear.

### PRGs analizados — estado completo (2026-04-04)

| PRG | Estado | Rol |
|---|---|---|
| `interfaz_allegra.prg` | ✅ | Orquestador — 11 pasos |
| `standar.prg` | ✅ | Inventario: REG_PROD + REG_PROD_SALDOS |
| `costo_ventas_contabiliza.prg` | ✅ | Costos venta: REG_CTAS × 2 por ítem |
| `contabilizar.prg` | ✅ | Gate + wrapper: verifica CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA, llama valores_insertar + inserta_reg_ctas |
| `valores_insertar.prg` | ✅ | Construye cursor CRREG_CTAS_FINAL con valores PVAR → TOTAL_DEBITOS/TOTAL_CREDITOS |
| `inserta_reg_ctas.prg` | ✅ | Escribe REG_CTAS + REG_CTAS_SALDOS + SAL_DOC + CONSECUTIVOS |
| `busquedad_registros.prg` → `INSERTAR_REG_CTAS_AUTOMATICO` | ✅ | Versión extendida de inserta_reg_ctas (con bancarios, cheques, depreciaciones) |
| `VALOR_POR_GRUPOS` | ❓ | Llamado desde valores_insertar — desconocido, probablemente irrelevante para tickets |

### Variables globales que Python debe tener como constantes

| Variable | Valor | Origen |
|---|---|---|
| `cod_ter_usuario` | 1 | Constante (COD_TER=1, Rafael) |
| `cod_ter_vendedor` | 0 | Constante |
| `empresa_costea` | True | Constante (Pilar sí costea) |
| `bodega` | 2 si emp='02', 1 si emp='LP' | Calculado por empresa |
| `maquina` | "DESKTOP-B2T06N0" | No aplica en Python |

### Detalles técnicos de implementación Python (2026-04-05)

#### _buscar_campo_bin() — lector binario de DBF
`TERCEROS.dbf` tiene un archivo `.fpt` huérfano (el header dice que no hay campos memo pero el .fpt existe). La librería `dbf` de Python lanza `BadDataError` al abrirlo.

**Solución:** `_buscar_campo_bin(ruta, campo_busqueda, valor, campo_retorno, normalizar)` en `interfaz_allegra.py` — lee el DBF directamente con `struct`, byte a byte, sin pasar por la librería. Parámetro `normalizar=True` para NITs con dígito de verificación.

```python
# Uso típico — resolver NIT en TERCEROS
resultado = _buscar_campo_bin(ruta, "IDENTIFICA", "860013730", "COD_TER", normalizar=True)
# normalizar=True: compara solo la parte antes del '-' en el campo leído
# '860013730-5'.split('-')[0] == '860013730' → match
```

**Aplica a:** cualquier tabla VFP que tenga .fpt huérfano. Si en el futuro otra tabla da `BadDataError`, usar este mismo lector.

---

#### _asegurar_tiposdoc() — auto-creación de alegra_tiposdoc.dbf
Llamada al inicio de `_resolver_tipo_doc()`. Si el archivo no existe en la carpeta BD, lo crea con los mapeos por defecto:

| tip_alegra | tip_admin | empresa |
|---|---|---|
| saleTicket | 013 | 02 |
| saleTicket | 013 | LP |
| invoice | (vacío) | 02 |
| invoice | (vacío) | LP |
| creditNote | (vacío) | 02 |
| creditNote | (vacío) | LP |

`invoice` y `creditNote` quedan vacíos → `_resolver_tipo_doc` retorna None → esas facturas se skipean con log. Se deben completar manualmente en el DBF cuando se necesiten.

---

#### num_inicio inteligente en configurar_allegra.py
Cada vez que el formulario abre, `_sugerir_num_inicio(carpeta)` consulta:

1. **allegra_pendientes.dbf** — max `num_doc` donde `procesado=True` por empresa (formato Alegra exacto: `PJP15913`)
2. **PROD_FACT1.dbf** — max `COD_FAC` por empresa + prefijo conocido (`PTV`=02, `PJP`=LP)

Luego compara contra `num_inicio` guardado en `allegra_config.dbf`:
- Si `num_inicio` vacío → lo llena con el sugerido sin avisar
- Si PROD_FACT1 tiene número **mayor** → avisa al usuario y actualiza el campo (evita duplicados)
- Si están al día → no hace nada

Esto corre en **cada apertura del formulario**, no solo la primera vez.

---

#### bd_esperada.txt — protección de BD
`C:\S.A.R\bd_esperada.txt` — almacena la ruta completa al `.DBC` esperado para el proceso Alegra.

- Lo define el usuario en `configurar_allegra.py` → botón "Usar BD activa como esperada"
- El daemon verifica al inicio de cada ciclo: si `ruta.dbf` ≠ `bd_esperada.txt` → aborta y escribe aviso en `ultimo_log`
- Vive en `C:\S.A.R\` (fuera de cualquier BD) para ser siempre accesible
- Si no existe → daemon aborta con mensaje claro

---

### Plan de implementación — actualizado (2026-04-05)

1. ✅ Analizar PRGs VFP — HECHO (2026-04-04)
2. ✅ Verificar campos allegra_pendientes.dbf — coinciden exactamente con allegra_sync.py
3. ✅ `interfaz_allegra.py` creado — PROD_FACT1 activo
4. ✅ Daemon orquesta ambos scripts + guarda log en allegra_config.dbf
5. ✅ `configurar_allegra.py` — formulario completo con BD esperada + num_inicio inteligente
6. ✅ `instalar_cliente.ps1` — instalador automático para PC cliente
7. **Pendiente — próximas fases de interfaz_allegra.py:**
   - `_standar()` → REG_PROD + REG_PROD_SALDOS
   - `_reg_costos_temporal()`
   - `_costo_ventas_contabiliza()` → REG_CTAS costos
   - `_contabilizar()` → REG_CTAS asientos principales (valores_insertar + inserta_reg_ctas)
8. **Pendiente — primera prueba real en BD Pilar** (ver checklist abajo)

---

### Manual por persona — quién hace qué

---

#### PILAR — Uso diario (cuando esté desplegado)

> **Pilar no necesita hacer nada.** El sistema corre automáticamente al encender el PC.

- **AlegraDaemon** arranca con Windows (via `AlegraDaemon.bat` en shell:startup)
- Cada N minutos: baja facturas de Alegra → las registra en Administrator automáticamente
- Pilar ve las facturas ya registradas en Administrator sin tocar nada

**Si quiere verificar o ajustar:**
- Abrir `configurar_allegra.py` (acceso directo en escritorio: "Alegra Configuracion")
- Ver: última sync por empresa, total procesadas, log del último proceso
- Ajustar: max_fact, intervalo, num_inicio por empresa
- Botón "Sincronizar ahora" para forzar sync manual

---

#### RAFAEL — Checklist de despliegue en PC Pilar

> **IMPORTANTE:** En una sesión anterior (remota) ya se instalaron archivos en el equipo de Pilar. Probablemente estén desactualizados. Al desplegar, **reemplazar todos los archivos sin excepción** — no omitir ninguno asumiendo que ya está.

> Ejecutar **en este orden** cuando se vaya a instalar en el PC de Pilar.

##### Pre-requisito: compilar nuevo .exe de Administrator
```
Abrir proyecto VFP en modo desarrollo
Compilar → generar Administrator.exe (incluye el timer en s.a.r.prg)
```

##### Pasos en PC Pilar

1. **Verificar prerequisitos en el PC del cliente:**
   - Python instalado: `python --version` en CMD
   - PyInstaller y dbf instalados:
     ```
     python -m pip install pyinstaller dbf
     ```

2. **Copiar archivos Python** a `C:\S.A.R\`:
   - `allegra_sync.py`
   - `configurar_allegra.py`
   - `alegra_daemon.py`
   - `instalar_allegra_bd.py`

3. **Compilar AlegraDaemon.exe en el PC del cliente** (obligatorio — no copiar el .exe de otro PC):
   ```
   python -m PyInstaller --onefile --noconsole --name AlegraDaemon "C:\S.A.Rlegra_daemon.py" --distpath "C:\S.A.R" --workpath "C:\S.A.Ruild_tmp" --specpath "C:\S.A.R"
   ```

4. **Copiar PRGs VFP** a `C:\S.A.R\PROYECTO\`:
   - `interfaz_allegra.prg`
   - `alegra_timer.prg`
   - `alegra_get_bd.prg`
   - `alegra_forzar_sync.prg`
   - `ver_allegra_pendientes.prg`
   - `agregar_menu_allegra.prg`

5. **Instalar DBFs:**
   ```
   python C:\S.A.R\instalar_allegra_bd.py
   ```
   Crea/migra: `allegra_config.dbf`, `alegra_tiposdoc.dbf` (idempotente)

6. **Configurar parámetros iniciales:**
   - Abrir `configurar_allegra.py`
   - Empresa 02 (TV & Video): `num_inicio` = número de la última factura PTV del día
   - Empresa LP (J&P): `num_inicio` = número de la última factura PJP del día
   - `max_fact = 1`, `intervalo = 1`
   - Clic "Guardar"

7. **Agregar AlegraDaemon.exe a inicio automático** (desde CMD):
   ```
   copy "C:\S.A.R\AlegraDaemon.exe" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\"
   ```

8. **Instalar nuevo .exe de Administrator**

9. **Verificar:**
   - Reiniciar PC
   - Abrir Administrator → el daemon arranca solo y sincroniza en ~1 minuto
   - Revisar `C:\S.A.Rlegra_daemon.log` (debe mostrar "Sync OK")
   - Revisar `allegra_pendientes.dbf` (debe tener registros)
---

#### CLAUDE FUTURO — Notas de retoma

**allegra_sync.py ya es OPERATIVO** — ruta BD dinámica desde `ruta.dbf`, sin MODO_TEST.

**Pendiente técnico principal: PRUEBA COMPLETA local**
1. Backup de `basedatosempresas` antes de correr
2. En el form: max_fact=1, intervalo=1, num_inicio 02=PTV20526, LP=PJP15293
3. Correr `configurar_allegra.py` → Sincronizar ahora
4. Verificar `allegra_pendientes.dbf` se llena
5. En VFP: `DO C:\S.A.R\PROYECTO\interfaz_allegra.prg WITH "02"`
6. Revisar: REG_CTAS (débitos=créditos), PROD_FACT1, REG_PROD
7. Repetir con "LP"

---

### Checklist técnica — estado completo (2026-04-01)

#### ✅ HECHO — Base y conectividad
- [x] API Alegra operativa — credenciales de ambas empresas funcionando
- [x] `allegra_sync.py` — 224 registros correctos en BD TEST, empresas 02 y LP
- [x] `TERCEROS.IDENTIFICACION` = NIT/cédula (nombre largo vía DBC — raw DBF es `IDENTIFICA`)
- [x] Bodegas confirmadas: 02=COD_BOD 2, LP=COD_BOD 1 (tabla BODEGA, campo COD_EMP_AS)
- [x] Backup BD: `C:\D\Pilar Peraltaasedatosempresas_BAK_20260321`

#### ✅ HECHO — Arquitectura Python (2026-04-01)
- [x] `configurar_allegra.py` — tkinter operativo, lee/escribe allegra_config.dbf via ruta.dbf
- [x] `alegra_daemon.py` — single-instance via Windows mutex, log OK, import directo (sin subprocess)
- [x] `AlegraDaemon.exe` — compilado con PyInstaller --onefile --noconsole (9.3MB)
- [x] Acceso directo en escritorio: "Alegra Configuracion.lnk" usando pythonw (sin consola)

#### ✅ HECHO — VFP multi-empresa (2026-04-01/02)
- [x] `interfaz_allegra.prg` — acepta `LPARAMETERS LC_EMP_PARAM`, bodega dinámica, CR_FACTURAS_PENDIENTES filtra por empresa
- [x] `alegra_timer.prg` — loop por empresas de allegra_config.dbf, llama interfaz con parámetro
- [x] Timer en `fondo_menu_limpio.scx` objeto `tmrAllegra` — Init lee config y activa timer
- [x] allegra_config PASO 11 actualiza registro de la empresa correcta (SCAN FOR empresa)
- [x] Bodegas: LP=1, 02=2 (dinámico desde BODEGA table, fallback hardcodeado)

#### ✅ HECHO — Bugs corregidos en prueba local (2026-04-02)
- [x] `allegra_config.dbf` "en uso": timer la dejaba abierta al llamar interfaz. Fix: cerrar antes, reabrir después
- [x] Campo `met_pago` (no `metodo_pago`) en `allegra_pendientes.dbf` — corregido en interfaz_allegra.prg
- [x] Campo `IDENTIFICACION` (vía DBC, no `IDENTIFICA`) en TERCEROS — corregido en interfaz_allegra.prg
- [x] `allegra_pendientes` no se cerraba al salir de interfaz_allegra.prg — corregido con `USE IN` + guard `IF USED()`
- [x] Trazas 1-2-3 en `agregar_menu_allegra.prg` eliminadas

#### 🔴 BUG PENDIENTE — HACER PRIMERO en próxima sesión
**MESSAGEBOX "NIT no encontrado" sin guard `GB_ALLEGRA_MODO_AUTO`** — en modo automático muestra popup a Pilar bloqueando el loop.

En `interfaz_allegra.prg` buscar:
```foxpro
MESSAGEBOX("NIT " + LC_NIT_ALLEGRA + " no encontrado en TERCEROS...
```
Reemplazar por `STRTOFILE(...)` al log `C:\S.A.R\alegra_vfp.log`.

#### Estado prueba local (2026-04-02)
- 118 facturas pendientes en BD TEST: **84 con NIT válido** en TERCEROS, 34 sin NIT
- PROD_FACT1 y REG_CTAS: sin registros nuevos — el MESSAGEBOX bloqueó el loop en la primera factura inválida
- Una vez corregido el MESSAGEBOX, las 84 facturas válidas deberían procesarse automáticamente

#### ✅ HECHO — Mapeo contable empresa 02
- [x] PLNTIPODOC = "013" — código POS Alegra (43.584 facturas en CONSECUTIVOS)
- [x] PVAR_CON_PRO1..8 — mapeo dinámico via CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR + AYUDA
- [x] Impuesto bolsa plástica — detectado por `'BOLSA' $ UPPER(nombre)`, contabilizado via TXT_BOLSA_IMPUESTO

#### ⚠️ ABANDONADO — formulario configurar_allegra.scx (2026-03-22)
Reemplazado por `configurar_allegra.py` (Python tkinter). Causa: bug OBJCODE/METHODS al modificar SCT desde Python. **No retomar esta vía.**

#### 🟡 EN CURSO — Prueba completa local (2026-04-02)
- [ ] Backup de `basedatosempresas` antes de correr
- [x] Bugs de archivos en uso, met_pago, IDENTIFICACION corregidos
- [ ] NIT `1006324944` no existe en TERCEROS TEST → datos de prueba incompletos
- [ ] Verificar REG_CTAS débitos=créditos con un NIT válido
- [ ] Probar empresa LP (num_inicio PJP15293)
- [ ] Confirmar TIPO_INVE del documento '013' en TIPO_DOC (esperado = 2 = salida inventario)

#### 🟩 HECHO hoy (2026-04-04) — Modo fantasma
- [x] `fondo_menu_limpio.scx` — sin trazas MESSAGEBOX (ya estaba limpio)
- [x] `alegra_timer.prg` — TEST MONITOR eliminado
- [x] `s.a.r.prg` — modo batch implementado: detecta `COMMAND()` con "ALLEGRA_SYNC", salta login, corre `interfaz_allegra.prg` para ambas empresas, QUIT
- [x] `alegra_daemon.py` — lanza `C:\S.A.R\Administrator.exe ALLEGRA_SYNC` después del sync Python

#### 🟡 EN CURSO — Prueba modo fantasma (2026-04-04)
- [ ] Compilar nuevo .exe → copiar a `C:\S.A.R\Administrator.exe`
- [ ] Correr `Administrator.exe ALLEGRA_SYNC` desde CMD
- [ ] Verificar `batch_test.log` → debe decir "BATCH MODE" + "BATCH: sync completo"
- [ ] Verificar `alegra_vfp.log` → facturas procesadas por empresa
- [ ] Verificar `PROD_FACT1` y `REG_CTAS` con registros nuevos

#### 🟥 PENDIENTE — Después de prueba exitosa
- [ ] Ejecutar checklist de despliegue completo (ver sección Rafael arriba)
- [ ] Verificar primera ejecución en producción

#### Estrategia modo fantasma — descripción técnica
`AlegraDaemon.exe` lanza `Administrator.exe ALLEGRA_SYNC` como subprocess después de cada sync Python.
`s.a.r.prg` detecta el argumento con `COMMAND()` → setea `LB_BATCH_MODE=.T.` → después de `VARIABLES_SISTEMA` salta el login y corre `interfaz_allegra.prg WITH "02"` + `WITH "LP"` → QUIT.
El Administrator del usuario corre normal, sin cambios visibles.

#### Numeración de facturas — decisión activa
**Opción A activa**: número de Alegra = `LC_NUM_DOC` (se usa tal cual en CONSECUTIVOS/PROD_FACT1).
CONSECUTIVOS empresa='02' TIPO_DOC='013' tiene 43.584 — pendiente verificar si coincide con numeración Alegra real.

---

## 4. Oportunidad estratégica — Reemplazar Allegra

Pilar paga $90.000/mes por Allegra solo para facturación. Si Administrator cubre esa funcionalidad, hay ahorro directo para el cliente y servicio de valor para SAR.

### Datos disponibles para análisis
- `C:\D\Pilar Peralta\basedatosempresas\prod_fact1.dbf` — archivo presente en la BD del cliente. **Propósito desconocido — no asumir** (ver nota en sección 1, Rutas clave).
- Una vez identificado qué es `prod_fact1.dbf`, se puede consultar volumen y estructura.

### Próximos pasos cuando se cierre el negocio
1. Identificar qué es realmente `prod_fact1.dbf` — abrirlo con Python y ver sus campos
2. Revisar el módulo de facturación actual en Administrator y comparar con lo que usa Allegra
3. Definir qué falta en Administrator para reemplazar completamente a Allegra
4. Plan de migración: transición gradual o corte total

---

## 4. Notas técnicas VFP — Aprendizajes

### 4.1 SCX/SCT — Estructura binaria (crítico)

- **SCX/SCT como binario**: VFP almacena formularios como DBF (`.scx`) + FPT memo (`.SCT`). Los METHODS de cada objeto son memo fields en el SCT. Se modifican con Python usando `struct`.
- **Backups numerados**: `_bak1`, `_bak3`, `_bak5` — siempre restaurar desde `_bak5` (punto más limpio).
- **Compile obligatorio**: después de modificar el SCX/SCT siempre correr en VFP:
  ```foxpro
  COMPILE FORM C:\S.A.R\PROYECTO\nombre_form.scx
  ```
- **FPT/SCT corrupción**: insertar bytes en medio del FPT corrompe todos los offsets de memos siguientes. Siempre usar dbf library para escribir memos completos, nunca editar bytes crudos en el medio del archivo.

### 4.2 SCT — Formato FPT y el bug crítico del record length (2026-03-22)

**El bug más importante aprendido:** Cuando Python escribe contenido nuevo al SCT, hay DOS longitudes que deben coincidir:
1. El campo `next_free_block` en el header FPT (bytes 0-3, big-endian) — indica el tamaño total del archivo.
2. El **record length** dentro de cada bloque memo (bytes 4-7 de cada bloque, big-endian) — indica cuántos bytes de contenido hay en ese bloque específico.

Si solo se actualiza `next_free_block` pero NO el record length del bloque, `COMPILE FORM` lee solo los bytes que dice el record length antiguo (ej: 102 bytes de los 5000 que escribiste). El Init se compila truncado, la forma abre vacía.

**Cómo leer/escribir correctamente el SCT con Python:**
```python
import struct

sct_path = r'C:\S.A.R\PROYECTO\nombre.SCT'
with open(sct_path, 'rb') as f:
    data = bytearray(f.read())

# Encontrar el bloque del Init
idx = data.find(b'PROCEDURE Init')
header_start = idx - 8  # 8 bytes antes del contenido: 4 type + 4 length

# Nuevo contenido a escribir
new_content = "PROCEDURE Init\r\n\t... código ...\r\nENDPROC".encode('cp1252')
new_len = len(new_content)

# Construir nuevo SCT
prefix = bytes(data[:header_start])
new_record_header = struct.pack('>I', 1) + struct.pack('>I', new_len)  # type=1, length=correct
new_data = bytearray(prefix + new_record_header + new_content)

# Actualizar next_free_block en header FPT
new_data[0:4] = struct.pack('>I', len(new_data))

with open(sct_path, 'wb') as f:
    f.write(new_data)
```

**Verificación obligatoria antes de COMPILE FORM:**
```python
with open(sct_path, 'rb') as f:
    verify = f.read()
idx = verify.find(b'PROCEDURE Init')
rec_len = struct.unpack('>I', verify[idx-4:idx])[0]
print(f'Record length: {rec_len}')  # debe coincidir con len(new_content)
```

**Estructura del SCX (DBF):**
- `record_size = 109` bytes por registro
- Campos: PLATFORM(C8), UNIQUEID(C10), TIMESTAMP(N10), luego 20 memo fields de 4 bytes c/u
- Campos memo en orden: CLASS, CLASSLOC, BASECLASS, OBJNAME, PARENT, PROPERTIES, PROTECTED, METHODS, OBJCODE, OLE, OLE2, RESERVED1-8, USER
- Registros: COMMENT, DataEnvironment, Form, COMMENT (estructura base mínima)
- Para agregar controles design-time: append registros al SCX DBF + memos al SCT

**PROPERTIES format en SCX:**
```
DoCreate = .T.
Caption = "Texto"
Left = 10
Top = 270
Width = 110
Height = 30
Name = "nombre_control"
```
(Usa `\n` LF-only, no CRLF)

**Agregar registros de controles al SCX desde Python:**
```python
# Quitar EOF marker (0x1A), append nuevo record, agregar EOF de nuevo
# Actualizar record count en bytes 4-7 (little-endian)
```

### 4.3 DEFINE CLASS — Limitación crítica de VFP

**DEFINE CLASS falla silenciosamente cuando se llama desde un DO sub-programa.**

- `DEFINE CLASS` es una directiva de compilación que VFP procesa al compilar un `.prg`.
- Cuando se ejecuta `DO mi_prg.prg` desde el Command Window o desde otra forma, el código compilado del DEFINE CLASS no registra la clase en el ámbito de runtime.
- Síntoma: Solo aparece el primer MESSAGEBOX del PRG (antes del DEFINE CLASS), luego nada. ON ERROR tampoco captura este fallo.
- Confirmado con test mínimo: PRG con `MESSAGEBOX("A") + DEFINE CLASS testc AS Custom + MESSAGEBOX("B")` — solo sale "A".

**Solución:** Poner toda la lógica del form directamente en el SCT del wrapper SCX, usando `ADDOBJECT()` sobre `THIS`. No usar DEFINE CLASS ni PRGs intermedios para definir formularios.

### 4.4 ADDOBJECT en SCT Init — La arquitectura correcta

La arquitectura que funciona para forms abiertos desde el menú de Administrator:

```foxpro
* SCT del wrapper configurar_allegra.scx — PROCEDURE Init
PROCEDURE Init
    THIS.Width      = 480
    THIS.Height     = 320
    THIS.Caption    = "Allegra - Configuracion"
    THIS.AutoCenter = .T.
    * ... más propiedades del form ...

    * Cargar datos desde DBF
    LOCAL lc_cfg, ln_max, ...
    lc_cfg = "C:\D\Pilar Peralta\basedatosempresas\allegra_config.dbf"
    USE (lc_cfg) IN 0 ALIAS allegra_cfg SHARED
    SELECT allegra_cfg : GO TOP
    ln_max = allegra_cfg.max_fact
    USE IN allegra_cfg

    THIS.AddProperty("cfg_path", lc_cfg)

    * Agregar controles
    THIS.AddObject("lbl_titulo", "Label")
    THIS.lbl_titulo.Caption = "Allegra - Configuracion"
    THIS.lbl_titulo.Left = 10 : THIS.lbl_titulo.Top = 8
    THIS.lbl_titulo.Visible = .T.

    THIS.AddObject("spn_max", "Spinner")
    THIS.spn_max.Value = ln_max
    THIS.spn_max.Visible = .T.
    * ... más controles ...

    RETURN .T.
ENDPROC

* Métodos de forma (llamados desde botones design-time con THISFORM.m_guardar())
PROCEDURE m_guardar
    LOCAL ln_mf
    ln_mf = THISFORM.spn_max.Value
    USE (THISFORM.cfg_path) IN 0 ALIAS allegra_sav EXCLUSIVE
    SELECT allegra_sav : GO TOP
    REPLACE max_fact WITH ln_mf
    USE IN allegra_sav
    MESSAGEBOX("Guardado.", 64, "Allegra")
ENDPROC

PROCEDURE m_cerrar
    THISFORM.Release()
ENDPROC
```

**Reglas clave de ADDOBJECT:**
- Siempre poner `Visible = .T.` explícitamente — el default de controles creados con ADDOBJECT es Visible=.F.
- NO intentar setear `THIS.ShowWindow` en Init — es read-only en runtime.
- Usar `THISFORM.` en vez de `THIS.` dentro de métodos de botones design-time.

### 4.5 BINDEVENT — No disponible en esta versión de VFP

`BINDEVENT()` (función VFP 9 para conectar eventos de controles dinámicos a métodos) **no está disponible en la versión de VFP runtime que usa Administrator de Pilar**.

- Síntoma: VFP lanza error "El archivo BINDEVENT.PRG no existe" — lo trata como un programa a DO.
- Causa probable: Runtime VFP 8 o VFP 9 sin las DLLs completas.

**Solución:** Agregar los botones como controles design-time en el SCX (no via ADDOBJECT), con sus métodos Click definidos en el SCT. Así los Click handlers se compilan con COMPILE FORM y funcionan sin BINDEVENT.

Los botones design-time tienen en su METHODS memo:
```foxpro
PROCEDURE Click
    THISFORM.m_guardar()
ENDPROC
```

### 4.6 Otras notas VFP

- **SCAN vs SEEK**: en CR_TERCEROS no se podía hacer SEEK directo (el orden/índice no coincidía con COD_TER). Solución: SCAN/IF/EXIT.
- **Cursor READWRITE**: `INTO CURSOR &lcCursor READWRITE` permite agregar columnas al cursor existente.
- **CDX no actualizado por Python**: dbf library de Python NO actualiza el CDX (índice binario de VFP) al hacer append/insert. Siempre correr `REINDEX` en VFP después de insertar desde Python.
- **Show(1) NO es modal en VFP**: `loForm.Show(1)` = muestra el form, el `1` es window style. Para modal usar `WindowType = 1` en la clase + `loForm.Show()` sin parámetro.
- **CREATEOBJECT con LOCAL**: si loForm es LOCAL y Show() no bloquea, el GC destruye el form al instante. WindowType=1 hace que Show() bloquee.
- **DO (variable)**: usar `lc = "ruta.prg" : DO (lc)` en lugar de `DO ruta.prg` en código guardado en SCX/SCT para evitar que VFP intente resolver la ruta en compilación.
- **Rafael tiene años de experiencia en VFP** — no necesita explicaciones básicas del lenguaje.

### 4.7 Scripts de trabajo en `C:\S.A.R\` (2026-03-22)

| Script | Qué hace | Estado |
|---|---|---|
| `fix_sct.py` | Reescribe el SCT de configurar_allegra con Init ADDOBJECT completo y record length correcto | Supersedido por v8+ |
| `fix_sct_v6.py` | Init + m_guardar con `_SCREEN.SetFocus()` + MESSAGEBOX | Supersedido |
| `fix_sct_v7.py` | Init + m_guardar con `DECLARE MessageBoxA IN user32.dll` | Supersedido |
| `fix_sct_v8.py` | **Init completo + m_guardar sin MESSAGEBOX (THISFORM.Caption = "Guardado")** — última versión sin STRTOFILE | Referencia — v8 es la base limpia |
| `fix_sct_v9.py` | v8 + `ON ERROR MESSAGEBOX(...)` al inicio del Init | Problemático — MESSAGEBOX aparecía detrás de Administrator |
| `fix_sct_v10.py` | v9 + ON ERROR escribe a `allegra_err.txt` con STRTOFILE | Roto — STRTOFILE no existe en este VFP runtime |
| `fix_sct_v11.py` | Init mínimo de prueba con STRTOFILE al inicio | Confirmó la causa raíz: STRTOFILE → compilación falla → forma vacía |
| `fix_sct_v12.py` | **Combinado: (1) OBJCODE=0 en SCX, (2) Init v8 sin STRTOFILE al SCT** | Última versión — corrió OK pero forma sigue vacía (causa desconocida) |
| `revert_scx.py` | Trunca SCX a 4 registros (revierte los que agrega COMPILE FORM) | Necesario después de cada COMPILE FORM accidental |
| `add_buttons_scx.py` | Agrega btn_guardar y btn_cerrar como registros design-time al SCX | Usado en etapas intermedias |
| `compile_allegra.prg` | PRG con ON ERROR para compilar configurar_allegra.scx | **NO ejecutar** — corrompe OBJCODE |
| `instalar_allegra_bd.py` | Instalador idempotente — registra Allegra en formularios.dbf + permisos de usuarios | ✅ Funciona |
| `test_class.prg` | PRG diagnóstico para confirmar que DEFINE CLASS falla en sub-programa | Diagnóstico histórico |

### 4.8 OBJCODE vs METHODS — El bug de SCX/SCT más importante (2026-03-22)

**Contexto**: En el SCX (DBF) existe el campo `METHODS` (puntero al source code en SCT) y el campo `OBJCODE` (puntero al P-code compilado en SCT). VFP prefiere OBJCODE sobre METHODS — si OBJCODE != 0, intenta cargar P-code desde esa posición.

**El bug**: `COMPILE FORM` escribe en `OBJCODE` la posición en bytes del P-code dentro del SCT en ese momento. Luego, cuando Python modifica el SCT (reemplazando el METHODS block con contenido diferente), el tamaño del archivo cambia y la posición en `OBJCODE` queda desapuntando a P-code corrupto o fuera del archivo.

**Resultado**: VFP intenta cargar P-code desde la posición `OBJCODE` → falla (out of range o P-code inválido) → cae back a compilar METHODS en runtime → si METHODS tiene código inválido (ej: `STRTOFILE`) → compilación falla → forma abre vacía con título "Form".

**STRTOFILE no existe**: Esta versión del VFP runtime de Administrator no tiene `STRTOFILE()`. Si se usa, todo el Init falla en compilación.

**Cómo revisar el estado del SCX (Python)**:
```python
import struct
with open(r'C:\S.A.R\PROYECTO\configurar_allegra.scx', 'rb') as f:
    data = f.read()
# Form record: header_size=1032, 2 records antes, record_size=109
# OBJCODE offset dentro del registro = 61
# => posición absoluta = 1032 + 2*109 + 61 = 1311
objcode_val = struct.unpack('<I', data[1311:1315])[0]
print(f'OBJCODE = {objcode_val}')  # debe ser 0 para forzar uso de METHODS
```

**Cómo resetear OBJCODE a 0 (Python)**:
```python
with open(r'C:\S.A.R\PROYECTO\configurar_allegra.scx', 'r+b') as f:
    f.seek(1311)
    f.write(struct.pack('<I', 0))
```

**Secuencia correcta de trabajo (sin COMPILE FORM)**:
1. `python C:\S.A.R\fix_sct_v12.py` — escribe source correcto al SCT y OBJCODE=0 al SCX
2. Abrir la forma en VFP — usa METHODS (source) → VFP lo compila en runtime
3. **No correr COMPILE FORM** — si se corre por error: `python C:\S.A.R\revert_scx.py` + `python C:\S.A.R\fix_sct_v12.py`

### 4.8 Estado actual del formulario configurar_allegra (2026-03-22)

| Componente | Estado |
|---|---|
| Wrapper SCX + SCT | ✅ SCT contiene Init con ADDOBJECT + m_guardar + m_cerrar |
| btn_guardar (design-time) | ✅ Registro en SCX, Click=`THISFORM.m_guardar()` en SCT |
| btn_cerrar (design-time) | ✅ Registro en SCX, Click=`THISFORM.Release()` en SCT |
| Form abre con controles | ✅ Confirmado en prueba — labels, spinners, checkbox, editbox |
| Guardar config funciona | 🔲 Pendiente prueba post-COMPILE FORM con botones design-time |
| BINDEVENT | ❌ No disponible — abandonado, reemplazado por botones design-time |

**Para compilar y probar:**
```foxpro
DO C:\S.A.R\compile_allegra.prg
* → debe decir "Compilado OK"
* Luego: Oficina → facturacion → ALLEGRA
```
