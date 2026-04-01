# Proyecto VFP — Administrator (SAR) — Contexto y Pendientes
_Actualizado: 2026-03-22 — documentación OBJCODE/METHODS bug, estado formulario configurar_allegra, decisión de pausar_

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
- `MODO_TEST = True` → escribe en `basedatosempresas_TEST\` (pruebas)
- `MODO_TEST = False` → escribe en `basedatosempresas\` (producción)
- Autentica en las dos empresas, trae facturas, extrae código del nombre cuando `reference=None`
- **Nuevos campos en `allegra_pendientes.dbf`**: `nombre C(60)` (nombre ítem), `metodo_pago C(20)` (cash/transfer/credit-card), `val_pago N(12,2)` (total pagado en la factura)
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
                 │    ├─ Resolver NIT → TERCEROS.COD_TER (campo IDENTIFICA)
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

### Archivos de la interfaz — ESTADO ACTUAL

| Archivo | Ruta | Estado |
|---|---|---|
| `allegra_sync.py` | `C:\S.A.R\` | ✅ OPERATIVO — v3 2026-03-31 |
| `interfaz_allegra.prg` | `C:\S.A.R\PROYECTO\` | ✅ Listo — tipo_doc dinámico, PVAR dinámico, bolsa, pagos, modo auto |
| `alegra_timer.prg` | `C:\S.A.R\PROYECTO\` | ✅ Nuevo — timer automático con guard re-entrada |
| `alegra_forzar_sync.prg` | `C:\S.A.R\PROYECTO\` | ✅ Nuevo — sincronización manual desde menú |
| `agregar_menu_allegra.prg` | `C:\S.A.R\PROYECTO\` | ✅ Actualizado — arranca ON TIMER al abrir Administrator |
| `configurar_allegra.prg` | `C:\S.A.R\PROYECTO\` | ✅ Listo — formulario VFP completo (SCX bloqueado, ver §3.4) |
| `ver_allegra_pendientes.prg` | `C:\S.A.R\PROYECTO\` | ✅ Listo — BROWSE de pendientes |
| `instalar_allegra_bd.py` | `C:\S.A.R\` | ✅ Listo — crea config, tiposdoc, permisos (idempotente) |
| `instalar_tarea_windows.bat` | `C:\S.A.R\` | ✅ Nuevo — registra allegra_sync.py en Task Scheduler (cada 5 min) |
| `allegra_config.dbf` | `C:\D\Pilar Peralta\basedatosempresas\` | 🔲 Se crea al correr `instalar_allegra_bd.py` |
| `allegra_pendientes.dbf` | `C:\D\Pilar Peralta\basedatosempresas\` | 🔲 Se crea al correr `allegra_sync.py` por primera vez |
| `alegra_tiposdoc.dbf` | `C:\D\Pilar Peralta\basedatosempresas\` | ✅ Creada 2026-03-31 — `saleTicket→013` para 02 y LP |

### Arquitectura de automatización (2026-03-31)

```
Windows Task Scheduler (cada 5 min — independiente de Administrator)
  └─ allegra_sync.py
       ├─ Consulta API Alegra (dos empresas)
       └─ Escribe nuevas facturas en allegra_pendientes.dbf

Administrator (abierto en el local del cliente)
  └─ agregar_menu_allegra.prg  ← se llama al arrancar Administrator
       ├─ Define menú Allegra (Configurar / Ver pendientes / Sincronizar ahora)
       └─ Si allegra_config.intervalo > 0:
            ON TIMER (intervalo * 60) DO alegra_timer.prg

alegra_timer.prg  ← dispara cada N minutos
  ├─ Guard GB_ALLEGRA_PROCESANDO (evita re-entrada)
  ├─ Cuenta registros procesado=.F. en allegra_pendientes.dbf
  └─ Si hay pendientes → DO interfaz_allegra.prg (modo auto, sin popup)

Menú → Sincronizar ahora → alegra_forzar_sync.prg
  ├─ RUN python allegra_sync.py (sincrónico)
  └─ DO interfaz_allegra.prg (modo manual, con popup resultado)
