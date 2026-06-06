# Planeacion de Compras y Cotizaciones

Fecha: 2026-06-05

## Contexto

TUC TUC es una plataforma web que comparte tablas comunes para diferentes unidades de negocio, como restaurantes y tiendas. Solo se crean tablas especificas para una unidad cuando la necesidad lo justifica.

La plataforma ya cuenta con tablas base para terceros, movimientos de inventario y movimientos contables. La planeacion de compras debe apoyarse en esas tablas existentes y evitar duplicar conceptos que ya estan resueltos por el modelo actual.

## Principios del Modelo

### Terceros

Todos los actores del sistema pertenecen a la tabla `terceros`: negocios, personas, empleados, clientes, proveedores y otros roles.

No se requiere marcar adicionalmente a un tercero como proveedor. Un tercero se entiende como proveedor cuando aparece asociado a una transaccion de compra de mercancia o a una cotizacion de compra de un item.

### Movimientos de Inventario

Los movimientos de inventario deben mantenerse bajo la filosofia de una sola tabla de movimientos, similar al modelo usado en Administrator con `REC_PRO`.

En esa tabla unica se registran ventas, compras, ajustes, entradas, salidas y otros movimientos. El significado del movimiento lo determina su tipo, documento o naturaleza.

El kardex de un item se obtiene filtrando esa tabla por el item especifico y ordenando sus movimientos.

### Movimientos Contables

La contabilidad tambien sigue la filosofia de una sola tabla de movimientos contables, similar al modelo usado en Administrator con `REG_CTAS`.

No se plantea crear una estructura contable paralela para compras. Las compras deben alimentar o relacionarse con los movimientos contables existentes segun las reglas del sistema.

## Reposicion de Inventario

La compra se entiende principalmente como una reposicion de inventario.

Existen dos lecturas principales para decidir que debe comprarse:

1. Reposicion por stock minimo y maximo.
2. Reposicion inteligente por rotacion.

### Reposicion por Minimo y Maximo

Cada item puede tener:

- stock actual
- stock minimo
- stock maximo

Cuando el stock actual llega al minimo o queda por debajo del minimo, el sistema puede sugerir compra.

La cantidad sugerida seria:

```text
cantidad sugerida = stock maximo - stock actual
```

Esta regla es simple y necesaria, especialmente para items donde el usuario ya conoce niveles ideales de inventario.

### Reposicion por Rotacion

La reposicion por rotacion analiza el consumo o venta promedio del item para estimar si esta proximo a agotarse.

Una lectura basica seria:

```text
dias para agotarse = stock actual / consumo promedio diario
```

Esta opcion permite sugerir compras antes de llegar al stock minimo, especialmente en items de alta rotacion.

El algoritmo podria considerar:

- rotacion historica
- stock actual
- tiempos de entrega conocidos
- margen de seguridad
- relevancia del item

Al inicio, como la plataforma no cuenta con negocios reales activos ni historico suficiente de compras, esta inteligencia se ira alimentando con el uso futuro.

## Cotizaciones de Compras

Se propone crear una sola tabla:

```text
cotizaciones_compras
```

Cada registro representa una oferta puntual de compra para un item, hecha por un tercero.

No se plantea usar encabezado y detalle. Si una cotizacion del proveedor incluye varios items, cada item queda como una fila independiente, compartiendo el mismo numero de cotizacion si aplica.

### Campos Conceptuales

La tabla `cotizaciones_compras` deberia incluir, como minimo:

- `id`
- `numero_cotizacion`
- `tercero_id`
- `item_id`
- `fecha_cotizacion`
- `fecha_vencimiento`
- `descripcion_presentacion`
- `unidades_item`
- `precio`
- `origen`
- `validada_proveedor`
- `observaciones`
- `created_at`
- `updated_at`

Los nombres definitivos deben ajustarse a las convenciones reales del proyecto TUC TUC.

### Numero de Cotizacion

El campo `numero_cotizacion` funciona de manera similar al numero de factura en compras.

Si un proveedor entrega una cotizacion con varios items, todos esos registros pueden compartir:

- `tercero_id`
- `numero_cotizacion`
- `fecha_cotizacion`
- `fecha_vencimiento`

Esto permite agrupar lineas sin necesidad de crear una tabla adicional de encabezado.

### Vigencia

Toda cotizacion debe tener una fecha de cotizacion y una fecha de vencimiento.

