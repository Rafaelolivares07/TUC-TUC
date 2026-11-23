# Cómo vender el módulo de Compras TUC TUC

**Documento:** guion comercial para vendedores
**Versión:** 1.1
**Fecha:** 2026-11-18
**Actualizado:** 2026-11-22 (8 ventajas afinadas con Rafael: consumo, sin canales, proveedor confirma); 2026-11-23 (#2 precisado: momento de empezar, columna Cuándo pedir); 2026-11-23 (#6 avisos absorbido por #2, quedan 7); 2026-11-23 (reorden: dias primero; #1 avisa cuando se agota, 2 estados); 2026-11-23 (#1 autocontenido 8/15; cada punto se defiende solo); 2026-11-23 (COMO FUNCIONA final: fusion 1+2, 5 puntos + cierre)
**Audiencia:** vendedores ante un posible comprador (dueño de restaurante, tienda o negocio con inventario)

> Regla de oro: todo lo que sigue existe y funciona hoy en producción. Si el cliente pide algo fuera de aquí, se anota como solicitud, no se promete.

---

## El problema (para abrir la conversación)

Todo negocio que compra mercancía sufre lo mismo:

1. **Se queda sin productos sin darse cuenta** — se entera cuando el cliente los pide y ya no hay.
2. **Compra de más o de menos** — pide "al ojo", sin saber cuánto se consume realmente al día.
3. **Pierde tiempo cotizando** — llama proveedores, compara precios en la cabeza y arma el pedido en un papel, un Excel o chats regados.

Pregunta de apertura: *"¿Cuántas veces este mes se quedaron sin algo en plena operación?"*

---

## La promesa (una frase)

*TUC TUC mira lo que consumes cada día y te dice qué pedir, cuánto pedir y a quién — antes de que te quedes sin nada.*

---

## El pitch de 60 segundos (léelo tal cual)

*"Mire cómo funciona. El sistema aprende de su consumo real — se venda o se gaste operando — no de números que usted tenga que inventar. Cuando algo se acerca a agotarse, le llega un aviso oportuno a su celular: qué es, cuánto queda y a quién pedirle, una sola vez, sin cansar. Usted abre Compras y la propuesta viene armada por proveedor: cantidades de su consumo, mejor precio entre sus cotizaciones, ofertas y días de descuento cazados, y el momento justo de empezar a pedir cada cosa: ni antes ni después. Revisa, ajusta si quiere y genera la orden: el proveedor la confirma o la ajusta desde su pantalla, y usted ve el estado sin llamar a nadie. Cuando llega la mercancía, la entrada viaja sola al inventario, sin digitar dos veces. Usted siempre aprueba — nada se pide sin que usted lo confirme."*

---

## ¿Cómo funciona?

**1. ¿QUÉ COMPRAR? -> Lo que entra en agotado.**
Usted pone los días: mínimos (su colchón — debajo de ahí, hay que comprar) y máximos (hasta dónde lo deja cubierta la sugerencia). Vienen en 8/15 por defecto y los ajusta a su negocio. Cuando lo que hay de un ítem ya no cubre sus días mínimos, entra en estado de agotado y se incluye en la solicitud de compra; con sus estadísticas de consumo, el algoritmo lo detecta solo.

**2. Cuándo comprar: el momento justo de empezar.**
Cada ítem marca el día en que debe empezar a pedirlo: ni antes (se sobrestockea) ni después (sufre agotados). Se calcula con su consumo y lo que tarda el proveedor en entregar. Y cuando llega ese momento, le cae un aviso oportuno al celular: qué es, cuánto queda y a quién pedirle, una sola vez, sin repetir ni cansar.

**3. Cuánto comprar: la cantidad exacta.**
La cantidad que lo deja cubierto hasta sus días máximos: ni bodega llena de más ni carrera de última hora.

**4. A qué precio comprar: selecciona el mejor precio.**
Usted descarta primero las ofertas o cotizaciones que fallan en calidad de producto o servicio, y se queda con las que sí cumplen. Entre esas, la aplicación hace la búsqueda por usted: compara cotizaciones, presentaciones, ofertas y días de descuento, para que usted pague menos. La aplicación asiste, usted decide.

**5. A quién comprar, de punta a punta.**
El mejor precio define al proveedor: la propuesta llega agrupada por proveedor y la orden de compra viaja con enlace propio: el proveedor la confirma o la ajusta desde su pantalla, y usted ve el estado sin llamar a nadie.

*La app propone, usted chulea, ajusta y confirma.*

---

## Objeciones y respuestas

**"Yo ya sé lo que tengo que pedir."**
*"Claro, usted conoce su negocio. Esto no lo reemplaza: le hace la cuenta que usted haría si tuviera tiempo de revisar 300 productos todos los días. Usted sigue aprobando todo."*

**"¿Y si sugiere mal?"**
*"Sugiere con sus propios números, y antes de ordenar usted ve, ajusta cantidades, cambia proveedor o descarta líneas. Nada se compra sin su visto bueno."*

**"Mis productos son preparaciones, no compras."**
*"El sistema los separa solo: lo que tiene receta sale como 'cocinar en sede' y se gestiona en Producción; lo de comprar afuera va a Compras. Cada cosa en su carril."*

**"¿Tengo que alimentar datos?"**
*"No. Aprende del consumo que usted ya registra: ventas y movimientos. Entre más lo use, más fino sugiere."*

---

## La demo de 5 minutos (paso a paso)

1. **Muestre un aviso real en el celular** (1 min): un agotado con stock, mínimo y el "pedir a".
2. **Abra Compras** (1 min): señale el banner de agotados y una tarjeta de proveedor con su total y su Cuándo pedir.
3. **Abra una tarjeta** (1 min): señale una línea — stock, demanda con flecha de tendencia, Cuándo pedir y cantidad sugerida editable.
4. **Cambie los días de un producto** (1 min): salga del campo y muestre el ✓ verde. *"Usted pone los días, el consumo pone las cantidades."*
5. **Muestre una orden** (1 min): estados, total, respuesta del proveedor y botón de enviar. *"Y cuando llega, viaja sola a Entradas."*

Cierre: *"¿Le armo una prueba con 10 de sus productos para que lo vea con sus números?"*

---

## Lo que NO se promete

- El sistema no compra solo ni envía pedidos sin aprobación.
- No sugiere productos sin historia de consumo (lo dice, no inventa).
- Los precios dependen de las cotizaciones que el cliente registre; sin cotizaciones, sugiere cantidad pero no proveedor ni valor.
- La pantalla de Compras muestra la sede principal; cada sede maneja sus propias alertas.
- No hay resúmenes programados todavía (el cliente los pedirá): existen solo avisos por novedad. No prometer fechas.