```

**Variables de control:**
- `GB_ALLEGRA_PROCESANDO` (PUBLIC L) — lock de re-entrada
- `GB_ALLEGRA_MODO_AUTO` (PUBLIC L) — `.T.` = timer (sin popup), `.F.` = manual (con popup)

**Campo `intervalo` en `allegra_config.dbf`**: en **minutos**. `0` = solo manual.

**Mecanismo de ruta de BD — `C:\S.A.R\RutaBaseDatos\ruta.dbf`:**
- Campo `RUTA` = ruta al `.DBC` activo en ese equipo (ej: `C:\D\Pilar Peralta\basedatosempresas\DATOS_SAR.DBC`)
- En red: cada PC tiene su propio `ruta.dbf` apuntando a `\\SERVIDOR\...` o ruta local
- Todos los PRGs leen esto via `alegra_get_bd.prg` → `PUBLIC LC_ALEGRA_BD` (carpeta con `\` final)
- `allegra_sync.py` y `instalar_allegra_bd.py` también leen `ruta.dbf` dinámicamente
- **NUNCA hardcodear rutas de BD** — siempre usar `LC_ALEGRA_BD` en PRGs y `_leer_ruta_bd()` en Python

**Para instalar en un equipo nuevo:**
1. Correr `instalar_allegra_bd.py` (crea tablas config en la BD del cliente)
2. Correr `instalar_tarea_windows.bat` como Administrador (registra Task Scheduler)
3. En VFP: agregar `DO C:\S.A.R\PROYECTO\agregar_menu_allegra.prg` al startup de Administrator
4. En `allegra_config.dbf`: setear `intervalo = 5` (minutos) para modo automático

**Backup BD Pilar**: `C:\D\Pilar Peralta\basedatosempresas_BAK_20260321` — punto de restauración seguro.

---

### Manual por persona — quién hace qué

---

#### RAFAEL — Lo que falta hacer (técnico)

**PASO A — Integrar el menú de Allegra en Administrator** *(1 línea de código)*

Buscar en el startup de Administrator el punto donde se lanza el menú principal y agregar:
```foxpro
DO C:\S.A.R\PROYECTO\agregar_menu_allegra.prg
```
Debe ejecutarse DESPUÉS de `DO administrador.mpr` (o el nombre del .mpr que use Administrator). El pad "Allegra" aparecerá en la barra de menú.

**PASO B — Confirmar PVAR_CON_PRO1..9** *(con acceso a VFP, ~5 min)*

Ejecutar en VFP Command (o crear PRG temporal):
```foxpro
USE C:\D\Pilar Peralta\basedatosempresas\REG_CTAS SHARED
SELECT tipo_doc, num_doc, cod_cue, nat_cue, tot_deb, tot_cre;
FROM REG_CTAS;
WHERE ALLTRIM(tipo_doc)='013' AND ALLTRIM(empresa)='02';
AND num_doc = <número de una factura reciente conocida>;
INTO CURSOR CR_CHECK
BROWSE NOCLEAR
```
Resultado: lista de cuentas + montos por factura. Cruzar con `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR` filtrando empresa='02', documento='013'. El campo `VAR_CON_PRO` (1..9) indica a qué PVAR_CON_PROx corresponde cada cuenta.

**PASO C — Confirmar TIPO_INVE del documento '013'** *(1 consulta)*
```foxpro
SELECT codigo, tipo_inve FROM TIPO_DOC WHERE ALLTRIM(codigo)='013'
```
Resultado esperado: `TIPO_INVE = 2` (salida de inventario). Si es diferente, actualizar la llamada a `STANDAR` en `interfaz_allegra.prg`.

**PASO D — Obtener acceso al portal de Allegra** *(requiere gestión con Allegra o con Pilar)*

Ver checklist de Allegra abajo — son ~4 datos que se obtienen en ~10 min con acceso al portal.

**PASO E — Primera prueba con 1 factura** *(sobre el backup `_BAK_20260321`)*

1. En `configurar_allegra.prg` → Máximo de facturas = **1**
2. Sincronizar
3. Revisar:
   - `REG_CTAS`: débitos == créditos para esa factura
   - `PROD_FACT1`: ítem registrado correctamente
   - `REG_PROD` / `REG_PROD_SALDOS`: movimiento de inventario ok
4. Si todo cuadra → aumentar el lote

---

#### PILAR — Lo que necesita para usar la interfaz

> Una vez que Rafael integre el menú (Paso A arriba), Pilar no necesita hacer nada técnico.

**Uso diario** (cuando esté activo):
1. Abrir Administrator normalmente
2. En el menú → **Allegra** → **Configurar / Sincronizar**
3. Clic en **"Sincronizar ahora"** — el sistema jalará las facturas de Allegra y las registrará en Administrator automáticamente
4. El formulario muestra: fecha de última sincronización + total de facturas procesadas históricas

**Si quiere verificar**: Allegra → **"Ver pendientes"** → browse con todas las facturas y su estado (procesado Sí/No)

**Parámetros que puede ajustar** (en el mismo formulario):
- `Máximo de facturas por lote` — cuántas procesa por ejecución (default 50)
- `Intervalo automático` — 0 = solo manual (recomendado al inicio)
- `Solo desde última sincronización` — marcado = solo trae lo nuevo

---

#### CLAUDE FUTURO — Para activar la interfaz con Allegra real

Cuando se tenga acceso al portal de Allegra, completar en `C:\S.A.R\allegra_sync.py`:

```python
# Líneas ~60-64 — reemplazar los "???"
ALLEGRA_BASE_URL   = "https://..."   # URL base del portal
ALLEGRA_CLIENTE_ID = "..."           # ID de Pilar Peralta en Allegra
ALLEGRA_API_KEY    = "..."           # token/clave
ENDPOINT_FACTURAS  = "/facturas"     # endpoint real
ENDPOINT_DETALLE   = "/facturas/{id}/items"  # si los ítems son separados
```

Luego en `obtener_token_allegra()` — descomentear el método que aplique (API key o usuario/contraseña).

Luego en `mapear_item(factura, item)` — reemplazar todos los `"???"` con los nombres reales de campos de la API de Allegra. Los únicos confirmados:
- `cod_pro` de Allegra = mismo código que Administrator ✅ (idénticos)
- `nit_cliente` de Allegra mapea a `TERCEROS.IDENTIFICA` en Administrator ✅

Finalmente en `main()` — descomentar el bloque (lines ~250-262).

---

### Checklist técnica — estado completo

#### ✅ HECHO — BD de Pilar (confirmado 2026-03-21)
- [x] `VAR_CODIGO_EMPRESA_USUARIO = "02"` — EMPRESAS.COD_EMP
- [x] `VAR_CODIGO_BODEGA_ACTUAL = 2` — BODEGAS.COD_BOD=2 'PRINCIPAL'
- [x] `PVNOMBRE_MAQUINA = "DESKTOP-B2T06N0"` — EMPRESA_CONFIGURAR EMPRESA='-1'
- [x] `VAR_CODIGO_TERCERO_USUARIO = 1` — TERCEROS.COD_TER=1 (Rafael)
- [x] `PLNTIPODOC = "013"` — código POS Allegra. 43.584 facturas en CONSECUTIVOS. 8 entradas en CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR
- [x] TERCEROS.IDENTIFICA = NIT/cédula (NO `IDENTIFICACION`)
- [x] TERCEROS.COD_TER = PK (NO `CONSECUTIVO`)
- [x] Todo dentro del mundo Administrator — `allegra_config.dbf` y `allegra_pendientes.dbf` en `C:\D\Pilar Peralta\basedatosempresas\`
- [x] Formulario `configurar_allegra.prg` — dentro de la UI de Administrator, guarda parámetros en la BD de Pilar
- [x] `interfaz_allegra.prg` — lee config (max_fact), procesa facturas, actualiza config (ultima_sin, total_proc)
- [x] `allegra_sync.py` — lee config (max_fact, desde_ult, ultima_sin) antes de llamar a Allegra
- [x] `agregar_menu_allegra.prg` — integración al menú de Administrator (pad "Allegra")
- [x] Backup BD: `C:\D\Pilar Peralta\basedatosempresas_BAK_20260321`

#### ✅ HECHO — Integración al menú de Administrator (2026-03-21)
- [x] Registro en `formularios.dbf`: CONSECUTIV=295, NOMBRE_MEN='ALLEGRA - Configurar y Sincronizar', **NOMBRE='configurar_allegra'** (sin prefijo DO), MODULO=2
- [x] Acceso en `usuarios_perfiles_formularios.dbf`: USUARIO=1 (Rafael) y USUARIO=971 (Pilar)
- [x] Wrapper `configurar_allegra.scx` + `configurar_allegra.SCT` — form invisible (Visible=.F., ShowWindow=0), Init llama el PRG y retorna .F.
- [x] CDX de formularios.dbf reconstruido con `reindex_bd_allegra.prg`
- [x] Instalador `instalar_allegra_bd.py` — idempotente, aplica a cualquier BD (2 comandos)
- [x] `configurar_allegra.prg` — clase frm_allegra con `WindowType=1` (modal real en VFP)

**Flujo completo**: `ayuda_manual.scx` → `DO FORM CONFIGURAR_ALLEGRA` → wrapper SCX Init → `DO (lc_prg)` → PRG define clase + `CREATEOBJECT("frm_allegra")` + `Show()` → form modal de configuración

**Para instalar en BD nueva**:
1. `python C:\S.A.R\instalar_allegra_bd.py "C:\D\BD_NUEVA\"`
2. En VFP: `DO C:\S.A.R\PROYECTO\reindex_bd_allegra.prg WITH "C:\D\BD_NUEVA\"`
3. En VFP: `COMPILE FORM C:\S.A.R\PROYECTO\configurar_allegra.scx`