Regla propuesta:

- Si el usuario no define vencimiento, la fecha de vencimiento sera `fecha_cotizacion + 180 dias`.
- Si el usuario define una fecha de vencimiento especifica, se guarda esa fecha.
- Por defecto, ninguna cotizacion deberia quedar sin vencimiento.

No se plantea guardar al mismo tiempo dias de vigencia y fecha de vencimiento, para evitar redundancia.

### Presentacion y Cantidad

Una cotizacion puede tener una descripcion de presentacion y una cantidad real de unidades del item.

Ejemplos:

```text
descripcion_presentacion = "Unidad"
unidades_item = 1
precio = 2000
```

```text
descripcion_presentacion = "Caja x 12"
unidades_item = 12
precio = 21600
```

```text
descripcion_presentacion = "Promo 2 cajas x 12"
unidades_item = 24
precio = 40000
```

No se requiere un campo separado de cantidad minima de presentaciones. Si la condicion comercial exige dos cajas, el usuario registra directamente la cantidad total de unidades del item y la descripcion correspondiente.

El precio unitario puede calcularse como:

```text
precio unitario = precio / unidades_item
```

Este valor puede calcularse en consultas o en interfaz; no necesariamente debe guardarse como dato redundante.

### Origen de la Cotizacion

Una cotizacion puede originarse de diferentes formas:

- registro manual de una cotizacion del proveedor
- actualizacion basada en una compra real
- importacion futura

Una compra real puede alimentar el historico de precios y eventualmente refrescar una cotizacion, pero debe conservarse la posibilidad de distinguir si el dato fue validado directamente por proveedor o simplemente proviene de una compra realizada.

## Seleccion de Proveedor

Un item puede tener varios terceros/proveedores posibles.

Un mismo tercero tambien puede tener varias cotizaciones para el mismo item, por ejemplo por diferentes presentaciones, cantidades o condiciones comerciales.

La mejor opcion no necesariamente es siempre el menor precio absoluto. El sistema puede comparar:

- precio unitario calculado
- cantidad ofrecida
- presentacion
- vigencia de la cotizacion
- origen del dato
- validacion del proveedor
- compras historicas
- disponibilidad futura, si se llega a registrar

La primera etapa no debe comprar automaticamente. Debe sugerir compras y permitir que el usuario revise, cambie proveedor, ajuste cantidades y apruebe.

## Flujo General Propuesto

1. Un movimiento de inventario modifica existencias.
2. El sistema revisa stock minimo, stock maximo y eventualmente rotacion.
3. Si corresponde, se genera una sugerencia de compra.
4. Para cada item sugerido, se buscan cotizaciones vigentes en `cotizaciones_compras`.
5. Se comparan opciones por proveedor, presentacion, cantidad y precio unitario.
6. El usuario decide si acepta, ajusta o descarta la sugerencia.
7. La compra real alimenta movimientos de inventario, contabilidad e historico de precios/cotizaciones segun corresponda.

## Ejecucion del Modulo de Compras Inteligente

Cuando el modulo de compras se ejecuta, debe partir de los saldos reales de inventario.

El proceso conceptual es:

1. Revisar el saldo actual de cada item.
2. Comparar ese saldo contra sus condiciones de stock minimo y stock maximo.
3. Evaluar tambien la rotacion del item, para detectar productos que pueden agotarse pronto aunque aun no hayan llegado al minimo.
4. Determinar que items requieren compra o alerta.
5. Para cada item requerido, buscar cotizaciones vigentes en `cotizaciones_compras`.
6. Si no existen cotizaciones vigentes, el item debe aparecer como pendiente de compra sin proveedor sugerido y con alerta de falta de cotizaciones.
7. Si existen cotizaciones, comparar las opciones disponibles.
8. Agrupar las sugerencias por tercero/proveedor.
9. Calcular el valor estimado de compra por proveedor.
10. Presentar al usuario una propuesta de orden de compra.

La salida del modulo no debe ser inicialmente una compra registrada, sino una propuesta de compra u orden de compra sugerida.

Ejemplo:

```text
Proveedor A
- Item 20
- Item 35
- Item 40
Total estimado: ...

Proveedor B
- Item 12
- Item 18
Total estimado: ...
```

El usuario revisa la propuesta y decide si el pedido se realiza.

## Orden de Compra y Recepcion

Cuando el usuario aprueba una propuesta, esa propuesta pasa a ser una orden de compra o pedido al proveedor.

