# Manual de Usuario — Compras TUC TUC

**Módulo:** Compras (sugerencias, órdenes y alertas de agotados)
**Versión:** 1.1
**Última actualización:** 2026-11-23
**Audiencia:** Dueños y encargados que compran mercancía para el negocio

---

## La idea en una línea

El sistema mira **lo que se consume cada día** (la rotación) y te dice **qué pedir, cuánto pedir y a quién**, antes de que te quedes sin nada. Consumo = todo lo que sale, se venda o se gaste operando: carnes, empaques, condimentos, servilletas. No usa mínimos fijos: las cantidades salen de tu consumo real.

Dos reglas de oro:

- Los **días mínimos** dicen **CUÁNDO** comprar: si te cubren menos que eso, el producto entra a agotado. Punto.
- Los **días máximos** dicen **CUÁNTO** comprar: la cantidad sugerida te deja cubierto esos días.

---

## Entrar a la pantalla

Desde el inventario administrativo, abre la pestaña **Compras**. Verás tres zonas:

| Zona | ¿Para qué? |
|---|---|
| 🔔 Alertas de agotados | Lo que ya entró a la lista de agotados y lleva días sin reabastecerse |
| ⚙️ Parámetros | Los 7 números globales que gobiernan todo (se guardan solos) |
| 🛒 Sugerencias por proveedor | La propuesta de compra, agrupada por proveedor, lista para ordenar |

---

## Alertas de agotados

Arriba aparece un banner con los ítems en estado agotado: stock actual, mínimo calculado y desde hace cuánto están pendientes.

**¿Para qué sirve?** Es tu semáforo. Si algo lleva muchos días ahí, o lo pides o lo cocinas (si es preparación).

Además, cada vez que un producto **entra** a la lista, te llega un aviso a Telegram con el stock, el mínimo, a quién pedirle (o si toca cocinarlo en sede) y desde hace cuánto está pendiente. Los avisos son oportunos: salen solo cuando hay novedad (un ítem en la mañana, otro en la tarde), una sola vez cada uno, sin repetir ni cansar. Cuando se recupera, no avisa: simplemente desaparece de la lista.

---

## Parámetros globales

Tú pones los días, el consumo pone las cantidades. Son 7 números que aplican a todo el negocio, salvo que un producto tenga sus propios días (ver abajo). **Se guardan solos al salir del campo**: al lado de cada uno hay un puntico que pasa de gris a `…` ámbar (guardando) y luego a `✓` verde con la hora (guardado). Si algo falla, verás `!` rojo.

| Parámetro | Valor inicial | ¿Qué es? |
|---|---|---|
| Stock Máx (días) | 15 | Hasta cuántos días de consumo te deja cubierta la cantidad sugerida |
| Stock Mín (días) | 8 | Si te cubre menos que esto, el producto entra a agotado |
| Días entrega | 2 | Cuánto tarda tu proveedor en entregar (para calcular el Cuándo pedir) |
| Historial (días) | 30 | Hasta dónde se mira atrás para calcular el consumo. Lo más viejo no cuenta |
| Ventana tendencia | 7 | Con cuántos días recientes se compara para detectar si sube o baja |
| Tope sube (%) | 100 | Máximo que se permite proyectar hacia arriba |
| Tope baja (%) | −50 | Máximo que se permite proyectar hacia abajo |

**¿Para qué sirve cada grupo?** Los tres primeros definen tu colchón de compra. Los cuatro últimos definen cómo se calcula lo que vendes al día: promedio de la ventana, ajustado por tendencia (si viene subiendo, sugiere más; si viene bajando, sugiere menos).

El botón **Recalcular Sugerencias de Compra** guarda todo y refresca la propuesta.

---

## Sugerencias por proveedor

Cada proveedor tiene su tarjeta con nombre, teléfono, total estimado, Cuándo pedir y los insumos incluidos. Ábrela para ver el detalle por producto:

