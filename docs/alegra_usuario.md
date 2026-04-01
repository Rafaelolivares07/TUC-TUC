# Manual de Usuario — Módulo Alegra
## Sistema Administrator SAR — Electronicas TV & Video / J&P

_Versión 1.0 — Marzo 2026_

---

## ¿Para qué sirve este módulo?

Usted factura a sus clientes en **Alegra** (el programa de facturación en internet).
Pero sus inventarios, costos y contabilidad viven en **Administrator**.

El módulo Alegra hace ese puente automáticamente:
trae las facturas que usted ya hizo en Alegra y las registra en Administrator,
moviendo inventario y generando los asientos contables correspondientes.

**Resultado:** usted no tiene que digitar nada dos veces.

---

## ¿Qué hace exactamente?

Por cada factura que encuentra en Alegra:

- ✅ Registra los productos vendidos en el inventario (salida de bodega)
- ✅ Genera el asiento contable completo (ventas, IVA, efectivo/tarjeta/transferencia, etc.)
- ✅ Registra el impuesto a la bolsa plástica cuando aplica
- ✅ Marca la factura como procesada para no repetirla

---

## ¿Qué necesita para usar el módulo?

1. Tener **Administrator abierto**
2. Tener **conexión a internet** (para consultar Alegra)
3. El módulo aparece en el menú de Administrator bajo **"Allegra"**

---

## Paso a paso — Sincronizar facturas

### Paso 1 — Abrir el módulo
En el menú de Administrator, haga clic en:
**Allegra → Configurar / Sincronizar**

Se abre la ventana de configuración.

---

### Paso 2 — Revisar los parámetros

| Parámetro | ¿Qué hace? | Valor recomendado |
|---|---|---|
| **Máximo de facturas por lote** | Cuántas facturas procesa en cada ejecución | 50 |
| **Solo desde última sincronización** | Trae solo las nuevas (desde la última vez) | ✅ Marcado |
| **Intervalo automático** | 0 = solo manual | 0 (manual por ahora) |

> La primera vez que sincronice, trae **todas** las facturas disponibles desde el número configurado en adelante.

---

### Paso 3 — Sincronizar

Haga clic en el botón **"Sincronizar ahora"**.

El sistema:
1. Se conecta a Alegra y descarga las facturas nuevas
2. Las procesa una por una en Administrator
3. Al terminar muestra un mensaje con cuántas facturas procesó

> **No cierre Administrator mientras sincroniza.**

---

### Paso 4 — Verificar

Después de sincronizar puede revisar:

**En la ventana de configuración:**
- Fecha y hora de la última sincronización
- Total de facturas procesadas (histórico acumulado)

**En contabilidad de Administrator:**
Abra los movimientos contables y busque por el número de factura de Alegra.

---

## Errores comunes

### "NIT no encontrado en TERCEROS"
**Qué significa:** El cliente de esa factura en Alegra no existe en el directorio de terceros de Administrator.

**Qué hacer:** Busque el cliente en Administrator (módulo de terceros) y verifique que el NIT/cédula esté bien escrito. Si el cliente no existe, créelo en Administrator con el mismo NIT que tiene en Alegra.

---

### "Tipo de documento sin mapeo"
**Qué significa:** Alegra tiene un tipo de factura nuevo que el sistema no reconoce.

**Qué hacer:** Llame a Rafael — es una configuración de 5 minutos.

---

### "Producto no encontrado"
**Qué significa:** Un producto que facturó en Alegra no existe en el inventario de Administrator.

**Qué hacer:** Verifique que el código del producto en Alegra coincida exactamente con el código en Administrator. Si son distintos, corrija en Alegra.

---

### La ventana no abre o aparece vacía
**Qué hacer:** Cierre y vuelva a abrir Administrator. Si persiste, llame a Rafael.

---

## Modo automático — sincronización sin hacer nada

El módulo puede configurarse para sincronizar **automáticamente** cada cierto tiempo,
sin que usted tenga que hacer nada.

### ¿Cómo funciona?

Hay dos procesos que trabajan juntos en segundo plano:

1. **Cada 5 minutos** (aunque Administrator esté cerrado): el sistema consulta Alegra
   y guarda las facturas nuevas en una lista de espera.

2. **Mientras Administrator está abierto**: el sistema revisa esa lista cada N minutos
   y procesa las facturas que encuentre, registrándolas en inventario y contabilidad.

Usted no ve nada — el proceso ocurre silenciosamente.

### ¿Cómo activarlo?

En **Allegra → Configurar / Sincronizar**, ajuste el parámetro:

| Parámetro | Valor |
|---|---|
| **Intervalo automático (minutos)** | 5 (recomendado) |

Con `5`, el sistema revisa cada 5 minutos si llegaron facturas nuevas y las procesa de inmediato.

Con `0`, el modo automático está desactivado — solo sincroniza cuando usted hace clic en **Sincronizar ahora**.

### ¿Qué pasa si Administrator está cerrado?

Las facturas se acumulan en la lista de espera. En cuanto abra Administrator, el sistema las procesa automáticamente.

---

## ¿Con qué frecuencia sincronizar? (modo manual)

Si prefiere el modo manual, **una vez al día al cierre de jornada** es suficiente.

En el menú: **Allegra → Sincronizar ahora**

---

## Lo que el módulo NO hace (por ahora)

- ❌ No crea clientes nuevos automáticamente — deben existir en Administrator
- ❌ No sincroniza devoluciones (notas crédito) — en desarrollo
- ❌ No modifica las facturas en Alegra — solo las lee

---

## Contacto

**Rafael Olivares — SAR**
Para soporte técnico, configuración o dudas sobre el módulo.