Al llegar la factura real del proveedor, pueden ocurrir dos escenarios:

### La factura coincide con la orden

Si los items, cantidades y valores coinciden con lo que ya estaba aprobado en la orden de compra, el sistema deberia permitir confirmar la compra con una accion simple.

En este caso, el usuario solo informaria datos finales como:

- numero de factura del proveedor
- fecha de factura, si aplica
- fecha de recepcion, si aplica

El sistema podria generar automaticamente:

- movimiento de inventario de compra
- movimiento contable correspondiente
- actualizacion de saldos
- actualizacion o refresco de referencias de precio/cotizacion

La idea es que, si la factura llego tal cual se habia pedido, el usuario no tenga que digitar nuevamente todos los items.

### La factura no coincide con la orden

Si hay diferencias en cantidades, precios, items o condiciones, el sistema debe permitir ajustar antes de registrar la compra definitiva.

Esas diferencias tambien pueden servir para actualizar el historico real de compras y las cotizaciones derivadas de compras.

La recepcion con diferencias deberia funcionar como una conciliacion contra la orden original:

- Chulear o confirmar los items que llegaron tal cual.
- Ajustar cantidades cuando el proveedor entrega mas o menos de lo pedido.
- Ajustar precios cuando la factura llega con un valor distinto al cotizado o pedido.
- Quitar items que finalmente no llegaron.
- Agregar items que llegaron en la factura pero no estaban en la orden original.
- Recalcular totales antes de registrar la compra definitiva.

Solo despues de esa conciliacion se deben generar los movimientos definitivos de inventario y contabilidad.

## Items sin Cotizacion

Un item puede requerir compra por minimo, maximo o rotacion y no tener cotizaciones vigentes.

En ese caso el modulo debe mostrarlo claramente como:

```text
Item requiere compra, pero no tiene cotizaciones vigentes.
```

Esto permite que el usuario sepa que debe solicitar o registrar cotizaciones antes de que el sistema pueda sugerir proveedor y valor de compra.

## Pendientes de Verificacion Tecnica

Antes de implementar se debe confirmar en el codigo y base de datos de TUC TUC:

- Nombre real de la tabla de items/productos.
- Nombre real de la tabla unica de movimientos de inventario.
- Nombre real de la tabla unica de movimientos contables.
- Convenciones actuales para crear tablas nuevas.
- Convenciones de nombres de columnas, indices y llaves foraneas.
- Si existe ya algun flujo parcial de compras o inventario que deba integrarse.

## Verificacion Tecnica Inicial

Revision realizada sobre el codigo de TUC TUC el 2026-06-06.

### Tablas Reales Confirmadas

- Items/productos: `productos`.
- Saldos de inventario: `saldos_inventario`.
- Movimientos de inventario: `movimientos_inventario`.
- Comprobantes contables: `comprobantes_contables`.
- Movimientos contables: `movimientos_contables`.
- Terceros: `terceros` ya se usa como tabla comun para personas, negocios, clientes, administradores e invitados.

### Flujo Actual de Entrada de Mercancia

El blueprint `inventarios` ya tiene una ruta para registrar entradas:

```text
POST /api/inventario/<negocio_id>/entrada
```

Esa ruta recibe lineas con producto, cantidad y costo unitario. Por defecto usa `motivo = compra`.

Internamente llama a `_aplicar_tarjeta`, que termina registrando movimientos en `movimientos_inventario` y actualizando `saldos_inventario`.

Esto significa que una compra ya existe tecnicamente como una entrada de mercancia al inventario. El modulo de compras inteligente no debe duplicar ese movimiento, sino apoyarse en esta entrada o en una funcion equivalente cuando la orden/factura quede confirmada.

### Integracion Contable Existente

La entrada de mercancia ya intenta ejecutar un asiento automatico de tipo `COMPRA` cuando hay valor de compra.

Adicionalmente, el modulo contable agrega a `movimientos_inventario` los campos:

- `tipo_documento`
- `numero_documento`

Estos campos pueden servir mas adelante para relacionar movimientos de inventario con facturas, ordenes de compra u otros documentos, aunque el flujo actual de entrada no los esta explotando completamente.

### Interfaz Actual

Existe una pantalla administrativa:

```text
/admin/inventario/<negocio_id>
```

Plantilla:

```text
inventario_admin.html
```

