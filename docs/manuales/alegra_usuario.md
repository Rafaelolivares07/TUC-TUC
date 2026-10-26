# Manual de Usuario — Módulo Alegra
## Sistema Administrator SAR — Electronicas TV & Video / J&P

_Versión 2.8 — Abril 2026_

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
- ✅ Actualiza los saldos de existencias por producto
- ✅ Genera el asiento de costo de ventas (inventario → costo ventas)
- ✅ Genera el asiento contable completo (ventas, IVA, efectivo/débito/crédito/transferencia/CxC, etc.)
- ✅ Registra el impuesto a la bolsa plástica cuando aplica
- ✅ Marca la factura como procesada para no repetirla

---

## ¿Qué necesita para usar el módulo?

1. El programa **AlegraDaemon** corriendo en segundo plano (se inicia automáticamente con Windows)
2. Tener **conexión a internet** (para consultar Alegra)
3. El formulario de control se abre desde el acceso directo **"ADMINISTRATOR INTERFASES"** en el escritorio

---

## El formulario de control

Al abrir el formulario verá cuatro pestañas:

### Pestaña Configuración
Parámetros por empresa:

| Parámetro | ¿Qué hace? |
|---|---|
| **Máximo de facturas por ciclo** | Cuántas facturas procesa en cada vuelta automática |
| **Pausa entre ciclos (seg)** | Tiempo de espera entre una vuelta y la siguiente. `0` = solo manual |
| **Auto-crear NITs** | Si está marcado, crea el cliente automáticamente cuando no existe en Administrator |

> **Intervalo en segundos**: el valor que ponga aquí son segundos de descanso entre ciclos. Si pone `10`, el sistema espera 10 segundos después de terminar cada ciclo antes de iniciar el siguiente.

---

### Pestaña Facturas

Muestra el estado de todas las facturas descargadas de Alegra. Tiene cuatro secciones:

| Sección | Color | Qué contiene |
|---|---|---|
| **Pendientes** | Azul | Facturas que aún no se han procesado |
| **Con inconsistencias** | Rojo | Facturas que fallaron — no se pudieron procesar |
| **Procesadas** | Verde | Facturas procesadas correctamente |
| **Procesadas con alertas** | Naranja | Facturas procesadas pero con alguna salvedad técnica |

**¿Qué es una "Procesada con alerta"?**
Son facturas que se registraron correctamente en Administrator, pero durante el proceso se detectó alguna situación que no impidió el registro pero que vale la pena conocer. Ejemplos:
- Un producto cuyo saldo o valor de existencias era demasiado alto para el campo (overflow) — el costo del ítem se tomó como cero pero el inventario se movió
- Productos sin cuenta contable asignada (grupo=0) — el asiento de costo de ventas no se generó para ese ítem

La factura queda registrada; la alerta aparece en la columna **"Motivo/Alerta"** de esa sección.

---

### Pestaña Terceros

Muestra los NITs de clientes que Alegra tiene pero que no existen en Administrator.

Desde aquí puede:
- **Crear** el cliente en Administrator con los datos de Alegra
- **Ignorar** el NIT (no volver a preguntar)

Si **Auto-crear NITs** está activado en Configuración, esto ocurre automáticamente.

---

### Pestaña Estado & Log

Muestra:
- Estado del daemon (corriendo / pausado / detenido)
- El log del último ciclo ejecutado
- Botones de control:

| Botón | ¿Qué hace? |
|---|---|
| **Pausar** | Detiene los ciclos automáticos (el daemon sigue corriendo pero no ejecuta) |
| **Reanudar** | Reactiva los ciclos automáticos |
| **Un ciclo** | Ejecuta un solo ciclo ahora mismo (útil en modo manual) |
| **Borrado DBF (DELETE)** | Limpia registros marcados como eliminados en las tablas locales. **Solo disponible cuando el daemon está pausado.** |
| **Reiniciar proceso** | Borra todas las facturas pendientes y reinicia la sincronización desde el número configurado. **Use con precaución — es irreversible.** |

---

## Modo automático — sincronización sin hacer nada

El sistema puede configurarse para sincronizar automáticamente cada cierto tiempo.

### ¿Cómo funciona?

Hay dos procesos que trabajan juntos en segundo plano:

1. **AlegraDaemon** (siempre activo): ejecuta ciclos cada N segundos — descarga facturas nuevas de Alegra y las procesa en Administrator.

2. Los ciclos son **secuenciales**: primero descarga (`allegra_sync`), luego procesa (`interfaz_allegra`). El siguiente ciclo no empieza hasta que el anterior termine por completo.

Usted no ve nada — el proceso ocurre silenciosamente.

### ¿Cómo activarlo?

En la pestaña **Configuración**, ajuste:

| Parámetro | Valor |
|---|---|
| **Pausa entre ciclos (seg)** | 300 (5 minutos recomendado) |

Con `300`, el sistema espera 5 minutos después de cada ciclo antes de iniciar el siguiente.

Con `0`, el modo automático está desactivado — solo procesa cuando usted hace clic en **Un ciclo**.

---

## Errores comunes — pestaña "Con inconsistencias"

### "NIT no encontrado en TERCEROS"
**Qué significa:** El cliente de esa factura en Alegra no existe en el directorio de terceros de Administrator.

**Qué hacer:** Vaya a la pestaña **Terceros** y cree o vincule el cliente. O active **Auto-crear NITs** en Configuración.

---

### "Tipo de documento sin mapeo"
**Qué significa:** Alegra tiene un tipo de factura que el sistema no reconoce.

**Qué hacer:** Llame a Rafael — es una configuración rápida.

---

### "Producto no encontrado"
**Qué significa:** Un producto que facturó en Alegra no existe en el inventario de Administrator.

**Qué hacer:** Verifique que el código del producto en Alegra coincida exactamente con el código en Administrator.

---

### La ventana no abre o aparece vacía
**Qué hacer:** Cierre y vuelva a abrir el formulario desde el acceso directo del escritorio. Si persiste, llame a Rafael.

---

## Alertas — pestaña "Procesadas con alertas"

Estas facturas **ya quedaron registradas** en Administrator. La alerta es informativa.

| Tipo de alerta | Qué significa |
|---|---|
| "Producto X: saldo/valor fuera de rango" | El saldo o valor de existencias del producto excede el límite del campo en Administrator. El inventario se movió pero el costo del ítem se tomó como cero. |
| "Costo ventas sin contabilizar (grupo=0)" | Uno o más productos no tienen cuenta contable asignada (grupo=0). El asiento de costo de ventas no se generó para esos ítems. |

**¿Qué hacer?** Notifique a Rafael para revisar la configuración contable o los saldos del producto en cuestión.

---

## Lo que el módulo NO hace (por ahora)

- ❌ No crea productos nuevos automáticamente — deben existir en Administrator
- ❌ No sincroniza devoluciones (notas crédito)
- ❌ No modifica las facturas en Alegra — solo las lee

---

## Contacto

**Rafael Olivares — SAR**
Para soporte técnico, configuración o dudas sobre el módulo.
