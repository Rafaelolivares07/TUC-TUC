// Modal Carrusel de Tareas de Revisión de Cotizaciones
// Este script verifica si hay tareas pendientes y muestra un modal carrusel

let tareasRevisionPendientes = [];
let indiceActual = 0;
let ultimaVerificacion = null;

// Verificar si es hora de mostrar alertas
async function debeVerificarTareas() {
    try {
        // Obtener frecuencia configurada
        const res = await fetch('/api/parametro/frecuencia_alerta_cotizaciones');
        const data = await res.json();

        if (!data.ok || !data.valor) return false;

        const frecuencia = data.valor;
        const ahora = new Date();

        // Si es 'login' o 'ambos', verificar al cargar la página
        if (frecuencia === 'login' || frecuencia === 'ambos') {
            // Verificar solo si no lo hemos hecho en esta sesión
            if (!sessionStorage.getItem('tareas_verificadas_en_login')) {
                sessionStorage.setItem('tareas_verificadas_en_login', 'true');
                return true;
            }
        }

        // Si es 'periodico' o 'ambos', verificar cada X días
        if (frecuencia === 'periodico' || frecuencia === 'ambos') {
            const resDias = await fetch('/api/parametro/dias_alerta_periodica_cotizaciones');
            const dataDias = await resDias.json();

            if (dataDias.ok && dataDias.valor) {
                const diasPeriodico = parseInt(dataDias.valor);
                const ultimaVerificacionStr = localStorage.getItem('ultima_verificacion_tareas');

                if (!ultimaVerificacionStr) {
                    return true; // Primera vez
                }

                const ultimaVerificacion = new Date(ultimaVerificacionStr);
                const diasTranscurridos = (ahora - ultimaVerificacion) / (1000 * 60 * 60 * 24);

                if (diasTranscurridos >= diasPeriodico) {
                    return true;
                }
            }
        }

        return false;

    } catch (error) {
        console.error('Error verificando si debe mostrar tareas:', error);
        return false;
    }
}

// Cargar tareas pendientes
async function cargarTareasPendientes() {
    try {
        const res = await fetch('/api/tareas-revision/pendientes');
        const data = await res.json();

        if (data.ok && data.tareas && data.tareas.length > 0) {
            tareasRevisionPendientes = data.tareas;
            indiceActual = 0;
            mostrarModalTareas();

            // Actualizar timestamp de última verificación
            localStorage.setItem('ultima_verificacion_tareas', new Date().toISOString());
        }
    } catch (error) {
        console.error('Error cargando tareas pendientes:', error);
    }
}

