# Manual de Desarrollo — Restaurante TUC TUC
**Módulo:** Restaurante (Menú del Día)
**Versión:** 1.0
**Última actualización:** 2026-03-16
**Audiencia:** Rafael + Claude (desarrollo y mantenimiento)

---

## 1. Arquitectura general

El módulo restaurante tiene cuatro vistas diferenciadas:

| Vista | Ruta | Quién la usa |
|---|---|---|
| Página pública | `/r/<slug>` | Clientes — ver menú del día |
| Pedido en mesa | `/r/<slug>/<mesa_nombre>` | Clientes en mesa — pedir |
| Panel dueño | `/mi-restaurante/<slug>` | Dueño — administrar |
| Admin general | `/admin/restaurante/<slug>` | Rafael — gestión completa |
| Mesero | `/r/<slug>/mesero` | Mesero — ver menú y pedidos |
| Cocina | `/r/<slug>/cocina` | Cocina — ver y marcar pedidos |

---

## 2. Base de datos

### Tabla principal: `restaurantes`
```
id, slug, nombre, descripcion, tema, imagen_header,
pin_habilitado, dias_pagados, fecha_vence,
created_at, updated_at
```

### Opciones del menú: `opciones_restaurante`
```
id, restaurante_id, nombre, descripcion, precio,
imagen_url, disponible, orden, created_at
```

### Pedidos: `pedidos_restaurante`
```
id, restaurante_id, mesa_id, cliente_id,
estado (recibido/en_cocina/listo/entregado),
total, created_at
```

### Líneas de pedido: `pedido_items_restaurante`
```
id, pedido_id, opcion_id, cantidad, precio_unitario
```

### Mesas: `mesas_restaurante`
```
id, restaurante_id, nombre, qr_token
```

### Clientes registrados: `clientes_restaurante`
```
id, restaurante_id, tercero_id (→ terceros),
nombre, telefono, created_at
```

### Pagos: `pagos_restaurante`
```
id, restaurante_id, mesa_id, total, created_at
```

---

## 3. Flujo de un pedido

```
Cliente escanea QR de mesa
    ↓
GET /r/<slug>/<mesa_nombre>
    ↓ muestra menú del día + formulario de pedido
POST /api/restaurante/<slug>/pedido
    ↓ crea pedido_restaurante + items
    ↓ estado = 'recibido'
Cocina ve pedido en /r/<slug>/cocina
    ↓
POST /api/restaurante/<slug>/pedido/<id>/listo
    ↓ estado = 'listo'
Mesero entrega pedido
    ↓
POST /api/restaurante/<slug>/pedido/<id>/entregado
    ↓ estado = 'entregado'
Dueño cobra la mesa
    ↓
POST /api/restaurante/<slug>/cobrar/<mesa_id>
    ↓ crea registro en pagos_restaurante
```

---

## 4. APIs principales

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/restaurante/<slug>/opciones` | Lista menú del día |
| POST | `/api/restaurante/<slug>/opcion` | Crear/editar opción |
| DELETE | `/api/restaurante/<slug>/opcion/<id>` | Eliminar opción |
| POST | `/api/restaurante/<slug>/agotar/<id>` | Toggle disponible/agotado |
| POST | `/api/restaurante/<slug>/opcion/<id>/imagen` | Subir imagen |
| POST | `/api/restaurante/<slug>/imagen-header` | Imagen de portada |
| POST | `/api/restaurante/<slug>/tema` | Modo claro/oscuro |
| POST | `/api/restaurante/<slug>/pedido` | Crear pedido desde mesa |
| GET | `/api/restaurante/<slug>/pedidos` | Listar pedidos activos |
| POST | `/api/restaurante/<slug>/pedido/<id>/listo` | Marcar listo |
| POST | `/api/restaurante/<slug>/pedido/<id>/entregado` | Marcar entregado |
| GET | `/api/restaurante/<slug>/cuentas` | Cuentas abiertas por mesa |
| POST | `/api/restaurante/<slug>/cobrar/<mesa_id>` | Cobrar mesa |
| GET | `/api/restaurante/<slug>/venta-dia` | Resumen ventas del día |

---

## 5. Promo / Compartir

### Menú del día completo
```
GET /promo/restaurante/<slug>/menu
```
Página pública con preview Open Graph (og:image generada) para WhatsApp/Facebook.

### Opción individual
```
GET /promo/restaurante/<slug>/<opcion_id>
```
Página individual de una opción con su foto, nombre y precio.

### Imagen OG generada
```
GET /promo/restaurante/<slug>/<opcion_id>/imagen
```
Devuelve imagen 1200×630 con la foto del plato y blur de fondo para preview social.

---

## 6. Autenticación y acceso

- El dueño accede vía **link mágico** con token en URL (`/r/acceso/<token>`)
- No requiere usuario/contraseña — el token autentica directamente
- El PIN de caja es opcional, se activa/desactiva desde `/api/restaurante/<slug>/toggle-pin`
- El acceso admin general (`/admin/restaurante`) requiere `session['rol'] == 'Administrador'`

---

## 7. Suscripción y facturación

- `dias_pagados` INTEGER en tabla `restaurantes`
- `fecha_vence` DATE — calculada al agregar días
- Si `fecha_vence < hoy` → pedidos bloqueados (HTTP 402)
- Endpoint admin para extender: `POST /api/restaurante/<slug>/dias-pagados`

---

## 8. Tabla `terceros` — clientes del restaurante

Los clientes que piden por QR pueden quedar registrados como `terceros` si dan su nombre y teléfono. Esto permite:
- Historial de pedidos por cliente
- Registro en la base de contactos del restaurante

---

## 9. Notas técnicas

- Slug: generado automáticamente desde el nombre al crear, sin espacios, en minúsculas
- Las imágenes se suben como base64 y se guardan en la BD (columna `imagen_url` = data URI)
- Las mesas se crean automáticamente al primer pedido con ese nombre de mesa, o manualmente
- El módulo almuerzo (`/almuerzo`, `/api/almuerzo/*`) es una vista de descubrimiento que agrega restaurantes en el mapa — relacionado pero separado

---

## 10. Pendientes conocidos

- [ ] Notificación Telegram al dueño cuando llega pedido (implementado en tienda, pendiente en restaurante)
- [ ] Reporte de ventas por rango de fechas (actualmente solo muestra el día actual)
- [ ] Programa de fidelización para clientes recurrentes
- [ ] **Sin clientes reales aún** — módulo completo pero sin despliegue comercial a la fecha (2026-03-16)