La pantalla actual tiene pestañas para:

- Productos
- Entradas
- Produccion
- Stock
- Kardex

La pestaña `Entradas` ya permite registrar entradas de mercancia con motivo `compra`, `ajuste`, `devolucion` o `inicial`.

Tambien existe una seccion de inventario dentro de `tienda_admin.html`. Esa pantalla arma una entrada de inventario mas completa, con:

- tipo de documento
- numero de documento
- fecha
- motivo
- notas
- IVA
- lineas de producto, cantidad y valor unitario

Sin embargo, en la revision inicial no se encontro una ruta activa en `tiendas.py` para:

```text
/api/tienda/<slug>/inventario/entrada
```

La ruta activa encontrada para registrar entradas es la generica:

```text
/api/inventario/<negocio_id>/entrada
```

Esa ruta no consume completamente los campos enriquecidos que envia la pantalla de tienda, como `tipo_documento`, `numero_documento`, `fecha_documento` e `iva`.

Antes de construir compras inteligentes conviene consolidar este flujo para que una compra registrada desde interfaz pueda conservar correctamente su documento de proveedor.

### Faltantes Detectados Para Compras Inteligentes

No se encontraron campos claros de stock minimo y stock maximo en `productos` ni en `saldos_inventario`.

Por eso, para que el modulo sugiera compras por minimo/maximo, se debe agregar una forma de guardar parametros de reposicion por producto y negocio.

Opciones tecnicas posibles:

- Agregar columnas a `productos`, si el parametro aplica igual para todo el negocio y no depende de bodega.
- Agregar columnas a `saldos_inventario`, si el minimo/maximo debe depender de producto, negocio y bodega.
- Crear una tabla separada de parametros de reposicion, si se espera una logica mas amplia en el futuro.

Por la estructura actual, la opcion mas coherente para una primera etapa parece ser agregar `stock_minimo` y `stock_maximo` a `saldos_inventario`, porque los saldos ya estan separados por `negocio_id`, `producto_id` y `bodega`.

## Decision Actual

La decision de planeacion, hasta este punto, es crear una sola tabla `cotizaciones_compras`, donde cada fila representa una cotizacion puntual de un tercero para un item, con cantidad, presentacion, precio y vigencia.

No se creara una tabla separada de encabezado de cotizacion en esta etapa.

Para la primera version de compras inteligentes, la deteccion de items a comprar se hara por rotacion y agotamiento proyectado, no por stock minimo y maximo.

Los campos de stock minimo y stock maximo pueden quedar como una mejora posterior, pero no son requisito para iniciar el algoritmo.

## Implementacion Inicial de Entrada de Compra

Fecha: 2026-06-06

Se inicio la consolidacion de la entrada de mercancia para que pueda conservar datos basicos del documento de proveedor.

Cambios realizados:

- La entrada generica de inventario ahora acepta datos enriquecidos del documento.
- Se agregaron columnas a `movimientos_inventario` para guardar:
  - `tipo_documento`
  - `documento_numero`
  - `documento_fecha`
  - `proveedor_id`
  - `proveedor_nombre`
  - `iva_total`
  - `documento_total`
- Se centralizo el registro de entrada en una funcion comun para evitar duplicar logica.
- La ruta generica `POST /api/inventario/<negocio_id>/entrada` usa esa funcion comun.
- Se agregaron rutas por tienda para inventario usando `slug`:
  - `POST /api/tienda/<slug>/inventario/entrada`
  - `GET /api/tienda/<slug>/inventario/stock`
  - `GET /api/tienda/<slug>/inventario/kardex`
- La pantalla `inventario_admin.html` permite capturar tipo de documento, numero, fecha, proveedor textual e IVA.
- El kardex de inventario devuelve y muestra documento/proveedor cuando existen.

Esta etapa no crea todavia `cotizaciones_compras`. Primero deja mas firme la base de compra real como entrada de mercancia documentada.

## Algoritmo de Compras por Rotacion

Fecha: 2026-06-06

Decision: la primera version del modulo inteligente no dependera de stock minimo y stock maximo. La sugerencia de compra se calculara por rotacion real, usando los movimientos de inventario.

### Base de Datos del Calculo

La rotacion debe calcularse desde:

```text
movimientos_inventario
```

Filtrando principalmente:

```text
tipo = 'salida'
motivo = 'venta'
```