**Para habilitar acceso a otros usuarios**: insertar en `usuarios_perfiles_formularios.dbf` con COD_TER del usuario, FORMULARIO=295, ESTADO=1

#### ❌ BLOQUEADO — formulario configurar_allegra.scx (2026-03-22)

**Estado**: La forma abre desde el menú de Administrator pero aparece VACÍA (sin controles, título "Form").

**Causa raíz identificada**: Dos problemas encadenados:
1. `COMPILE FORM` escribe en SCX el campo `OBJCODE` apuntando a P-code compilado en el SCT. Cuando Python modifica el SCT (cambiando tamaños), ese puntero queda fuera de rango.
2. VFP intenta cargar el P-code de `OBJCODE` → falla por out-of-range → intenta compilar METHODS → pero el source contenía `STRTOFILE()` que no existe en esta versión de VFP runtime → compilación falla → forma vacía.

**Fix v12 aplicado**: `fix_sct_v12.py` hace (1) `OBJCODE=0` en SCX para que VFP ignore el P-code y use METHODS, (2) restaura Init v8 sin STRTOFILE. El script corrió sin errores. Sin embargo la forma sigue vacía — causa desconocida sin acceso a más herramientas de debug en VFP runtime sin Command Window.

**Decisión**: Pausar el formulario SCX por ahora. Opciones futuras (ver nota al final de esta sección).

