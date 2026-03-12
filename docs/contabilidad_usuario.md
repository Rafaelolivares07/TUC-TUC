# Módulo Contabilidad — Manual de Usuario

**Plataforma:** TUC TUC
**Dirigido a:** Dueños de negocio, contadores, administradores
**Última actualización:** 2026-03-12

---

## ¿Qué hace el módulo de Contabilidad?

TUC TUC registra automáticamente los asientos contables de tu negocio cada vez que ocurre una transacción: una venta en caja, un pedido entregado a domicilio, una entrada de inventario. No tienes que ingresar nada a mano — el sistema lo hace por ti, siguiendo las reglas que tú mismo defines.

Para que eso funcione, primero haces la parametrización una sola vez. Luego el sistema trabaja solo.

---

## 1. Acceder al módulo

Desde el panel de administración de tu negocio, busca la pestaña o enlace **Contabilidad**. El módulo tiene cuatro secciones:

1. **Plan de Cuentas** — las cuentas contables que usa tu negocio
2. **Tipos de Documento** — los documentos contables (venta, compra, etc.)
3. **Parametrización** — las reglas de cómo se genera cada asiento
4. **Comprobantes** — el histórico de asientos generados

---

## 2. Plan de Cuentas

### ¿Qué es?

El plan de cuentas es la lista de cuentas contables que tu negocio utiliza. TUC TUC viene con el **Plan Único de Cuentas (PUC) colombiano** pre-cargado, y tú simplemente adoptas las que necesitás.

### Cómo agregar una cuenta

1. En el campo de búsqueda, escribe parte del nombre o el código de la cuenta (ej: `caja`, `1105`, `ingresos`)
2. El buscador mostrará las coincidencias del PUC
3. Haz clic en **Adoptar** junto a la cuenta que quieres usar
4. Opcionalmente, puedes ponerle un alias personalizado (ej: "Caja Principal")

### Notas importantes

- Solo puedes usar en parametrización las cuentas que hayas adoptado primero
- Las cuentas adoptadas se pueden inactivar si dejan de usarse — no se eliminan para no afectar el histórico
- El PUC está organizado en niveles: Clase → Grupo → Cuenta → Subcuenta. Solo las cuentas del nivel más detallado aceptan movimientos

---

## 3. Tipos de Documento

### ¿Qué es un tipo de documento?

Es la categoría del asiento contable. Ejemplos típicos:

| Código | Nombre sugerido | Cuándo lo genera el sistema |
|---|---|---|
| `VENTA_POS` | Venta en caja | Cada vez que el cajero registra una venta en el POS |
| `VENTA_DOM` | Venta domicilio | Cuando marcas un pedido como "Entregado" |
| `COMPRA` | Compra / Entrada inventario | Cuando registras una entrada de inventario |
| `VENTA` | Venta restaurante | Cuando cobras una mesa en el restaurante |

### Cómo crear un tipo de documento

1. Haz clic en **Nuevo tipo de documento**
2. Ingresa el **Código** — debe ser exactamente el que el sistema espera (ver tabla arriba). Distingue mayúsculas.
3. Ingresa el **Nombre** descriptivo (es solo para que tú lo identifiques)
4. Guarda

> **Importante:** el código del tipo de documento es el que conecta tus reglas con los eventos del sistema. Si el código no coincide exactamente, el sistema no encontrará la parametrización y no generará el asiento.

---

## 4. Parametrización

Esta es la parte central del módulo. Aquí defines las reglas de cómo se contabiliza cada evento.

### ¿Qué es una parametrización?

Es el "molde" del asiento contable. Defines, línea por línea, qué cuentas se debitan y cuáles se acreditan, y cómo se obtiene el monto de cada una.

### Paso 1 — Crear la cabecera

1. Haz clic en **Nueva parametrización**
2. Elige el **Tipo de documento** (ej: `VENTA_POS`)
3. Escribe una **Descripción del asiento** — este texto aparecerá en los comprobantes (ej: "Registro de venta en caja POS")
4. Guarda

### Paso 2 — Agregar líneas al asiento

Con la cabecera creada, haz clic en **Editar líneas**. Se abre el editor de líneas del asiento.