Estas salidas ya son generadas por tiendas y restaurantes cuando se registran pedidos. Si el producto vendido tiene tarjeta estandar, el movimiento queda aplicado sobre los componentes reales consumidos. Eso permite calcular rotacion sobre el item que realmente se agota, no solo sobre el plato o producto final vendido.

El saldo actual debe salir de:

```text
saldos_inventario
```

La identificacion del item debe salir de:

```text
productos
```

### Concepto Principal

El sistema debe responder esta pregunta por cada item:

```text
Con el ritmo actual de consumo, cuantos dias le quedan de existencia?
```

Formula base:

```text
dias_para_agotarse = stock_actual / consumo_promedio_diario
```

Si el consumo promedio diario es cero, el item no se sugiere para compra por rotacion.

### Ventanas de Analisis

Para evitar que una venta aislada o un dia raro distorsione el resultado, el algoritmo debe mirar varias ventanas:

- ultimos 7 dias
- ultimos 30 dias
- ultimos 90 dias

Calculos:

```text
promedio_7  = consumo_7_dias  / 7
promedio_30 = consumo_30_dias / 30
promedio_90 = consumo_90_dias / 90
```

La demanda diaria estimada puede iniciar asi:

```text
demanda_diaria = max(promedio_7, promedio_30)
```

Regla:

- Si hay poca historia, se usa lo que exista, pero se marca la sugerencia como baja confianza.
- Si `promedio_7` sube mucho frente a `promedio_30`, se interpreta como aceleracion reciente.
- Si `promedio_7` baja mucho frente a `promedio_30`, no se debe bajar la compra automaticamente sin advertencia; puede ser un bajon temporal.

En una version posterior se puede usar una formula ponderada:

```text
demanda_diaria = promedio_7 * 0.50 + promedio_30 * 0.35 + promedio_90 * 0.15
```

Pero para la primera version es mas clara y prudente la regla `max(promedio_7, promedio_30)`.

### Estados del Item

Cada item evaluado debe quedar en uno de estos estados:

#### Sin Rotacion

Condicion:

```text
demanda_diaria <= 0
```

Accion:

No sugerir compra por rotacion.

#### Agotado Real

Condicion:

```text
stock_actual <= 0
demanda_diaria > 0
```

Accion:

Marcar como agotado y sugerir compra urgente.

#### Agotado Funcional

Condicion:

```text
stock_actual > 0
dias_para_agotarse <= dias_alerta_agotamiento
```

Valor inicial recomendado:

```text
dias_alerta_agotamiento = 2
```

Interpretacion:

Aunque todavia hay stock, por rotacion se considera practicamente agotado.

#### Comprar Pronto

Condicion:

```text
dias_para_agotarse <= dias_cobertura_minima
```

Valor inicial recomendado:

```text
dias_cobertura_minima = 7
```

Interpretacion:

El item no esta agotado, pero debe entrar a una propuesta de compra.

#### Sano

Condicion:

```text
dias_para_agotarse > dias_cobertura_minima
```

Accion:

No sugerir compra.

### Cantidad Sugerida

La compra sugerida no debe comprar apenas hasta cero. Debe comprar hasta una cobertura objetivo.

Valor inicial recomendado:

```text
dias_cobertura_objetivo = 15
```

Formula:

```text
cantidad_sugerida = demanda_diaria * dias_cobertura_objetivo - stock_actual
```

Si el resultado es menor o igual a cero, no se sugiere compra.

La cantidad final debe redondearse hacia arriba:

```text
cantidad_sugerida = techo(cantidad_sugerida)
```

Cuando existan cotizaciones con presentaciones, la cantidad sugerida debe ajustarse a la presentacion elegida. Ejemplo: si se necesitan 20 unidades y la mejor cotizacion es caja x 12, la compra sugerida puede ser 24 unidades.

### Confianza de la Sugerencia

Cada sugerencia debe traer un nivel de confianza.

Alta:

- hay consumo en varios dias
- existe historia suficiente en 30 dias
- la demanda no depende de una sola venta aislada

Media:

- hay ventas recientes, pero poca historia
- hay diferencia importante entre 7 y 30 dias

Baja:

- solo hay uno o dos movimientos
- el producto es nuevo
- el consumo aparece concentrado en un solo dia

La confianza no bloquea la sugerencia, pero debe mostrarse al usuario para que revise antes de aprobar.

### Relacion con Cotizaciones

Despues de detectar items a comprar, el modulo debe buscar cotizaciones vigentes en:

```text
cotizaciones_compras
```

Si no hay cotizacion vigente:

```text
estado_cotizacion = sin_cotizacion
```

El item debe aparecer como necesario, pero sin proveedor sugerido.

Si hay cotizaciones:

1. Calcular precio unitario:

```text
precio_unitario = precio / unidades_item
```

2. Filtrar cotizaciones vencidas.
3. Ordenar por mejor precio unitario.
4. Ajustar cantidad sugerida a la presentacion seleccionada.
5. Agrupar por proveedor.

### Salida Esperada del Algoritmo

La salida debe ser una propuesta, no una compra definitiva.

Por item:

```text
producto_id
producto_nombre
stock_actual
demanda_diaria
dias_para_agotarse
estado_rotacion
cantidad_sugerida
confianza
cotizacion_sugerida_id
proveedor_id
proveedor_nombre
precio_unitario_estimado
valor_estimado
alertas
```

Por proveedor:

```text
proveedor_id
proveedor_nombre
items
total_estimado
```

### Reglas de Prudencia

- El algoritmo no debe registrar compras automaticamente.
- El algoritmo no debe ocultar items sin cotizacion.
- El algoritmo debe diferenciar agotado real de agotado funcional.
- El algoritmo debe mostrar baja confianza cuando hay poca historia.
- El algoritmo debe permitir que el usuario cambie proveedor, cantidad o descarte una sugerencia.
- La compra definitiva solo nace cuando el usuario aprueba la propuesta y luego confirma factura/recepcion.

## Implementacion Inicial de Compras por Rotacion

Fecha: 2026-06-06

Se inicio la implementacion del modulo de compras inteligentes por rotacion.

Cambios realizados:

- Se creo el blueprint `compras`.
- Se registro el blueprint en la aplicacion principal.
- Se creo la tabla `cotizaciones_compras` desde el modulo de compras.
- Se creo la ruta administrativa:

```text
/admin/compras/<negocio_id>
```

- Se creo la ruta de calculo:

```text
/api/compras/<negocio_id>/rotacion
```

- La ruta calcula consumo de 7, 30 y 90 dias desde `movimientos_inventario`.
- La ruta usa `tipo = 'salida'` y `motivo = 'venta'`.
- El saldo actual sale de `saldos_inventario`.
- La demanda diaria inicial se calcula con:

```text
demanda_diaria = max(promedio_7, promedio_30)
```

- Se clasifican items en:
  - `sin_rotacion`
  - `agotado_real`
  - `agotado_funcional`
  - `comprar_pronto`
  - `sano`
- Se calcula cantidad sugerida con cobertura objetivo.
- Si existe cotizacion vigente, se ajusta la cantidad sugerida a la presentacion de compra y se agrupa por proveedor.
- Se creo la pantalla `compras_admin.html` para revisar la propuesta.
- Se agrego acceso a compras desde la pantalla de inventario.

Pendiente de prueba funcional:

- Probar contra una base real con productos, saldos y movimientos.
- Registrar cotizaciones de prueba para validar agrupacion por proveedor.
- Ajustar la interfaz despues de ver resultados reales.

## Implementacion Inicial de Cotizaciones

Fecha: 2026-06-06

Se implemento un CRUD basico de cotizaciones para alimentar la propuesta de compras por rotacion.

Rutas creadas:

```text
GET    /api/compras/<negocio_id>/cotizaciones
POST   /api/compras/<negocio_id>/cotizaciones
POST   /api/compras/cotizaciones/<cotizacion_id>
DELETE /api/compras/cotizaciones/<cotizacion_id>
```

Reglas iniciales:

- Toda cotizacion pertenece a un `negocio_id`.
- Toda cotizacion apunta a un producto de `productos`.
- El proveedor se maneja como tercero.
- Si el usuario escribe un proveedor que no existe, se crea en `terceros` solo con nombre.
- Si no se informa vencimiento, se toma `fecha_cotizacion + 180 dias`.
- El precio unitario se calcula como `precio / unidades_item`.

La pantalla `compras_admin.html` permite crear cotizaciones sencillas con:

- producto
- proveedor
- numero de cotizacion
- fecha de vencimiento
- presentacion
- unidades del item
- precio
- observaciones

Al guardar o eliminar una cotizacion, la propuesta de compras se recalcula para que las sugerencias por proveedor queden actualizadas.
