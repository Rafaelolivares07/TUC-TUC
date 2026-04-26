# Manual de Desarrollo — Tienda TUC TUC

**Módulo:** Tienda
**Versión:** 1.1
**Última actualización:** 2026-03-17
**Audiencia:** Desarrolladores que mantienen o extienden el módulo

---

## Arquitectura general

```
1_medicamentos.py          ← backend monolítico Flask
templates/tienda_admin.html ← panel del dueño (SPA con pestañas JS)
templates/tienda_cliente.html ← página pública del cliente
```

La tienda pública usa URLs tipo `/t/<slug>`. El panel admin usa `/tienda/admin` con sesión autenticada.

---

## Tabla `producto_imagenes`

Almacena las imágenes adicionales de cada producto (la imagen principal está en la tabla `productos`).

```sql
CREATE TABLE producto_imagenes (
    id          SERIAL PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    orden       INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

**Relación:** Un producto puede tener 0 o N filas en `producto_imagenes`. La imagen de portada está en `productos.imagen_url`. Las imágenes del carrusel están en `producto_imagenes`.

---

## Endpoint: `GET /api/tienda/<slug>/productos`

**Archivo:** `1_medicamentos.py`, función `api_tienda_productos`

### Respuesta

```json
{
  "productos": [
    {
      "id": 42,
      "nombre": "Camiseta azul",
      "precio": 25000,
      "imagen_url": "https://...",
      "tiene_variantes": true,
      "n_fotos": 3,
      ...
    }
  ]
}
```

### Campo `n_fotos`

Indica cuántas fotos adicionales tiene el producto en `producto_imagenes`. **No incluye la foto principal** (que está en `productos.imagen_url`).

**Implementación en el endpoint:**

```python
# Por cada producto p en el loop de resultados:
nf = conn.execute(
    "SELECT COUNT(*) FROM producto_imagenes WHERE producto_id = %s",
    (p['id'],)
).fetchone()[0]
producto_dict['n_fotos'] = nf
```

**Nota de rendimiento:** Se hace una query COUNT por producto. Para catálogos grandes (>100 productos), considerar en el futuro hacer un JOIN con subquery o una sola query con `GROUP BY` para obtener todos los counts de una vez. Por ahora el rendimiento es aceptable para el uso actual.

---

## Badge `📷 +N` en `tienda_cliente.html`

### CSS

```css
.badge-fotos {
    position: absolute;
    bottom: 8px;
    right: 8px;
    background: rgba(0,0,0,0.65);
    backdrop-filter: blur(4px);
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 7px;
    border-radius: 20px;
    display: flex;
    align-items: center;
    gap: 3px;
    pointer-events: none;  /* no interfiere con el clic en la card */
}
```

El `pointer-events: none` es importante — el badge es solo visual, el clic debe pasar a la card para abrir el modal.

### HTML generado (template JS)

```javascript
// Dentro del template de tarjeta de producto
${p.n_fotos > 0
  ? `<span class="badge-fotos">
       <svg ...icono cámara...></svg>
       +${p.n_fotos}
     </span>`
  : ''
}
```

El badge solo se renderiza si `p.n_fotos > 0`. Si el producto no tiene fotos adicionales, la tarjeta no muestra ningún badge.

---

## Dark mode — Modal de detalle de producto

### Problema resuelto (2026-03-14)

El modal de detalle de producto tenía clases de fondo hardcodeadas en blanco (`bg-white`), lo que hacía que en modo oscuro se viera un rectángulo blanco brillante dentro de un contexto oscuro.

### Fix aplicado

**Contenedor del modal:** añadir clase `modal-card` además de (o en lugar de) `bg-white`:

```html
<!-- Antes (roto en dark mode): -->
<div class="... bg-white rounded-2xl shadow-2xl ...">

<!-- Después (correcto): -->
<div class="modal-card bg-white rounded-2xl shadow-2xl ...">
```

**CSS que maneja el dark mode:**
```css
/* ya existía en el archivo */
.tema-oscuro .modal-card {
    background: #1f2937;
}
```

Al agregar la clase `modal-card`, el CSS de modo oscuro ya existente toma efecto automáticamente.

### Fondo de imagen en el modal (`foto-grande-bg`)

El contenedor donde se muestra la imagen ampliada tenía un `style` inline con `background: #f3f4f6`. Se reemplazó por una clase CSS para que el dark mode también aplique:

```html
<!-- Antes: -->
<div style="background: #f3f4f6; ...">

<!-- Después: -->
<div class="foto-grande-bg ...">
```

```css
.foto-grande-bg {
    background: #f3f4f6;
}
.tema-oscuro .foto-grande-bg {
    background: #374151;
}
```

**Por qué una clase en lugar de inline style:** Los estilos inline no pueden ser sobreescritos por selectores CSS de clases. `.tema-oscuro .foto-grande-bg` necesita que sea una clase para funcionar.

---

## Pestaña 🖥️ Soporte en `tienda_admin.html`

### Cómo funcionan los tabs

Los tabs del panel admin usan un sistema JS con un array de IDs:

```javascript
function cambiarTab(tab) {
    const tabs = ['catalogo','pedidos','inventario','personalizar','acceso','ubicacion','soporte'];
    tabs.forEach(t => {
        document.getElementById('panel-' + t).classList.add('hidden');
        document.getElementById('tab-' + t).classList.remove('tab-activo');
    });
    document.getElementById('panel-' + tab).classList.remove('hidden');
    document.getElementById('tab-' + tab).classList.add('tab-activo');
}
```

