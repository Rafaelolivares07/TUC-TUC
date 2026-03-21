# Proyecto VFP — Administrator (SAR) — Contexto y Pendientes
_Actualizado: 2026-03-21_

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
| Tabla facturas Allegra | `prod_fact1.dbf` (dentro de la ruta anterior) |
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

## 3. Interfaz Allegra ↔ Administrator — PENDIENTE RETOMAR

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
| `REG_CTAS` | SELECT + INSERT | Cuentas por cobrar |
| `reg_ctas_notas_documentos` | INSERT | Notas del documento |
| `TIPO_DOC` | SELECT | Tipos de documento disponibles |
| `CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR` | SELECT | Config. contable |
| `EMPRESA_CONFIGURAR` | SELECT | Config. por empresa/máquina |
| `TERCEROS` | SELECT | Datos del cliente |
| `TELEFONOS` | SELECT | Teléfono del cliente |
| `VENTAS_VENDEDOR` | SELECT | Comisiones |
| `reg_costos_temporal` | APPEND + REPLACE | Costo de ventas |
| `FACTURAR_CONFIGURAR` | SELECT + UPDATE + INSERT | Config. ticket/impresión |
| `facturas_entregas` | INSERT | Despachos |
| `FACTURAR_PERSONAS_FACTURA` | INSERT | Propina/personas (restaurante) |
| `productos_reservas` | SELECT + REPLACE | Liberar reservas |

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

### Fuente de datos: Allegra
- Allegra (empresa que vende el software) expone rutas/endpoints en su web para que aplicativos externos puedan consumir las facturas y notas contables/inventario de cada cliente.
- **Las rutas exactas se perdieron** — pendiente recuperarlas desde el portal/web de Allegra.
- Pilar Peralta es cliente de Allegra. Rafael accede como proveedor/integrador de Administrator.

### Lo que falta para continuar
1. Recuperar las rutas/endpoints del portal web de Allegra
2. Diseñar la interfaz: cómo los datos de Allegra alimentan `facturar_cancelar.scx` — probablemente pre-llenando `PROD_FACT` con los ítems de Allegra y luego disparando el cierre normal

---

## 4. Oportunidad estratégica — Reemplazar Allegra

Pilar paga $90.000/mes por Allegra solo para facturación. Si Administrator cubre esa funcionalidad, hay ahorro directo para el cliente y servicio de valor para SAR.

### Datos disponibles para análisis
- `C:\D\Pilar Peralta\basedatosempresas\prod_fact1.dbf` — facturas de Allegra
- Se puede consultar cuántas facturas hacen por mes, volumen, y comparar con el límite de Allegra

### Próximos pasos cuando se cierre el negocio
1. Revisar el módulo de facturación actual en Administrator y comparar con lo que usa Allegra
2. Consultar `prod_fact1.dbf` para entender estructura y volumen de facturas de Allegra
3. Definir qué falta en Administrator para reemplazar completamente a Allegra
4. Plan de migración: transición gradual o corte total

---

## 4. Notas técnicas VFP — Aprendizajes

- **SCX/SCT como binario**: VFP almacena formularios como DBF+FPT. Los METHODS son memo fields. Se modifican con Python usando `struct`.
- **Backups numerados**: `_bak1`, `_bak3`, `_bak5` — siempre restaurar desde `_bak5` (punto más limpio).
- **Compile obligatorio**: después de modificar el SCX/SCT:
  `COMPILE FORM C:\S.A.R\PROYECTO\contabilidad_movimiento_cuentas_terceros.scx`
- **SCAN vs SEEK**: en CR_TERCEROS no se podía hacer SEEK directo (el orden/índice no coincidía con COD_TER). Solución: SCAN/IF/EXIT.
- **Cursor READWRITE**: `INTO CURSOR &lcCursor READWRITE` permite agregar columnas al cursor existente.
- **Rafael tiene años de experiencia en VFP** — no necesita explicaciones básicas del lenguaje.