| Columna | ¿Qué significa? |
|---|---|
| ✓ | Chulea lo que sí vas a comprar (lo demás no entra a la orden) |
| Producto | Nombre + ahorro si hay promo aprovechable |
| Empaque | Presentación sugerida (ej: bulto × 50) según la mejor cotización |
| Stock | Lo que tienes hoy (en rojo si está en negativo) |
| Demanda | `hist`: promedio real; `proy`: proyectado con tendencia; `↑/↓ %`: hacia dónde va |
| Días Mín/Máx | Días propios de ESE producto (vacío = usa el global). Se guardan solos al salir |
| Cuándo pedir | Día de empezar a pedir: ni antes (sobrestock) ni después (agotados). `Inmediato` (rojo) = pide ya |
| Sugerido | Cantidad propuesta (puedes editarla antes de ordenar) |
| Costo / Subtotal | Valor estimado con el empaque elegido |

**¿Para qué sirve el Cuándo pedir?** Es el día de empezar a pedir, calculado con tu consumo y los días de entrega: si te quedan 5 días de producto y el proveedor tarda 2, empiezas a pedir en 3 días. Antes te sobrestockeas, después sufres agotados.

**¿Cómo elige al proveedor?** Compara tus cotizaciones vigentes y sugiere al del mejor precio: menor costo por unidad, en empaque que te sirve. Si no hay cotizaciones, usa tu último proveedor; si nunca hubo, te lo dice de frente. Antes de ordenar puedes cambiarlo o descartar la línea.

---

## Generar la orden de compra

1. En la tarjeta del proveedor, chulea los insumos que vas a pedir.
2. Ajusta cantidades y costo de empaque si hace falta, y escribe el número de **Documento**.
3. Pulsa el botón de generar orden: se abre un resumen para confirmar.
4. Al confirmar, la orden queda registrada, **se abre WhatsApp** con el pedido listo y el proveedor recibe su enlace propio: desde su pantalla la confirma o propone cambios (cantidad, precio) según su oferta real.

Cada orden tiene un estado que la sigue en su tarjeta:

| Estado | Significado |
|---|---|
| Enviada (Esperando) | Se generó y está esperando respuesta del proveedor |
| Confirmada | El proveedor confirmó (o aceptaste los cambios que propuso) |
| Propuesta con Cambios | El proveedor propuso cambios desde su pantalla; revísalos y aprueba |
| Recibida en Almacén | La mercancía ya entró |

**¿Para qué sirve?** La orden es tu constancia: qué pediste, a quién, por cuánto y en qué va.

---

## Registrar la entrada

Si ya compraste y la mercancía llegó, usa **Registrar Entrada**: lo chuleado viaja a la pestaña de **Entradas** con documento, cantidades y costos, para que solo confirmes el ingreso al inventario.

**¿Para qué sirve?** No digitas dos veces: lo que pediste en Compras aparece listo en Entradas.

---

## Cocinar o comprar

No todo se pide: si el producto tiene receta (es una preparación), el sistema lo marca para **Cocinar en sede** en vez de pedirlo. Esos items se gestionan en **Producción Sugerida**: el Telegram también los avisa, con su stock y su mínimo.

**¿Para qué sirve?** Separa las dos cocinas mentales: lo que se compra afuera y lo que se produce adentro.

---

## Preguntas frecuentes

**¿Por qué sale un producto en agotados?**
Porque su cobertura (stock ÷ consumo diario) quedó por debajo de los días mínimos. No es que esté en cero: es que ya toca pedirlo.

**¿Por qué NO sale un producto que casi no se mueve?**
Si no tiene historia de consumo en la ventana, el sistema no inventa: no lo recomienda. Sin datos no hay sugerencia.

**¿Qué pasa si cambio los días de un producto?**
Solo ese producto usa tus días; los demás siguen con el global. Se guarda solo al salir del campo (mira el ✓ verde).

**¿Cada cuánto se revisa?**
En cada movimiento de inventario: cada entrada o salida re-evalúa ese producto al instante. Sin esperas ni procesos nocturnos.

**¿El sistema compra solo?**
No, nunca. Propone, tú decides: aceptas, ajustas o descartas. La compra definitiva nace cuando tú la confirmas.