// Crear y mostrar el modal
function mostrarModalTareas() {
    if (tareasRevisionPendientes.length === 0) return;

    // Crear modal HTML
    const modalHTML = `
        <div id="modal-tareas-revision" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 10000; align-items: center; justify-content: center;">
            <div style="background: white; border-radius: 12px; max-width: 700px; width: 90%; max-height: 90vh; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.3);">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h3 style="margin: 0; font-size: 1.5rem;">📋 Revisión de Cotizaciones</h3>
                        <p style="margin: 5px 0 0 0; font-size: 0.9rem; opacity: 0.9;" id="contador-tareas"></p>
                    </div>
                    <button onclick="cerrarModalTareas()" style="background: rgba(255,255,255,0.2); border: none; color: white; font-size: 24px; width: 36px; height: 36px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">
                        ×
                    </button>
                </div>

                <!-- Contenido de la tarea -->
                <div id="contenido-tarea-actual" style="padding: 30px; max-height: calc(90vh - 200px); overflow-y: auto;">
                    <!-- Cargado dinámicamente -->
                </div>

                <!-- Botones -->
                <div style="padding: 20px; background: #f8f9fa; display: flex; justify-content: space-between; gap: 10px; border-top: 1px solid #dee2e6;">
                    <button onclick="rechazarTarea()" style="background: #dc3545; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: background 0.2s;" onmouseover="this.style.background='#c82333'" onmouseout="this.style.background='#dc3545'">
                        ❌ Estoy Ocupado
                    </button>
                    <div style="display: flex; gap: 10px;">
                        <button onclick="confirmarPrecio()" style="background: #28a745; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: background 0.2s;" onmouseover="this.style.background='#218838'" onmouseout="this.style.background='#28a745'">
                            ✅ Confirmar Precio
                        </button>
                        <button onclick="mostrarInputActualizar()" style="background: #007bff; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: background 0.2s;" onmouseover="this.style.background='#0056b3'" onmouseout="this.style.background='#007bff'">
                            🔄 Actualizar Precio
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Agregar modal al body si no existe
    if (!document.getElementById('modal-tareas-revision')) {
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    // Mostrar tarea actual
    mostrarTareaActual();

    // Mostrar modal con flex
    const modal = document.getElementById('modal-tareas-revision');
    modal.style.display = 'flex';
}

// Mostrar tarea actual del carrusel
function mostrarTareaActual() {
    if (indiceActual >= tareasRevisionPendientes.length) {
        cerrarModalTareas();
        return;
    }

    const tarea = tareasRevisionPendientes[indiceActual];

    // Actualizar contador
    document.getElementById('contador-tareas').textContent =
        `Tarea ${indiceActual + 1} de ${tareasRevisionPendientes.length}`;

    // Renderizar contenido de la tarea
    const contenido = document.getElementById('contenido-tarea-actual');
    contenido.innerHTML = `
        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
            <p style="margin: 0; font-weight: 600; color: #856404;">
                ⚠️ Esta cotización tiene <strong>${tarea.dias_vencido} días</strong> sin actualizar
            </p>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
            <div>
                <label style="font-size: 0.85rem; color: #6c757d; font-weight: 600; display: block; margin-bottom: 5px;">💊 MEDICAMENTO</label>
                <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #212529;">${tarea.medicamento}</p>
            </div>
            <div>
                <label style="font-size: 0.85rem; color: #6c757d; font-weight: 600; display: block; margin-bottom: 5px;">🏭 FABRICANTE</label>
                <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #212529;">${tarea.fabricante}</p>
            </div>
        </div>

        <div style="background: #e7f3ff; border: 1px solid #b3d7ff; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
            <label style="font-size: 0.85rem; color: #004085; font-weight: 600; display: block; margin-bottom: 5px;">🏪 COMPETIDOR</label>
            <p style="margin: 0; font-size: 1.2rem; font-weight: 700; color: #004085;">${tarea.competidor}</p>
        </div>

        <div style="background: #d4edda; border: 1px solid #c3e6cb; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
            <label style="font-size: 0.85rem; color: #155724; font-weight: 600; display: block; margin-bottom: 5px;">💰 PRECIO ACTUAL</label>
            <p style="margin: 0; font-size: 1.8rem; font-weight: 700; color: #155724;">$${parseFloat(tarea.precio).toLocaleString('es-CO')}</p>
            <p style="margin: 5px 0 0 0; font-size: 0.85rem; color: #155724;">Última actualización: ${new Date(tarea.fecha_actualizacion).toLocaleDateString('es-CO')}</p>
        </div>

        ${tarea.url ? `
            <div style="margin-bottom: 20px;">
                <a href="${tarea.url}" target="_blank" style="display: inline-block; background: #17a2b8; color: white; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; transition: background 0.2s;" onmouseover="this.style.background='#138496'" onmouseout="this.style.background='#17a2b8'">
                    🔗 Abrir Cotización Original
                </a>
            </div>
        ` : ''}

        <div id="contenedor-input-actualizar" style="display: none; margin-top: 20px;">
            <label style="font-size: 0.9rem; color: #495057; font-weight: 600; display: block; margin-bottom: 8px;">Nuevo precio:</label>
            <div style="display: flex; gap: 10px; align-items: center;">
                <span style="font-size: 1.5rem; font-weight: 700;">$</span>
                <input type="number" id="input-nuevo-precio" step="0.01" min="0" placeholder="${tarea.precio}" style="flex: 1; padding: 12px; border: 2px solid #007bff; border-radius: 6px; font-size: 1.2rem; font-weight: 600;">
                <button onclick="guardarPrecioActualizado()" style="background: #28a745; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; white-space: nowrap;">
                    💾 Guardar
                </button>
            </div>
        </div>
    `;
}

// Mostrar input de actualizar precio
function mostrarInputActualizar() {
    document.getElementById('contenedor-input-actualizar').style.display = 'block';
    document.getElementById('input-nuevo-precio').focus();
}

// Confirmar precio actual (sin cambios)
async function confirmarPrecio() {
    const tarea = tareasRevisionPendientes[indiceActual];

    try {
        const res = await fetch('/api/tareas-revision/responder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tarea_id: tarea.tarea_id,
                accion: 'completar',
                observaciones: 'Precio confirmado sin cambios'
            })
        });

        const data = await res.json();

        if (data.ok) {
            avanzarSiguienteTarea();
        } else {
            alert('❌ Error: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        console.error('Error confirmando precio:', error);
        alert('❌ Error al confirmar precio');
    }
}

// Guardar precio actualizado
async function guardarPrecioActualizado() {
    const tarea = tareasRevisionPendientes[indiceActual];
    const nuevoPrecio = parseFloat(document.getElementById('input-nuevo-precio').value);

    if (isNaN(nuevoPrecio) || nuevoPrecio <= 0) {
        alert('⚠️ Debe ingresar un precio válido');
        return;
    }

    try {
        const res = await fetch('/api/tareas-revision/responder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tarea_id: tarea.tarea_id,
                accion: 'actualizar',
                precio_nuevo: nuevoPrecio,
                observaciones: `Precio actualizado de $${tarea.precio} a $${nuevoPrecio}`
            })
        });

        const data = await res.json();

        if (data.ok) {
            avanzarSiguienteTarea();
        } else {
            alert('❌ Error: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        console.error('Error actualizando precio:', error);
        alert('❌ Error al actualizar precio');
    }
}

// Rechazar tarea (estoy ocupado)
async function rechazarTarea() {
    const tarea = tareasRevisionPendientes[indiceActual];

    try {
        const res = await fetch('/api/tareas-revision/responder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tarea_id: tarea.tarea_id,
                accion: 'rechazar',
                observaciones: 'Admin rechazó la tarea (ocupado con otras tareas)'
            })
        });

        const data = await res.json();

        if (data.ok) {
            avanzarSiguienteTarea();
        } else {
            alert('❌ Error: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        console.error('Error rechazando tarea:', error);
        alert('❌ Error al rechazar tarea');
    }
}

// Avanzar a la siguiente tarea
function avanzarSiguienteTarea() {
    indiceActual++;

    if (indiceActual >= tareasRevisionPendientes.length) {
        // No hay más tareas
        cerrarModalTareas();
        alert('✅ ¡Todas las tareas han sido procesadas!');
    } else {
        // Mostrar siguiente tarea
        mostrarTareaActual();
    }
}

// Cerrar modal
function cerrarModalTareas() {
    const modal = document.getElementById('modal-tareas-revision');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Inicializar al cargar la página (solo para admins)
document.addEventListener('DOMContentLoaded', async () => {
    // Verificar si debe mostrar tareas
    const debeVerificar = await debeVerificarTareas();

    if (debeVerificar) {
        await cargarTareasPendientes();
    }
});
