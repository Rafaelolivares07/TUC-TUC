# Inventario de Funciones — Módulo Tienda TUC TUC
**Versión de trabajo | 2026-03-16**
*(Documento vivo — se actualiza a medida que se identifican fortalezas y se afina el pitch)*

---

## 1. Catálogo de Productos

- Nombre, descripción, categoría, precio
- Foto principal + galería de fotos adicionales por producto
- Variantes con atributos configurables (talla, color, presentación, etc.)
  - Precio independiente por variante
  - Disponibilidad independiente por variante
- Código de barras por producto
- Activar / desactivar producto sin eliminarlo
- Búsqueda de productos de otras tiendas en la plataforma y "adopción" (copiar nombre y categoría)
- Navegación por categorías en la tienda pública

---

## 2. Tienda Pública del Cliente

- URL propia por tienda: `tuc-tuc.onrender.com/t/<slug>`
- Catálogo navegable sin necesidad de registro del cliente
- Filtro y navegación por categorías
- Vista de producto con galería, variantes y precio
- Botón de pedido directo desde la tienda
- Diseño responsive — funciona bien en celular

---

## 3. Compartir y Distribución ⭐ FORTALEZAS CLAVE

### 3.1 Página promo por producto
- URL individual por producto: `/promo/tienda/<slug>/<producto_id>`
- Se puede compartir por WhatsApp, Facebook, Telegram, email — cualquier canal
- **Preview automática para WhatsApp y Facebook**: imagen 1200×630 generada al vuelo con la foto del producto, nombre y precio — se ve profesional sin hacer nada
- Parámetros configurables en la URL:
  - Ocultar precio (`?precio=0`)
  - Ocultar descripción (`?desc=0`)
  - Agregar texto personalizado (`?txt=Oferta del día`)

### 3.2 Enlace con cliente preidentificado ⭐
- El enlace puede llevar **hardcodeado quién es el cliente** que va a abrirlo
- Cuando ese cliente entra, la plataforma lo reconoce como usuario pregrabado (de la base de contactos de la tienda)
- El cliente no necesita registrarse — ya está en el sistema
- Permite personalizar la experiencia: "Hola Juan, mira esta oferta"
- **Desencadena una compra trazable desde el primer clic**: se sabe quién compró, desde qué enlace, en qué momento

### 3.3 Compartir a contacto específico
- Desde el panel de la tienda, el dueño puede compartir un producto directamente a un contacto de su base
- No es un broadcast masivo — es un envío dirigido, personalizado
- El cliente recibe el link listo para pedir

### 3.4 Publicación en muro de Facebook ⭐
- Un clic publica el producto en el muro de Facebook del usuario
- La publicación incluye la preview de imagen generada automáticamente
- Clientes que ven la publicación pueden hacer clic y llegar directamente a la página de pedido
- Si el cliente ya está pregrabado en el sistema (fue importado desde contactos), es reconocido al entrar

### 3.5 Compartir en Estado de WhatsApp
- El dueño puede compartir el enlace del producto como estado de WhatsApp
- Toda su lista de contactos ve la oferta con preview de imagen
- El que quiera comprar entra al link y hace el pedido sin tener que escribir

---

## 4. Contactos y Base de Clientes

- Importar contactos desde:
  - Archivo VCF (.vcf / .vcard) — formato estándar de celulares
  - Exportación de Telegram (HTML o JSON)
  - Selección manual desde el celular (contacto por contacto)
  - Entrada manual uno a uno
- Deduplicación automática al importar
- Cada contacto queda como cliente potencial pregrabado
- Al compartir un enlace a ese contacto, el sistema lo reconoce cuando entra

---

## 5. Pedidos

- Pedidos a domicilio o recogida en caja
- Estado del pedido con seguimiento
- Notas del cliente
- Pagos mixtos: efectivo + transferencia en el mismo pedido
- Historial de pedidos por cliente

---

## 6. Punto de Venta (POS / Caja)

- Módulo de caja con PIN de seguridad
- Cajeros con acceso controlado (cada cajero tiene su PIN)
- Registro de ventas en caja con contabilidad automática
- IVA calculado automáticamente (back-calculation desde el precio final)
- Funciona desde el celular — no requiere computador ni software especial

---

## 7. Inventario

- Stock por producto y por variante
- Registro de entradas (compras, devoluciones)
- Registro de salidas (ventas)
- Kardex completo — historial de todos los movimientos
- Descuento automático de inventario al recibir un pedido

---

## 8. Personalización de la Tienda

- Banner / foto de portada propia
- Modo claro u oscuro
- Color principal personalizable
- Nombre del negocio y descripción
- Ubicación en mapa con botón "Cómo llegar"

---

## 9. Notificaciones

- Alerta por Telegram al dueño cada vez que llega un pedido nuevo
- Mensaje con todos los detalles del pedido (cliente, productos, total, dirección)

---

## 10. Acceso y Seguridad

- Links de acceso mágico para onboarding (sin necesidad de contraseña)
- PIN de caja por cajero
- Suscripción con fecha de vencimiento — bloqueo automático si no está al día

---

## 11. Contabilidad y Reportes

- Registro automático de cada venta en el sistema contable
- IVA separado por producto y por venta
- Integrado con el módulo de contabilidad general de TUC TUC

---

## 12. Métodos de Pago

- Cada tienda configura sus propios métodos aceptados:
  - Efectivo
  - Tarjeta
  - Transferencia bancaria
  - Billetera digital
  - Combinación de los anteriores en el mismo pedido

---

## 13. Comunidad / Red *(módulo plataforma, aplica a tiendas)*

- Programa de referidos: el dueño puede invitar a otros dueños y ganar créditos
- Catálogo compartido de nombres de productos entre todas las tiendas de la plataforma
- Red de crecimiento: cada tienda nueva enriquece el catálogo común

---

## — Notas para el pitch (pendiente de afinar) —

### Fortalezas identificadas hasta ahora
1. **Enlace con cliente preidentificado** — el cliente entra al link y ya está en el sistema, sin registro
2. **Preview automática para WhatsApp/Facebook** — imagen profesional generada sin esfuerzo
3. **Un clic al muro de Facebook que desencadena una compra trazable** — desde la publicación hasta el pedido, todo registrado
4. **Compartir dirigido (no broadcast)** — product + cliente específico + reconocimiento automático
5. **Catálogo público navegable por categorías** — reemplaza el catálogo de fotos de WhatsApp, que no tiene precio ni forma de pedir
6. **POS desde el celular** — no requiere software, funciona desde cualquier celular

### Comparativo (pendiente de desarrollar)
- vs. Foto en WhatsApp: ✗ sin precio, ✗ sin botón de pedido, ✗ sin trazabilidad
- vs. Instagram: ✗ no tiene tienda real, ✗ el pedido llega por DM, ✗ sin inventario
- vs. WhatsApp Business: ✗ catálogo estático, ✗ sin carrito, ✗ sin pedidos ni pago
- vs. TUC TUC: ✓ todo integrado, ✓ cliente preidentificado, ✓ pedido + inventario + caja + contabilidad

---

*Documento en construcción — agregar funciones a medida que se identifiquen y afinar el comparativo.*
