# Manual de Usuario — Tienda TUC TUC

**Módulo:** Tienda (cliente y dueño)
**Versión:** 1.1
**Última actualización:** 2026-03-14
**Audiencia:** Dueños de tienda, clientes que visitan tiendas en TUC TUC

---

## Para clientes que visitan una tienda

### Navegar el catálogo

Cuando visitas la página pública de una tienda TUC TUC (por ejemplo `https://tuc-tuc.onrender.com/t/nombre-tienda`), verás el catálogo de productos organizados en tarjetas.

#### Indicador de fotos adicionales (📷 +N)

Cuando un producto tiene **más de una foto**, aparece un pequeño indicador en la esquina inferior derecha de la imagen:

```
┌───────────────────┐
│                   │
│   [foto del       │
│    producto]      │
│                   │
│              📷+3 │
└───────────────────┘
```

- **📷 +3** significa que el producto tiene 3 fotos adicionales además de la principal
- Si no hay ningún indicador, el producto solo tiene la foto principal

**¿Para qué sirve?** Te ahorra tener que hacer clic en cada producto para saber si hay más fotos. Si el indicador dice `+3`, vale la pena entrar a ver el producto desde varios ángulos.

### Ver el detalle de un producto

Haz clic sobre la tarjeta del producto para abrir el modal de detalle. Aquí puedes:

- Ver el precio, descripción, y variantes disponibles (tallas, colores, etc.)
- **Navegar entre todas las fotos** del producto (si tiene varias)
- Agregar al carrito

#### Modo oscuro

Si la tienda está configurada en modo oscuro, el modal de detalle del producto también usa fondo oscuro para no romper la experiencia visual. Las imágenes se muestran sobre fondo gris oscuro (en lugar del blanco habitual).

### Agregar al carrito y hacer un pedido

1. Selecciona la variante del producto que deseas (si el producto tiene tallas, colores, etc.)
2. Haz clic en **"Agregar al carrito"**
3. Cuando termines de seleccionar productos, haz clic en el carrito (esquina de la pantalla)
4. Completa tus datos de contacto y confirma el pedido
5. El dueño de la tienda recibirá una notificación con tu pedido

---

## Para dueños de tienda

### Panel de administración

Accede a tu panel desde `https://tuc-tuc.onrender.com/tienda/admin`. El panel tiene las siguientes pestañas:

| Pestaña | ¿Para qué? |
|---|---|
| 📦 Catálogo | Agregar, editar y eliminar productos |
| 🛒 Pedidos | Ver y gestionar pedidos recibidos |
| 📋 Inventario | Control de stock |
| 🎨 Personalizar | Imagen, colores, nombre, descripción de tu tienda |
| 🔑 Acceso | Cambiar contraseña, gestionar acceso |
| 📍 Ubicación | Dirección y mapa de tu tienda |
| 🖥️ Soporte | Obtener ayuda técnica remota |

### Pestaña Soporte — Asistencia Remota

Desde la pestaña **🖥️ Soporte** puedes solicitar asistencia técnica remota. Un técnico TUC TUC puede conectarse a tu pantalla y ayudarte directamente.

**Cómo funciona:**
1. Descarga el programa `AsistenciaTucTuc.exe` usando el botón de descarga
2. Ejecútalo — aparece una ventana con un código como `847-293`
3. Comparte ese código con el técnico que te está atendiendo
4. El técnico ve tu pantalla y puede ayudarte en tiempo real

Para instrucciones detalladas, ver el manual completo de Asistencia Remota.

### Agregar fotos a un producto

Para que tus clientes vean el indicador de fotos adicionales en las tarjetas:

1. Ve a la pestaña **📦 Catálogo**
2. Haz clic en el producto que deseas editar
3. En la sección de imágenes, sube fotos adicionales
4. Las fotos adicionales aparecen en el modal de detalle cuando el cliente hace clic en el producto
5. El indicador `📷 +N` aparece automáticamente en la tarjeta del catálogo

**Recomendación:** Sube al menos 2-3 fotos por producto — desde distintos ángulos, con detalle del material o etiqueta, y en uso. Los clientes que ven más fotos tienen más confianza para comprar.

### Modo oscuro de la tienda

Puedes configurar tu tienda en modo oscuro desde la pestaña **🎨 Personalizar**. El modo oscuro aplica a toda la experiencia del cliente:
- Fondo de página
- Tarjetas de productos
- Modal de detalle de producto (incluyendo el fondo de las imágenes)
- Navegación y botones

Si tus productos tienen fotos con fondos blancos, considera si el modo oscuro va bien con tu catálogo antes de activarlo.