Cada línea representa un movimiento contable (un débito o un crédito). Completa:

**Cuenta:** La cuenta del plan de cuentas que se afecta

**Movimiento:** `D` = Débito / `C` = Crédito

**Origen del monto:** aquí defines cómo se obtiene el valor de esta línea:

| Origen | Cuándo usarlo | Qué ingresar |
|---|---|---|
| **Fijo** | El monto siempre es el mismo (ej: una cuota fija) | Ingresa el valor numérico |
| **Heredado de fuente** | El monto viene de la transacción (venta, compra) | Elige la fuente y la variable (ej: `ventas_pos → total_venta`) |
| **Calculado** | El monto se calcula en base a otras líneas | Escribe una fórmula (ej: `L1*0.19` = 19% de la línea 1) |
| **Manual** | El monto lo ingresa el contador a mano después | No requiere valor — el sistema deja la línea en blanco |

### ¿Qué es una "fuente"?

Cuando el origen es **Heredado de fuente**, el sistema te pide que elijas qué información tomar de la transacción. Las fuentes disponibles son:

| Fuente | Qué representa | Variables disponibles |
|---|---|---|
| `ventas_pos` | Ventas registradas en caja POS | subtotal_venta, iva_venta, total_venta |
| `ventas_domicilio` | Pedidos entregados a domicilio | subtotal_venta, iva_venta, total_venta |
| `compras_tienda` | Entradas de inventario | subtotal_compra, iva_compra, total_compra |
| `ventas_restaurante` | Cobros de mesa en restaurante | subtotal_venta, iva_venta, total_venta |

> **Regla:** dentro de una misma parametrización, todas las líneas "Heredado de fuente" deben usar la **misma fuente**. No puedes mezclar `ventas_pos` con `ventas_domicilio` en el mismo parámetro. Si intentas hacerlo, el sistema te lo impedirá con un aviso. Esto es correcto: cada parametrización responde a un solo tipo de evento.

### Ejemplo completo: Venta en caja POS

Supongamos una venta de $100.000 con IVA 19% incluido (subtotal $84.034, IVA $15.966).

| # | Cuenta | Mov | Origen | Valor/Variable |
|---|---|---|---|---|
| L1 | 1105 — Caja | D | Heredado de fuente | ventas_pos → total_venta |
| L2 | 2408 — IVA por pagar | C | Heredado de fuente | ventas_pos → iva_venta |
| L3 | 4135 — Ingresos comercio | C | Heredado de fuente | ventas_pos → subtotal_venta |

Cuando el cajero registre una venta de $100.000, el sistema generará automáticamente:

```
Débito:   1105 Caja                   $100.000
Crédito:  2408 IVA por pagar           $15.966
Crédito:  4135 Ingresos comercio       $84.034
```

### Ejemplo con fórmula calculada

Si quieres que el IVA lo calcule el sistema en base al total (en lugar de tomarlo de la variable):

| # | Cuenta | Mov | Origen | Valor/Fórmula |
|---|---|---|---|---|
| L1 | 1105 — Caja | D | Heredado | ventas_pos → total_venta |
| L2 | 2408 — IVA por pagar | C | Calculado | `L1*19/119` |
| L3 | 4135 — Ingresos | C | Calculado | `L1-L2` |

La fórmula `L1*19/119` toma el valor de la línea 1 (total_venta) y calcula el IVA. `L1-L2` calcula el subtotal restando el IVA al total.

---

## 5. Comprobantes generados

En la pestaña **Comprobantes** puedes ver todos los asientos generados por el sistema. Cada comprobante muestra:

- Número secuencial automático (ej: `AUTO-VENTA_POS-0001`)
- Fecha y descripción
- Detalle de débitos y créditos
- Total débitos y total créditos

Los comprobantes generados automáticamente tienen el prefijo `AUTO-`. Los manuales no lo tienen.

---

## 6. IVA por producto — Módulo Tienda

### Cómo asignar el IVA a un producto

En el panel de administración de tu tienda, al crear o editar un producto, encontrarás el campo **% IVA**. Opciones disponibles:

- **0%** — producto exento de IVA
- **5%** — tarifa reducida (alimentos, medicamentos)
- **19%** — tarifa general
- **Otro %** — ingresa el porcentaje que necesites

El precio que ingresas para el producto **incluye el IVA**. El sistema calcula el desglose automáticamente.

### Cómo se ve el IVA en el POS (caja)

Al agregar productos al carrito, si alguno tiene IVA, el panel del carrito mostrará:

```
IVA incluido: $15.966
Total:        $100.000
```

### Recibo al cliente

El recibo que se genera después de cobrar muestra:

```
1x Producto A              $50.000  (IVA 19%)
1x Producto B              $50.000  (IVA 19%)
─────────────────────────────────────
Subtotal                   $84.034
IVA incluido               $15.966
Total                     $100.000
```

### Ticket impreso

El ticket de impresión incluye las líneas de Subtotal e IVA antes del TOTAL, para que el cliente tenga el desglose completo.

### Mensaje por WhatsApp

Si el cliente tiene teléfono registrado, puedes enviarle el recibo por WhatsApp. El mensaje incluye el desglose de IVA cuando aplica.

---

## 7. Flujos completos por canal de venta

### Canal 1 — Venta en caja POS

1. El cajero agrega productos al carrito en la pantalla POS
2. Selecciona método de pago y hace clic en **Cobrar**
3. El sistema registra el pedido y **en ese mismo momento genera el asiento contable** (`VENTA_POS`)
4. El cajero ve el recibo con el desglose de IVA
5. Puede imprimir el ticket o enviarlo por WhatsApp

### Canal 2 — Pedido desde URL pública (domicilio)

1. El cliente hace el pedido desde la página pública de la tienda
2. El pedido queda en estado "Pendiente" — **aún no se contabiliza**
3. Cuando el admin marca el pedido como **Entregado**, el sistema genera el asiento contable (`VENTA_DOM`)
4. La lógica es: solo se registra la venta cuando la entrega está confirmada

### Canal 3 — Entrada de inventario (compra)

1. El admin registra la entrada de inventario con los productos recibidos, cantidades, precios y % de IVA
2. Al guardar, el sistema genera el asiento contable (`COMPRA`) automáticamente

### Canal 4 — Cobro de mesa (restaurante)

1. El mesero registra los pedidos de la mesa
2. Cuando el cajero hace clic en **Cobrar mesa**, el sistema registra el cobro y genera el asiento contable (`VENTA`)

---

## 8. Preguntas frecuentes

**¿Qué pasa si no tengo parametrización para un tipo de documento?**
El sistema registra la transacción normalmente (la venta, la compra, el cobro), pero no genera asiento contable. No hay error ni aviso — simplemente no hay movimiento contable. Puedes parametrizar en cualquier momento y los nuevos eventos se contabilizarán a partir de ahí.

**¿Puedo inactivar una parametrización sin eliminarla?**
Sí. Con el botón de estado en la lista de parametrizaciones, puedes activarla o inactivarla. Mientras esté inactiva, el motor la ignora.

**¿Puedo tener parametrizaciones distintas para ventas POS y ventas a domicilio?**
Sí, precisamente para eso existen los tipos de documento `VENTA_POS` y `VENTA_DOM`. Son parametrizaciones independientes con sus propias reglas y cuentas contables.

**¿El sistema me avisa si el asiento no cuadra (débitos ≠ créditos)?**
El sistema genera el asiento con los valores que resultan de la parametrización. Si la parametrización está bien construida, el asiento cuadra siempre. Si hay un error en la parametrización (por ejemplo, olvidaste una línea de crédito), el comprobante quedará descuadrado — revisa la parametrización en ese caso.

**¿Puedo ver los comprobantes ya generados?**
Sí, en la pestaña **Comprobantes** del módulo de contabilidad, con filtro por fecha y tipo de documento.

**¿Qué significa "Fuente bloqueada" cuando agrego una línea?**
Significa que ya existe otra línea en esa parametrización que usa una fuente específica (por ejemplo `ventas_pos`). El sistema exige que todas las líneas "Heredado de fuente" usen la misma fuente. Esto garantiza que el asiento sea coherente — todos sus valores vienen del mismo evento.
