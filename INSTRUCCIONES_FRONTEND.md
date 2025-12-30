# Instrucciones para integrar sistema de horarios en frontend

## Archivos a modificar

### 1. tienda_home.html

#### A) Agregar estilos CSS (dentro de `<style>`, antes del `</style>`)

```css
/* Toast para notificación de producto agregado */
.toast {
    position: fixed;
    bottom: 100px;
    right: 20px;
    background: #10b981;
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    transform: translateX(400px);
    transition: transform 0.3s ease;
    z-index: 9999;
    font-weight: 600;
}

.toast.show {
    transform: translateX(0);
}

/* Modal de advertencia de horario */
.modal-horario {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.7);
    z-index: 10000;
    align-items: center;
    justify-content: center;
}

.modal-horario.show {
    display: flex;
}

.modal-horario-content {
    background: white;
    padding: 2rem;
    border-radius: 12px;
    max-width: 400px;
    margin: 1rem;
    text-align: center;
}

.modal-horario-content h3 {
    font-size: 1.5rem;
    font-weight: bold;
    margin-bottom: 1rem;
    color: #333;
}

.modal-horario-content p {
    font-size: 1rem;
    color: #666;
    line-height: 1.6;
    margin-bottom: 1.5rem;
}

.modal-horario-btn {
    background: #2e89ff;
    color: white;
    padding: 0.75rem 2rem;
    border-radius: 8px;
    border: none;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    width: 100%;
}

.modal-horario-btn:active {
    transform: scale(0.98);
}
```

#### B) Agregar HTML del toast y modal (antes del cierre `</body>`)

```html
<!-- Toast para notificación de producto agregado -->
<div id="toast" class="toast"></div>

<!-- Modal de advertencia de horario -->
<div id="modal-horario" class="modal-horario">
    <div class="modal-horario-content">
        <h3>⚠️ Entrega Programada</h3>
        <p id="modal-horario-mensaje"></p>
        <button class="modal-horario-btn" onclick="cerrarModalHorario()">Entendido</button>
    </div>
</div>
```

#### C) Reemplazar la función `agregarAlCarrito` (línea 2276-2297)

ANTES:
```javascript
function agregarAlCarrito(producto) {
    if (!producto.precio || producto.precio <= 0) {
        alert('Este producto no tiene precio disponible');
        return;
    }

    const index = carrito.findIndex(item => item.precio_id === producto.precio_id);

    if (index >= 0) {
        carrito[index].cantidad++;
    } else {
        carrito.push({
            ...producto,
            cantidad: 1
        });
    }

    localStorage.setItem('carrito', JSON.stringify(carrito));
    actualizarBadgeCarrito();

    alert(`${producto.nombre} (${producto.fabricante}) agregado al carrito`);
}
```

DESPUÉS:
```javascript
async function agregarAlCarrito(producto) {
    if (!producto.precio || producto.precio <= 0) {
        mostrarToast('Este producto no tiene precio disponible');
        return;
    }

    const index = carrito.findIndex(item => item.precio_id === producto.precio_id);

    if (index >= 0) {
        carrito[index].cantidad++;
    } else {
        carrito.push({
            ...producto,
            cantidad: 1
        });
    }

    localStorage.setItem('carrito', JSON.stringify(carrito));
    actualizarBadgeCarrito();

    // Mostrar toast
    mostrarToast(`${producto.nombre} agregado al carrito`);

    // Validar horario solo en el PRIMER producto
    const yaVioModal = localStorage.getItem('vio_modal_horario');
    if (!yaVioModal) {
        await validarYMostrarModalHorario();
    }
}

function mostrarToast(mensaje) {
    const toast = document.getElementById('toast');
    toast.textContent = mensaje;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

async function validarYMostrarModalHorario() {
    try {
        const res = await fetch('/api/validar-horario');
        const data = await res.json();

        if (data.ok && !data.dentro_horario && data.mensaje) {
            // Fuera de horario - mostrar modal
            const modal = document.getElementById('modal-horario');
            const mensaje = document.getElementById('modal-horario-mensaje');

            mensaje.textContent = data.mensaje;
            modal.classList.add('show');

            // Marcar que ya vio el modal
            localStorage.setItem('vio_modal_horario', 'true');
        }
    } catch (error) {
        console.error('Error validando horario:', error);
        // No bloquear la compra si hay error
    }
}

function cerrarModalHorario() {
    const modal = document.getElementById('modal-horario');
    modal.classList.remove('show');
}
```

---

### 2. carrito.html

#### A) Buscar la sección antes del botón "Continuar con la Compra" (aprox línea 299)

#### B) Agregar advertencia de horario

AGREGAR ANTES del botón "Continuar con la Compra":

```html
<!-- Advertencia de horario (si aplica) -->
<div id="advertencia-horario" style="display: none; background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
    <p style="margin: 0; color: #92400e; font-size: 0.95rem;">
        <strong>⚠️ Nota:</strong> <span id="mensaje-horario"></span>
    </p>
</div>
```

#### C) Agregar JavaScript al final (antes de `</script>`)

```javascript
// Validar horario al cargar el carrito
async function validarHorarioCarrito() {
    try {
        const res = await fetch('/api/validar-horario');
        const data = await res.json();

        if (data.ok && !data.dentro_horario && data.mensaje) {
            // Mostrar advertencia
            const advertencia = document.getElementById('advertencia-horario');
            const mensaje = document.getElementById('mensaje-horario');

            mensaje.textContent = data.mensaje;
            advertencia.style.display = 'block';
        }
    } catch (error) {
        console.error('Error validando horario:', error);
    }
}

// Ejecutar validación al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    validarHorarioCarrito();
});
```

---

## Resumen de cambios

1. **tienda_home.html**:
   - Agregar estilos CSS para toast y modal
   - Agregar HTML del toast y modal
   - Reemplazar `alert()` con `mostrarToast()`
   - Validar horario en primer producto
   - Mostrar modal una sola vez

2. **carrito.html**:
   - Agregar div de advertencia
   - Validar horario al cargar
   - Mostrar mensaje discreto

## Notas importantes

- El modal solo se muestra UNA VEZ (localStorage: 'vio_modal_horario')
- Si hay error en validación, NO bloquea la compra
- El toast es discreto y desaparece en 3 segundos
- La advertencia en carrito es visible pero no intrusiva