Para agregar un nuevo tab:
1. Agregar el ID al array `tabs`
2. Agregar el botón: `<button onclick="cambiarTab('nuevo')" id="tab-nuevo" class="tab-btn">Label</button>`
3. Agregar el panel: `<div id="panel-nuevo" class="hidden">...</div>`

### Tab Soporte

Botón:
```html
<button onclick="cambiarTab('soporte')" id="tab-soporte" class="tab-btn">🖥️ Soporte</button>
```

El panel `panel-soporte` contiene el flujo de 3 pasos de asistencia remota (instrucciones para el dueño) y el enlace directo al visor para técnicos.

---

## Bug histórico: nested `<a>` en `admin_menu.html`

**Fecha:** 2026-03-14
**Síntoma:** Aparecía una card vacía a la izquierda de la card "Asistencia Remota" en `/area_admin`. Al hacer clic en esa card vacía, abría el visor remoto.

**Causa raíz:** HTML inválido — había un `<a>` (enlace de descarga del `.exe`) anidado dentro de otro `<a>` (el enlace de la card completa). El estándar HTML prohíbe anidar elementos interactivos. Chrome "arregla" el error cerrando el `<a>` externo antes de tiempo y promoviendo el `<a>` interno a hijo directo del grid — creando así un elemento extra en el grid.

**Fix:** Reemplazar el `<a>` interno por `<span onclick="event.stopPropagation(); window.open('...')">`. El comportamiento es idéntico para el usuario pero el HTML es válido.

```html
<!-- ANTES (HTML inválido — produce card fantasma): -->
<a href="https://tuc-tuc-remote.onrender.com" target="_blank" class="block ...">
    ...
    <a href="https://github.com/.../AsistenciaTucTuc.exe"
       onclick="event.stopPropagation()">Descargar agente (.exe)</a>
</a>

<!-- DESPUÉS (HTML válido): -->
<a href="https://tuc-tuc-remote.onrender.com" target="_blank" class="block ...">
    ...
    <span onclick="event.stopPropagation(); window.open('https://github.com/.../AsistenciaTucTuc.exe')"
          class="cursor-pointer ...">Descargar agente (.exe)</span>
</a>
```

**Regla general:** Nunca anidar `<a>` dentro de `<a>`, ni `<button>` dentro de `<a>`. Para links secundarios dentro de una card-link, siempre usar `<span onclick>` o `<button onclick>` con `event.stopPropagation()`.

---

## APIs relacionadas

| Ruta | Método | Auth | Descripción |
|---|---|---|---|
| `/api/tienda/<slug>/productos` | GET | Pública | Lista productos con `n_fotos` y `tiene_variantes` |
| `/api/tienda/<slug>/producto/<id>` | GET | Pública | Detalle de producto con imágenes del carrusel |
| `/api/tienda/<slug>/carrito` | POST | Pública | Agregar al carrito |
| `/api/tienda/admin/producto` | POST | Sesión dueño | Crear/editar producto |
| `/api/tienda/admin/producto/<id>/fotos` | POST | Sesión dueño | Subir fotos adicionales |

---

## Header de la tienda — título y descripción

La sección de título/descripción tiene **3 variantes** según la configuración de la tienda, todas en `tienda_cliente.html`:

| Caso | Condición |
|---|---|
| Con imagen + nombre visible | `tienda.imagen_header` existe Y `tienda.mostrar_nombre = true` |
| Con imagen + nombre oculto | `tienda.imagen_header` existe Y `tienda.mostrar_nombre = false` |
| Sin imagen | `tienda.imagen_header` no existe |

### Clases aplicadas (2026-03-17)

```html
<!-- Título -->
<h1 class="text-2xl font-extrabold txt-primary tracking-tight leading-snug drop-shadow-sm">

<!-- Descripción -->
<p class="text-sm txt-secondary mt-2 leading-relaxed max-w-sm mx-auto opacity-90">

<!-- Contenedor (con imagen) -->
<div class="px-4 pt-4 pb-3 text-center">

<!-- Contenedor (sin imagen) -->
<div class="px-6 pt-6 pb-3 text-center">
```

**Decisiones de diseño:**
- `text-center` en el contenedor — centra título y descripción horizontalmente
- `tracking-tight` — aprieta el kerning del título, da más carácter tipográfico
- `drop-shadow-sm` — sombra sutil que da cuerpo al título sobre fondos claros y oscuros
- `leading-relaxed` en la descripción — mejor legibilidad en texto de más de una línea
- `max-w-sm mx-auto` en la descripción — evita que líneas largas se estiren al ancho completo en pantallas grandes; la descripción queda como bloque centrado y compacto
- `opacity-90` — descripción levemente atenuada respecto al título para mantener jerarquía visual

---

## Notas de estilo y convenciones

- **Modo oscuro:** Se activa agregando la clase `tema-oscuro` al `<body>`. Todos los overrides de dark mode usan el selector `.tema-oscuro .<clase>`.
- **Modales:** Usar la clase `modal-card` en el contenedor principal del modal para que el dark mode aplique automáticamente.
- **Imágenes con fondo:** Usar la clase `foto-grande-bg` en lugar de `style="background: ..."` para que el dark mode funcione.
- **Badges sobre imágenes:** Posición `absolute` dentro de un contenedor `relative`. `pointer-events: none` para no interceptar clics.
