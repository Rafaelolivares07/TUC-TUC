# Manual de Usuario — Restaurante TUC TUC
**Módulo:** Restaurante (Menú del Día)
**Versión:** 1.0
**Última actualización:** 2026-03-16
**Audiencia:** Dueños de restaurante, meseros, clientes

---

## Para clientes

### Ver el menú del día

Cuando el restaurante comparte su enlace (por WhatsApp, Facebook o cualquier canal), abrís una página como esta:

```
tuc-tuc.onrender.com/r/nombre-restaurante
```

Allí ves el menú del día completo: plato principal, sopa, bebida, precio. No necesitás llamar ni preguntar — está actualizado en tiempo real por la cocina.

### Pedir desde la mesa

Cada mesa tiene un código QR. Al escanearlo desde el celular ves el menú del restaurante. Dependiendo de cómo lo tenga configurado el dueño:

- **Con pedidos habilitados:** seleccionás lo que querés, confirmás, y el pedido llega directamente a la cocina.
- **Solo carta:** ves el menú completo con fotos y precios, pero el pedido lo toma el mesero. (El dueño elige este modo si prefiere que el mesero mantenga el contacto con el cliente.)

No necesitás registrarte ni instalar nada.

---

## Para el dueño del restaurante

### Panel de administración

Accedé a tu panel desde el enlace que te compartieron al crear la cuenta, o desde:

```
tuc-tuc.onrender.com/mi-restaurante/<tu-slug>
```

El panel tiene estas secciones:

| Sección | ¿Para qué? |
|---|---|
| 🍽️ Menú del día | Publicar y actualizar las opciones del día |
| 📋 Pedidos | Ver pedidos activos de las mesas |
| 🧾 Cuentas | Cobrar mesas |
| 📊 Ventas | Resumen de ventas del día |
| 🎨 Personalizar | Imagen, colores y nombre del restaurante |

### Actualizar el menú del día

1. Entrá al panel → sección **Menú del día**
2. Para cada opción (sopa, plato, bebida, etc.):
   - Escribí el nombre del plato
   - Agregá una foto si querés
   - Marcá si está disponible o agotado
3. Guardá — los cambios se ven de inmediato en la página pública

**Tip:** Actualizá el menú antes de las 11:00 AM para que tus clientes puedan verlo antes de salir.

### Marcar un plato como agotado

En el panel de Menú del día, cada opción tiene un botón de **"Agotar"**. Al presionarlo, la opción aparece como no disponible en la página del cliente.

Útil cuando se acaba la sopa o el plato especial antes de terminar el servicio.

### Ver y gestionar pedidos

Desde la sección **Pedidos** ves todos los pedidos activos agrupados por mesa. Cada pedido muestra:
- Número de mesa
- Productos pedidos
- Estado: recibido / en cocina / listo

Podés marcar cada pedido como "Listo" cuando la cocina lo prepara.

### Configurar modo de mesas — solo carta o con pedidos

En el panel de administración, sección **Mesas**, encontrás el toggle **"Solo carta en QR de mesas"**:

- **Desactivado (predeterminado):** el cliente puede pedir directamente desde el QR. El pedido llega solo a cocina — el mesero solo entrega.
- **Activado:** el cliente ve el menú completo (fotos, precios, categorías) pero no puede hacer el pedido. El mesero toma la orden en persona.

> **Este toggle solo afecta el QR de mesas.** El enlace público del restaurante (para domicilios y pedidos desde fuera) siempre permite pedir, sin importar esta configuración.

### Cobrar una mesa

1. Ve a **Cuentas**
2. Seleccioná la mesa a cobrar
3. El sistema muestra el total de todos los pedidos de esa mesa
4. Confirmá el cobro — queda registrado en el historial de ventas

### Compartir el menú del día

Desde el panel, podés compartir el menú del día como enlace directo. El enlace incluye una **preview automática** para WhatsApp y Facebook con la imagen del restaurante y el nombre del plato principal.

También podés compartir una opción individual:
```
tuc-tuc.onrender.com/promo/restaurante/<slug>/<opcion_id>
```

---

## Para el mesero

### Vista del mesero

El mesero accede desde:
```
tuc-tuc.onrender.com/r/<slug>/mesero
```

Aquí puede:
- Ver el menú del día disponible
- Registrar pedidos por mesa (tocando la mesa en el mapa o ingresando el nombre)
- Ver cuáles pedidos ya están listos para llevar

### Vista de cocina

La cocina accede desde:
```
tuc-tuc.onrender.com/r/<slug>/cocina
```

Ve todos los pedidos en tiempo real, ordenados por hora de llegada. Al preparar cada plato, lo marca como "Listo" y el mesero ve la notificación.

---

## Preguntas frecuentes

**¿Cuántas opciones puedo tener en el menú del día?**
Sin límite. Podés tener sopa, plato principal, plato vegano, bebida, postre — todo en el mismo menú del día.

**¿Los clientes tienen que descargarse una app?**
No. La página funciona directamente en el navegador del celular.

**¿Puedo usar TUC TUC solo para mostrar el menú, sin pedidos en mesa?**
Sí. La página pública del menú funciona sin necesidad de activar los pedidos en mesa.

**¿Cómo saben mis clientes cuál es el enlace?**
Compartilo por WhatsApp, ponelo en tu bio de Instagram, imprimilo en un afiche en la puerta, o ponlo como estado de WhatsApp cada mañana.