**REGLA CRÍTICA para cualquier trabajo futuro en este SCX:**
- **NUNCA correr COMPILE FORM** sobre `configurar_allegra.scx` — cada vez que se corra, OBJCODE queda apuntando a un valor que se desactualiza cuando Python modifica el SCT. Hay que volver a correr `revert_scx.py` + `fix_sct_v12.py`.
- Si se corre COMPILE FORM por accidente: ejecutar `python C:\S.A.R\revert_scx.py` + `python C:\S.A.R\fix_sct_v12.py`

**Opciones para retomar la configuración de Allegra:**
- **Opción A**: Agregar los controles de config Allegra a un formulario de parámetros existente en Administrator (el que Pilar ya usa para otras configs).
- **Opción B**: Crear un nuevo formulario `.scx` desde cero con VFP abierto en modo desarrollo (no compilado), sin tocar el SCT con Python.
- **Opción C**: Usar el `configurar_allegra.prg` directamente (tiene la clase `frm_allegra` completa) y ajustar la entrada desde el menú para llamar al PRG.

#### 🔲 PENDIENTE — Rafael hace esto (no depende de Allegra)
- [ ] Confirmar mapeo PVAR_CON_PRO1..9 (ver script en sección Paso B arriba)
- [ ] Confirmar TIPO_INVE del documento '013' en TIPO_DOC

#### 🔲 PENDIENTE — Depende de acceso al portal Allegra (~10 min con acceso)
- [ ] URL base del portal de Allegra
- [ ] Endpoint de facturas (GET/POST, params de filtro)
- [ ] Endpoint de ítems por factura (o si vienen dentro)
- [ ] Tipo de autenticación (API key, OAuth, usuario/contraseña)
- [ ] Nombres de campos en la respuesta JSON (id, nit, cod_pro, cantidad, precio, iva, etc.)
- [ ] ¿Allegra expone el costo del producto?

#### 🔲 PENDIENTE — Decisión técnica abierta
- [ ] Numeración de facturas: **Opción A activa** (número de Allegra = LC_NUM_DOC). CONSECUTIVOS empresa='02' TIPO_DOC='013' tiene 43.584 — ¿estos coinciden con números de Allegra? Verificar con una factura real.

#### Estrategia de prueba (antes de activar en producción)
1. Backup activo ✅ (`basedatosempresas_BAK_20260321`)
2. `configurar_allegra.prg` → Máximo = **1**
3. Sincronizar → revisar REG_CTAS (débitos=créditos), PROD_FACT1, REG_PROD
4. Si ok → aumentar lote gradualmente

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
