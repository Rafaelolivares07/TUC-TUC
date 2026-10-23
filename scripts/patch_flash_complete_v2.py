# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('templates/caja.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update Badge in renderProductosFlash
old_badge = """                <!-- Badge de Cantidad (Persistente para cero toques perdidos) -->
                <div id="flash-badge-${p.id}" class="absolute -top-2.5 -right-2 bg-emerald-600 text-white font-black text-xs sm:text-sm px-2.5 py-0.5 rounded-full shadow-md flex items-center gap-1 animate-in zoom-in duration-100 ${cant > 0 ? '' : 'hidden'}">
                    <span>x${cant}</span>
                </div>"""

new_badge = """                <!-- Badge de Cantidad y Botón Llevar a Cero ✕ (Fácil y Táctil) -->
                <div id="flash-badge-${p.id}" class="absolute -top-3 -right-2 bg-emerald-600 text-white font-black text-xs sm:text-sm pl-2.5 pr-1 py-0.5 rounded-full shadow-md flex items-center gap-1.5 animate-in zoom-in duration-100 ${cant > 0 ? '' : 'hidden'}">
                    <span id="flash-badge-txt-${p.id}">x${cant}</span>
                    <button type="button" onclick="event.stopPropagation(); llevarACeroProductoFlash(${p.id})"
                            class="w-6 h-6 rounded-full bg-emerald-800 hover:bg-rose-600 active:scale-90 text-white flex items-center justify-center font-bold text-xs cursor-pointer border border-emerald-400/40 shadow-xs transition"
                            title="Llevar a cero (borrar cantidad)">
                        ✕
                    </button>
                </div>"""

if old_badge in html:
    html = html.replace(old_badge, new_badge, 1)
    print("1. Badge updated with tactile ✕ button")
else:
    print("WARNING 1: old_badge not found")

# 2. Update tocarProductoFlash, cambiarCantidadFlash, and add llevarACeroProductoFlash
old_touch = """function tocarProductoFlash(prodId) {
    pedidoFlash[prodId] = (pedidoFlash[prodId] || 0) + 1;
    actualizarCardProductoFlashDOM(prodId);
    actualizarTotalesFlash();
}

function cambiarCantidadFlash(prodId, delta) {
    const act = (pedidoFlash[prodId] || 0) + delta;
    if (act <= 0) {
        delete pedidoFlash[prodId];
    } else {
        pedidoFlash[prodId] = act;
    }
    actualizarCardProductoFlashDOM(prodId);
    actualizarTotalesFlash();
}

function actualizarCardProductoFlashDOM(prodId) {
    const card = document.getElementById('flash-card-' + prodId);
    const badge = document.getElementById('flash-badge-' + prodId);
    const btnMinus = document.getElementById('flash-btn-minus-' + prodId);
    const cant = pedidoFlash[prodId] || 0;
    
    if (card) {
        if (cant > 0) {
            card.className = "flash-card relative p-3.5 sm:p-4 rounded-3xl border-2 border-emerald-500 bg-emerald-50/50 shadow-md ring-2 ring-emerald-400/40 flex flex-col justify-between min-h-[118px] sm:min-h-[132px] cursor-pointer transition select-none";
        } else {
            card.className = "flash-card relative p-3.5 sm:p-4 rounded-3xl border-2 border-gray-200 hover:border-gray-300 bg-white shadow-xs flex flex-col justify-between min-h-[118px] sm:min-h-[132px] cursor-pointer transition select-none";
        }
    }
    if (badge) {
        if (cant > 0) {
            badge.innerHTML = `<span>x${cant}</span>`;
            badge.classList.remove('hidden');
            // Micro-pulsación táctil para confirmación visual inmediata
            badge.classList.remove('animate-in', 'zoom-in');
            void badge.offsetWidth;
            badge.classList.add('animate-in', 'zoom-in');
        } else {
            badge.classList.add('hidden');
        }
    }
    if (btnMinus) {
        if (cant > 0) btnMinus.classList.remove('hidden');
        else btnMinus.classList.add('hidden');
    }
}"""

new_touch = """function tocarProductoFlash(prodId) {
    pedidoFlash[prodId] = (pedidoFlash[prodId] || 0) + 1;
    actualizarCardProductoFlashDOM(prodId);
    actualizarTotalesFlash();
}

function cambiarCantidadFlash(prodId, delta) {
    const act = (pedidoFlash[prodId] || 0) + delta;
    if (act <= 0) {
        delete pedidoFlash[prodId];
    } else {
        pedidoFlash[prodId] = act;
    }
    actualizarCardProductoFlashDOM(prodId);
    actualizarTotalesFlash();
}

function llevarACeroProductoFlash(prodId) {
    delete pedidoFlash[prodId];
    actualizarCardProductoFlashDOM(prodId);
    actualizarTotalesFlash();
}

function actualizarCardProductoFlashDOM(prodId) {
    const card = document.getElementById('flash-card-' + prodId);
    const badge = document.getElementById('flash-badge-' + prodId);
    const btnMinus = document.getElementById('flash-btn-minus-' + prodId);
    const cant = pedidoFlash[prodId] || 0;
    
    if (card) {
        if (cant > 0) {
            card.className = "flash-card relative p-3.5 sm:p-4 rounded-3xl border-2 border-emerald-500 bg-emerald-50/50 shadow-md ring-2 ring-emerald-400/40 flex flex-col justify-between min-h-[118px] sm:min-h-[132px] cursor-pointer transition select-none";
        } else {
            card.className = "flash-card relative p-3.5 sm:p-4 rounded-3xl border-2 border-gray-200 hover:border-gray-300 bg-white shadow-xs flex flex-col justify-between min-h-[118px] sm:min-h-[132px] cursor-pointer transition select-none";
        }
    }
    if (badge) {
        if (cant > 0) {
            const txt = document.getElementById('flash-badge-txt-' + prodId);
            if (txt) {
                txt.textContent = `x${cant}`;
            } else {
                badge.innerHTML = `
                    <span id="flash-badge-txt-${prodId}">x${cant}</span>
                    <button type="button" onclick="event.stopPropagation(); llevarACeroProductoFlash(${prodId})"
                            class="w-6 h-6 rounded-full bg-emerald-800 hover:bg-rose-600 active:scale-90 text-white flex items-center justify-center font-bold text-xs cursor-pointer border border-emerald-400/40 shadow-xs transition"
                            title="Llevar a cero (borrar cantidad)">
                        ✕
                    </button>
                `;
            }
            badge.classList.remove('hidden');
            // Micro-pulsación táctil para confirmación visual inmediata
            badge.classList.remove('animate-in', 'zoom-in');
            void badge.offsetWidth;
            badge.classList.add('animate-in', 'zoom-in');
        } else {
            badge.classList.add('hidden');
        }
    }
    if (btnMinus) {
        if (cant > 0) btnMinus.classList.remove('hidden');
        else btnMinus.classList.add('hidden');
    }
}"""

if old_touch in html:
    html = html.replace(old_touch, new_touch, 1)
    print("2. DOM and zero-clear functions updated")
else:
    print("WARNING 2: old_touch not found")

# 3. Update modal-validacion-flash HTML
old_modal_val = """<!-- Modal de Validación Post-Facturación Flash -->
<div id="modal-validacion-flash" class="hidden fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-3xl shadow-2xl w-full max-w-sm p-5 flex flex-col gap-3.5 border border-gray-150 animate-in zoom-in-95 duration-150" onclick="event.stopPropagation()">
        <!-- Header con check -->
        <div class="flex items-center gap-2.5 pb-2.5 border-b border-gray-150">
            <span class="w-10 h-10 rounded-2xl bg-emerald-100 text-emerald-700 flex items-center justify-center text-xl shrink-0 font-black">✓</span>
            <div class="min-w-0">
                <h3 class="font-black text-sm text-gray-900 leading-tight truncate">
                    ¡Venta <span id="val-flash-num-doc">#---</span> Registrada!
                </h3>
                <span id="val-flash-hora" class="text-[11px] text-gray-500 font-semibold block">00:00 a.m.</span>
            </div>
        </div>

        <!-- Lista de productos que acaba de marcar -->
        <div class="bg-slate-50 rounded-2xl p-3 border border-slate-200/90 space-y-1.5 font-mono text-xs">
            <div id="val-flash-items-lista" class="space-y-1 text-slate-900 font-bold max-h-36 overflow-y-auto">
                <!-- Items list -->
            </div>
            <div class="pt-2 border-t border-slate-200 flex items-center justify-between text-xs font-black text-slate-800">
                <span>Total Sándwiches / Unds:</span>
                <span id="val-flash-total-unds" class="text-indigo-700 text-sm font-black">0 unds</span>
            </div>
            <div class="flex items-center justify-between text-xs font-black text-slate-900">
                <span>Total Cobrado:</span>
                <span id="val-flash-total-monto" class="text-emerald-700 text-base font-black">$0</span>
            </div>
            <div class="text-[10px] text-slate-500 font-semibold flex items-center justify-between pt-1 border-t border-slate-200/60">
                <span>Forma de pago:</span>
                <span id="val-flash-metodo-pago" class="font-bold text-slate-700">Efectivo</span>
            </div>
        </div>

        <!-- Pregunta y Botones Táctiles de Validación -->
        <div class="pt-1">
            <p class="text-xs font-black text-center text-gray-700 mb-2.5">
                ¿Confirmas que el registro fue correcto?
            </p>
            <div class="grid grid-cols-2 gap-2.5">
                <button type="button" onclick="responderValidacionFlash('incorrecto')"
                        class="py-3 px-3 rounded-2xl bg-rose-50 hover:bg-rose-100 active:scale-95 border-2 border-rose-300 text-rose-700 font-black text-xs sm:text-sm flex items-center justify-center gap-1.5 shadow-2xs transition cursor-pointer">
                    <span>❌</span> <span>INCORRECTO</span>
                </button>
                <button type="button" onclick="responderValidacionFlash('ok')"
                        class="py-3 px-3 rounded-2xl bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white font-black text-xs sm:text-sm flex items-center justify-center gap-1.5 shadow-md transition cursor-pointer">
                    <span>✅</span> <span>OK / BIEN</span>
                </button>
            </div>
        </div>
    </div>
</div>"""

new_modal_val = """<!-- Modal de Validación Post-Facturación Flash -->
<div id="modal-validacion-flash" class="hidden fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-3xl shadow-2xl w-full max-w-sm p-5 flex flex-col gap-3.5 border border-gray-150 animate-in zoom-in-95 duration-150" onclick="event.stopPropagation()">
        
        <!-- PASO 1: Confirmación Rápida -->
        <div id="val-flash-paso-confirmacion" class="space-y-3.5">
            <!-- Header con check -->
            <div class="flex items-center gap-2.5 pb-2.5 border-b border-gray-150">
                <span class="w-10 h-10 rounded-2xl bg-emerald-100 text-emerald-700 flex items-center justify-center text-xl shrink-0 font-black">✓</span>
                <div class="min-w-0">
                    <h3 class="font-black text-sm text-gray-900 leading-tight truncate">
                        ¡Venta <span id="val-flash-num-doc">#---</span> Registrada!
                    </h3>
                    <span id="val-flash-hora" class="text-[11px] text-gray-500 font-semibold block">00:00 a.m.</span>
                </div>
            </div>

            <!-- Lista de productos que acaba de marcar -->
            <div class="bg-slate-50 rounded-2xl p-3 border border-slate-200/90 space-y-1.5 font-mono text-xs">
                <div id="val-flash-items-lista" class="space-y-1 text-slate-900 font-bold max-h-36 overflow-y-auto">
                    <!-- Items list -->
                </div>
                <div class="pt-2 border-t border-slate-200 flex items-center justify-between text-xs font-black text-slate-800">
                    <span>Total Sándwiches / Unds:</span>
                    <span id="val-flash-total-unds" class="text-indigo-700 text-sm font-black">0 unds</span>
                </div>
                <div class="flex items-center justify-between text-xs font-black text-slate-900">
                    <span>Total Cobrado:</span>
                    <span id="val-flash-total-monto" class="text-emerald-700 text-base font-black">$0</span>
                </div>
                <div class="text-[10px] text-slate-500 font-semibold flex items-center justify-between pt-1 border-t border-slate-200/60">
                    <span>Forma de pago:</span>
                    <span id="val-flash-metodo-pago" class="font-bold text-slate-700">Efectivo</span>
                </div>
            </div>

            <!-- Pregunta y Botones Táctiles de Validación -->
            <div class="pt-1">
                <p class="text-xs font-black text-center text-gray-700 mb-2.5">
                    ¿Confirmas que el registro fue correcto?
                </p>
                <div class="grid grid-cols-2 gap-2.5">
                    <button type="button" onclick="mostrarPasoMotivosFlash()"
                            class="py-3 px-3 rounded-2xl bg-rose-50 hover:bg-rose-100 active:scale-95 border-2 border-rose-300 text-rose-700 font-black text-xs sm:text-sm flex items-center justify-center gap-1.5 shadow-2xs transition cursor-pointer">
                        <span>❌</span> <span>INCORRECTO</span>
                    </button>
                    <button type="button" onclick="enviarValidacionFlash('ok', '')"
                            class="py-3 px-3 rounded-2xl bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white font-black text-xs sm:text-sm flex items-center justify-center gap-1.5 shadow-md transition cursor-pointer">
                        <span>✅</span> <span>OK / BIEN</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- PASO 2: Selección de Motivo con 1 Solo Toque -->
        <div id="val-flash-paso-motivos" class="hidden space-y-3">
            <div class="flex items-center gap-2 pb-2 border-b border-gray-150">
                <span class="w-8 h-8 rounded-xl bg-rose-100 text-rose-700 flex items-center justify-center text-base shrink-0 font-black">⚠️</span>
                <div class="min-w-0">
                    <h3 class="font-black text-sm text-gray-900 leading-tight">
                        Indica qué pasó (1 solo toque)
                    </h3>
                    <span class="text-[11px] text-gray-500 font-semibold block">Factura <span id="val-flash-motivos-numdoc">#---</span></span>
                </div>
            </div>

            <p class="text-xs text-slate-600 text-center font-medium">
                Toca la opción para que quede registrada en auditoría:
            </p>

            <div class="grid grid-cols-1 gap-2 pt-1">
                <button type="button" onclick="enviarValidacionFlash('incorrecto', 'Error en Cantidad')"
                        class="w-full py-3 px-4 rounded-2xl bg-slate-50 hover:bg-amber-50 active:scale-98 border-2 border-slate-200 hover:border-amber-400 text-slate-800 font-black text-xs sm:text-sm flex items-center gap-3 transition cursor-pointer shadow-xs text-left">
                    <span class="text-xl">🔢</span>
                    <div>
                        <div class="font-black">Error en Cantidad</div>
                        <div class="text-[10px] text-slate-500 font-normal">Se marcaron más o menos sándwiches</div>
                    </div>
                </button>

                <button type="button" onclick="enviarValidacionFlash('incorrecto', 'Error en Método de Pago')"
                        class="w-full py-3 px-4 rounded-2xl bg-slate-50 hover:bg-indigo-50 active:scale-98 border-2 border-slate-200 hover:border-indigo-400 text-slate-800 font-black text-xs sm:text-sm flex items-center gap-3 transition cursor-pointer shadow-xs text-left">
                    <span class="text-xl">💳</span>
                    <div>
                        <div class="font-black">Error en Método de Pago</div>
                        <div class="text-[10px] text-slate-500 font-normal">Era Bancolombia, Efectivo u otro</div>
                    </div>
                </button>

                <button type="button" onclick="enviarValidacionFlash('incorrecto', 'Cliente Canceló')"
                        class="w-full py-3 px-4 rounded-2xl bg-slate-50 hover:bg-rose-50 active:scale-98 border-2 border-slate-200 hover:border-rose-400 text-slate-800 font-black text-xs sm:text-sm flex items-center gap-3 transition cursor-pointer shadow-xs text-left">
                    <span class="text-xl">🚫</span>
                    <div>
                        <div class="font-black">Cliente Canceló</div>
                        <div class="text-[10px] text-slate-500 font-normal">El cliente no se llevó el pedido</div>
                    </div>
                </button>

                <button type="button" onclick="enviarValidacionFlash('incorrecto', 'Otro Motivo')"
                        class="w-full py-3 px-4 rounded-2xl bg-slate-50 hover:bg-slate-100 active:scale-98 border-2 border-slate-200 hover:border-slate-400 text-slate-800 font-black text-xs sm:text-sm flex items-center gap-3 transition cursor-pointer shadow-xs text-left">
                    <span class="text-xl">❓</span>
                    <div>
                        <div class="font-black">Otro Motivo</div>
                        <div class="text-[10px] text-slate-500 font-normal">Otro detalle para revisar después</div>
                    </div>
                </button>
            </div>

            <div class="pt-1 text-center">
                <button type="button" onclick="enviarValidacionFlash('incorrecto', 'Sin especificar')"
                        class="text-[11px] text-slate-400 hover:text-slate-600 font-semibold underline cursor-pointer">
                    Cerrar sin especificar motivo
                </button>
            </div>
        </div>

    </div>
</div>"""

if old_modal_val in html:
    html = html.replace(old_modal_val, new_modal_val, 1)
    print("3. Modal validacion HTML updated with 4 one-tap reasons")
else:
    print("WARNING 3: old_modal_val not found")

# 4. Update Validation Modal Functions in JS
old_val_fn = """async function responderValidacionFlash(resultado) {
    const modal = document.getElementById('modal-validacion-flash');
    if (modal) modal.classList.add('hidden');

    if (!ultimaVentaParaValidar) return;

    const itemsDesc = (ultimaVentaParaValidar.items || []).map(i => `${i.cantidad}x ${i.nombre_producto}`).join(', ');
    const payload = {
        pedido_id: ultimaVentaParaValidar.pedido_id,
        numero_documento: ultimaVentaParaValidar.numero_documento,
        resultado: resultado,
        items_resumen: itemsDesc,
        total: ultimaVentaParaValidar.total,
        cajero: cajeroNombre || 'Caja'
    };

    try {
        await fetch(`/api/caja/${SLUG}/validar-factura-flash`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (resultado === 'ok') {
            toast('✅ Venta confirmada correctamente');
        } else {
            toast('⚠️ Marcado como incorrecto para revisión de auditoría', false);
        }
    } catch (e) {
        console.warn('Error guardando validación flash:', e);
    } finally {
        ultimaVentaParaValidar = null;
        renderizarTicketVivoFlash();
    }
}"""

new_val_fn = """function mostrarPasoMotivosFlash() {
    const p1 = document.getElementById('val-flash-paso-confirmacion');
    const p2 = document.getElementById('val-flash-paso-motivos');
    const docSpan = document.getElementById('val-flash-motivos-numdoc');
    if (p1) p1.classList.add('hidden');
    if (p2) p2.classList.remove('hidden');
    if (docSpan && ultimaVentaParaValidar) {
        docSpan.textContent = ultimaVentaParaValidar.numero_documento || ('#' + ultimaVentaParaValidar.pedido_id);
    }
}

async function enviarValidacionFlash(resultado, motivo = '') {
    const modal = document.getElementById('modal-validacion-flash');
    if (modal) modal.classList.add('hidden');

    const p1 = document.getElementById('val-flash-paso-confirmacion');
    const p2 = document.getElementById('val-flash-paso-motivos');
    if (p1) p1.classList.remove('hidden');
    if (p2) p2.classList.add('hidden');

    if (!ultimaVentaParaValidar) return;

    const docStr = ultimaVentaParaValidar.numero_documento || ('#' + ultimaVentaParaValidar.pedido_id);
    const itemsDesc = (ultimaVentaParaValidar.items || []).map(i => `${i.cantidad}x ${i.nombre_producto}`).join(', ');
    const payload = {
        pedido_id: ultimaVentaParaValidar.pedido_id,
        numero_documento: ultimaVentaParaValidar.numero_documento,
        resultado: resultado,
        motivo: motivo,
        items_resumen: itemsDesc,
        total: ultimaVentaParaValidar.total,
        cajero: cajeroNombre || 'Caja'
    };

    try {
        await fetch(`/api/caja/${SLUG}/validar-factura-flash`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (resultado === 'ok') {
            toast(`✅ Venta ${docStr} confirmada correctamente`);
        } else {
            const motivoTxt = motivo ? `: ${motivo}` : '';
            toast(`⚠️ Venta ${docStr} marcada para auditoría${motivoTxt}`, true);
        }
    } catch (e) {
        console.warn('Error guardando validación flash:', e);
    } finally {
        ultimaVentaParaValidar = null;
        renderizarTicketVivoFlash();
    }
}

function responderValidacionFlash(resultado) {
    if (resultado === 'incorrecto') {
        mostrarPasoMotivosFlash();
    } else {
        enviarValidacionFlash('ok', '');
    }
}"""

if old_val_fn in html:
    html = html.replace(old_val_fn, new_val_fn, 1)
    print("4. Validation modal JS functions updated with motivo handling")
else:
    print("WARNING 4: old_val_fn not found")

# 5. Update Live Ticket Header with Rango de Documentos
old_live_hdr = """                <div class="text-[11px] text-center text-slate-600 space-y-0.5">
                    <div id="ticket-vivo-inicio">Inicio Turno: Hoy</div>
                    <div id="ticket-vivo-cierre">Última Venta: Sin ventas aún</div>
                    <div id="ticket-vivo-cajero">Cajero: Administrador</div>
                </div>"""

new_live_hdr = """                <div class="text-[11px] text-center text-slate-600 space-y-0.5">
                    <div id="ticket-vivo-inicio">Inicio Turno: Hoy</div>
                    <div id="ticket-vivo-cierre">Última Venta: Sin ventas aún</div>
                    <div id="ticket-vivo-cajero">Cajero: Administrador</div>
                    <div id="ticket-vivo-rango-docs" class="text-indigo-950 font-black bg-indigo-50 border border-indigo-200/80 rounded-xl py-1 px-2.5 text-center text-[11px] mt-1 shadow-2xs">
                        Facturas del turno: Sin facturas aún
                    </div>
                </div>"""

if old_live_hdr in html:
    html = html.replace(old_live_hdr, new_live_hdr, 1)
    print("5. Live ticket header updated with rango-docs container")
else:
    print("WARNING 5: old_live_hdr not found")

# 6. Update registrarVentaEnSesionFlash and renderizarTicketVivoFlash for tracking documents
old_reg_fn = """function registrarVentaEnSesionFlash(items, pagos, omitidos = []) {
    cargarSesionVentaRapida();
    sessionVentaRapida.ventasCount = (sessionVentaRapida.ventasCount || 0) + 1;"""

new_reg_fn = """function registrarVentaEnSesionFlash(items, pagos, omitidos = [], docNum = null) {
    cargarSesionVentaRapida();
    sessionVentaRapida.ventasCount = (sessionVentaRapida.ventasCount || 0) + 1;
    if (docNum) {
        if (!sessionVentaRapida.documentos) sessionVentaRapida.documentos = [];
        if (!sessionVentaRapida.documentos.includes(docNum)) {
            sessionVentaRapida.documentos.push(docNum);
        }
    }"""

if old_reg_fn in html:
    html = html.replace(old_reg_fn, new_reg_fn, 1)
    print("6. registrarVentaEnSesionFlash updated to track document numbers")
else:
    print("WARNING 6: old_reg_fn not found")

# Update finalizarFacturacionFlashExitosa to pass document number to session
old_fin = """        if (d.ok) {
            registrarVentaEnSesionFlash(items, pagos, []);
            finalizarFacturacionFlashExitosa(d, total, items, pagos);"""

new_fin = """        if (d.ok) {
            const docId = d.numero_documento || (d.pedido_id ? ('#' + d.pedido_id) : null);
            registrarVentaEnSesionFlash(items, pagos, [], docId);
            finalizarFacturacionFlashExitosa(d, total, items, pagos);"""

if old_fin in html:
    html = html.replace(old_fin, new_fin, 1)
    print("7. finalizarFacturacionFlashExitosa call updated with docId")
else:
    print("WARNING 7: old_fin not found")

old_fin_retry = """                    if (d2.ok) {
                        registrarVentaEnSesionFlash(items, pagos, omitidosInfo);
                        finalizarFacturacionFlashExitosa(d2, total, items, pagos, omitidosInfo);"""

new_fin_retry = """                    if (d2.ok) {
                        const docId2 = d2.numero_documento || (d2.pedido_id ? ('#' + d2.pedido_id) : null);
                        registrarVentaEnSesionFlash(items, pagos, omitidosInfo, docId2);
                        finalizarFacturacionFlashExitosa(d2, total, items, pagos, omitidosInfo);"""

if old_fin_retry in html:
    html = html.replace(old_fin_retry, new_fin_retry, 1)
    print("8. finalizarFacturacionFlashExitosa retry updated with docId")
else:
    print("WARNING 8: old_fin_retry not found")

# Update renderizarTicketVivoFlash to compute and display document range
old_render_vivo = """    const tCajero = document.getElementById('ticket-vivo-cajero');
    if (tCajero) tCajero.textContent = `Cajero: ${cajeroNombre || 'Administrador'}`;"""

new_render_vivo = """    const tCajero = document.getElementById('ticket-vivo-cajero');
    if (tCajero) tCajero.textContent = `Cajero: ${cajeroNombre || 'Administrador'}`;

    // Rango de documentos del turno
    const tRangoDocs = document.getElementById('ticket-vivo-rango-docs');
    if (tRangoDocs) {
        const docs = sessionVentaRapida.documentos || [];
        if (!docs.length) {
            tRangoDocs.textContent = 'Facturas del turno: Sin facturas aún';
        } else if (docs.length === 1) {
            tRangoDocs.textContent = `Facturas del turno: Factura ${docs[0]}`;
        } else {
            tRangoDocs.textContent = `Facturas del turno: De la ${docs[0]} a la ${docs[docs.length - 1]}`;
        }
    }"""

if old_render_vivo in html:
    html = html.replace(old_render_vivo, new_render_vivo, 1)
    print("9. renderizarTicketVivoFlash updated with document range")
else:
    print("WARNING 9: old_render_vivo not found")

# 10. Update sincronizarTurnoConServidor to populate sessionVentaRapida.documentos
old_sync_turno = """    sessionVentaRapida.ventasCount = facturas.length;
    sessionVentaRapida.granTotal = servidorResumenCache.gran_total || 0;"""

new_sync_turno = """    sessionVentaRapida.ventasCount = facturas.length;
    sessionVentaRapida.granTotal = servidorResumenCache.gran_total || 0;
    sessionVentaRapida.documentos = facturas.map(f => f.numero_documento || ('#' + f.id)).reverse();"""

if old_sync_turno in html:
    html = html.replace(old_sync_turno, new_sync_turno, 1)
    print("10. sincronizarTurnoConServidor updated with document mapping")
else:
    print("WARNING 10: old_sync_turno not found")

# 11. Update print functions (HTML & Bluetooth) with document range
old_print_html = """            <div class="centro" style="font-size:10px;">Cierre/Impresión: ${ahora}</div>
            <div class="centro" style="font-size:10px;">Cajero: ${cajeroNombre || 'Caja'}</div>"""

new_print_html = """            <div class="centro" style="font-size:10px;">Cierre/Impresión: ${ahora}</div>
            <div class="centro" style="font-size:10px;">Cajero: ${cajeroNombre || 'Caja'}</div>
            <div class="centro" style="font-size:10px; font-weight:bold; margin-top:2px;">
                Facturas del turno: ${(function(){
                    const d = (resumenScope === 'hoy' && srv && srv.facturas) ? srv.facturas.map(f=>f.numero_documento||('#'+f.id)).reverse() : (sess.documentos||[]);
                    if (!d.length) return 'Sin facturas';
                    return d.length === 1 ? `Factura ${d[0]}` : `De la ${d[0]} a la ${d[d.length-1]}`;
                })()}
            </div>"""

if old_print_html in html:
    html = html.replace(old_print_html, new_print_html, 1)
    print("11. HTML print ticket updated with document range")
else:
    print("WARNING 11: old_print_html not found")

old_print_bt = """    builder.line(`Cierre/Impresion: ${ahora}`);
    builder.line(`Cajero: ${cajeroNombre || 'Caja'}`);"""

new_print_bt = """    builder.line(`Cierre/Impresion: ${ahora}`);
    builder.line(`Cajero: ${cajeroNombre || 'Caja'}`);
    const rangoDocsBT = (function(){
        const d = (resumenScope === 'hoy' && srv && srv.facturas) ? srv.facturas.map(f=>f.numero_documento||('#'+f.id)).reverse() : (sess.documentos||[]);
        if (!d.length) return 'Sin facturas';
        return d.length === 1 ? `Factura ${d[0]}` : `De la ${d[0]} a la ${d[d.length-1]}`;
    })();
    builder.line(`Facturas: ${rangoDocsBT}`);"""

if old_print_bt in html:
    html = html.replace(old_print_bt, new_print_bt, 1)
    print("12. Bluetooth print updated with document range")
else:
    print("WARNING 12: old_print_bt not found")

# 13. Update Scope Selector and add Auditoria View in modal-resumen-venta-rapida
old_selector = """        <!-- Selector de Alcance: Turno Actual vs Todo el Día en Servidor -->
        <div class="flex items-center justify-between gap-1.5 p-1 bg-slate-100 rounded-2xl mb-2.5 shrink-0">
            <div class="flex items-center gap-1 flex-1">
                <button type="button" id="btn-resumen-scope-turno" onclick="cambiarAlcanceResumen('turno')"
                        class="flex-1 py-1.5 px-2.5 rounded-xl text-xs font-bold transition shadow-xs bg-white text-indigo-950 cursor-pointer">
                    ⚡ Mi Turno Actual
                </button>
                <button type="button" id="btn-resumen-scope-hoy" onclick="cambiarAlcanceResumen('hoy')"
                        class="flex-1 py-1.5 px-2.5 rounded-xl text-xs font-bold transition text-slate-600 hover:text-slate-900 cursor-pointer">
                    📅 Todo el Día de Hoy
                </button>
            </div>
            <button type="button" onclick="sincronizarResumenDesdeServidor(true)" 
                    class="py-1.5 px-2.5 rounded-xl text-[11px] font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 transition flex items-center gap-1 shrink-0 cursor-pointer active:scale-95"
                    title="Consultar y sincronizar con los pedidos reales guardados en el servidor">
                <span>🔄</span> <span class="hidden sm:inline">Sincronizar</span>
            </button>
        </div>"""

new_selector = """        <!-- Selector de Alcance: Turno Actual vs Todo el Día vs Auditoría de Validaciones -->
        <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 p-1.5 bg-slate-100 rounded-2xl mb-2.5 shrink-0">
            <div class="flex items-center gap-1 flex-1 overflow-x-auto">
                <button type="button" id="btn-resumen-scope-turno" onclick="cambiarAlcanceResumen('turno')"
                        class="flex-1 py-1.5 px-2 rounded-xl text-xs font-bold transition shadow-xs bg-white text-indigo-950 cursor-pointer whitespace-nowrap text-center">
                    ⚡ Mi Turno
                </button>
                <button type="button" id="btn-resumen-scope-hoy" onclick="cambiarAlcanceResumen('hoy')"
                        class="flex-1 py-1.5 px-2 rounded-xl text-xs font-bold transition text-slate-600 hover:text-slate-900 cursor-pointer whitespace-nowrap text-center">
                    📅 Todo el Día
                </button>
                <button type="button" id="btn-resumen-scope-auditoria" onclick="cambiarAlcanceResumen('auditoria')"
                        class="flex-1 py-1.5 px-2 rounded-xl text-xs font-bold transition text-slate-600 hover:text-slate-900 cursor-pointer whitespace-nowrap text-center">
                    🔍 Auditoría Turno
                </button>
            </div>
            <button type="button" onclick="sincronizarResumenDesdeServidor(true)" 
                    class="py-1.5 px-2.5 rounded-xl text-[11px] font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 transition flex items-center justify-center gap-1 shrink-0 cursor-pointer active:scale-95"
                    title="Consultar y sincronizar con los pedidos reales guardados en el servidor">
                <span>🔄</span> <span>Sincronizar</span>
            </button>
        </div>"""

if old_selector in html:
    html = html.replace(old_selector, new_selector, 1)
    print("13. Scope selector updated with Auditoría option")
else:
    print("WARNING 13: old_selector not found")

# 14. Add the Auditoria View Container in modal-resumen-venta-rapida
old_modal_body = """        <div class="overflow-y-auto space-y-4 flex-1 pr-1 custom-scrollbar min-w-0">"""

new_modal_body = """        <!-- Vista de Auditoría Flash para el Administrador / Dueño -->
        <div id="flash-resumen-vista-auditoria" class="hidden overflow-y-auto space-y-3.5 flex-1 pr-1 custom-scrollbar min-w-0">
            <!-- Filtro por fecha -->
            <div class="flex items-center justify-between gap-2 p-2.5 bg-slate-50 border border-slate-200 rounded-2xl text-xs">
                <span class="font-bold text-slate-700 flex items-center gap-1">
                    <span>📅</span> <span>Fecha a auditar:</span>
                </span>
                <div class="flex items-center gap-1.5">
                    <input type="date" id="flash-auditoria-fecha" class="border border-slate-300 rounded-xl px-2 py-1 text-xs font-bold text-slate-800 bg-white" onchange="cargarAuditoriaFlash(this.value)">
                    <button type="button" onclick="cargarAuditoriaFlash()" class="p-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-xl text-xs font-bold cursor-pointer transition">
                        🔄
                    </button>
                </div>
            </div>

            <!-- Resumen Rápido del Turno Auditado -->
            <div class="grid grid-cols-2 gap-2">
                <div class="bg-indigo-50/70 border border-indigo-200/80 rounded-2xl p-3">
                    <span class="text-[10px] uppercase font-black text-indigo-900 block">Horario Turno</span>
                    <span id="auditoria-horario-turno" class="font-mono text-xs font-black text-indigo-950 block mt-0.5">-- : -- a -- : --</span>
                </div>
                <div class="bg-emerald-50/70 border border-emerald-200/80 rounded-2xl p-3">
                    <span class="text-[10px] uppercase font-black text-emerald-900 block">Rango Facturas</span>
                    <span id="auditoria-rango-docs" class="font-mono text-xs font-black text-emerald-950 block mt-0.5 truncate">---</span>
                </div>
                <div class="bg-slate-900 text-white rounded-2xl p-3">
                    <span class="text-[10px] uppercase font-black text-indigo-200 block">Total Recaudado</span>
                    <span id="auditoria-gran-total" class="font-mono text-base font-black block mt-0.5">$0</span>
                </div>
                <div class="bg-indigo-600 text-white rounded-2xl p-3">
                    <span class="text-[10px] uppercase font-black text-indigo-100 block">Sándwiches Vendidos</span>
                    <span id="auditoria-total-unds" class="font-mono text-base font-black block mt-0.5">0 unds</span>
                </div>
            </div>

            <!-- Desglose por Sabor y por Métodos -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <!-- Sándwiches por Sabor -->
                <div class="border border-slate-200 rounded-2xl p-3 bg-white space-y-1.5">
                    <div class="font-black text-slate-800 border-b border-slate-100 pb-1 flex items-center justify-between">
                        <span>🥪 Por Sabor</span>
                        <span id="auditoria-docs-count" class="text-[10px] font-normal text-slate-500">0 ventas</span>
                    </div>
                    <div id="auditoria-prods-lista" class="space-y-1 max-h-36 overflow-y-auto">
                        <div class="text-center text-slate-400 py-2">Sin datos</div>
                    </div>
                </div>

                <!-- Recaudo por Métodos -->
                <div class="border border-slate-200 rounded-2xl p-3 bg-white space-y-1.5">
                    <div class="font-black text-slate-800 border-b border-slate-100 pb-1 flex items-center justify-between">
                        <span>💳 Por Método</span>
                        <span class="text-[10px] font-normal text-slate-500">Recaudo</span>
                    </div>
                    <div id="auditoria-metodos-lista" class="space-y-1 max-h-36 overflow-y-auto">
                        <div class="text-center text-slate-400 py-2">Sin datos</div>
                    </div>
                </div>
            </div>

            <!-- Validaciones Registradas por David -->
            <div class="border border-slate-200 rounded-2xl p-3 bg-white space-y-2">
                <div class="flex items-center justify-between border-b border-slate-100 pb-1.5">
                    <div class="font-black text-xs text-slate-900 flex items-center gap-1.5">
                        <span>📋 Validaciones del Turno</span>
                    </div>
                    <div class="flex items-center gap-1.5 text-[11px] font-black">
                        <span id="auditoria-val-ok-badge" class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">0 OK</span>
                        <span id="auditoria-val-inc-badge" class="px-2 py-0.5 rounded-full bg-rose-100 text-rose-800">0 Inc</span>
                    </div>
                </div>

                <div id="auditoria-validaciones-lista" class="space-y-2 max-h-56 overflow-y-auto text-xs">
                    <div class="text-center text-slate-400 py-4">No hay validaciones registradas en esta fecha</div>
                </div>
            </div>
        </div>

        <div id="flash-resumen-vista-estandar" class="overflow-y-auto space-y-4 flex-1 pr-1 custom-scrollbar min-w-0">"""

if old_modal_body in html:
    html = html.replace(old_modal_body, new_modal_body, 1)
    print("14. Auditoría view container added to modal-resumen-venta-rapida")
else:
    print("WARNING 14: old_modal_body not found")

# 15. Close the #flash-resumen-vista-estandar div
old_close_div = """            <!-- Sección Componentes Omitidos por Faltantes de Inventario -->
            <div class="space-y-1.5 min-w-0">
                <h4 class="text-xs font-black text-rose-800 uppercase tracking-wider flex items-center gap-1.5">
                    <span>🚫</span> <span>Componentes Omitidos por Falta de Stock</span>
                </h4>
                <div id="flash-resumen-omitidos-lista" class="border border-rose-200 bg-rose-50/50 rounded-2xl p-2.5 text-xs text-rose-900 space-y-1.5 max-h-40 overflow-y-auto">
                    <!-- Dinámico -->
                </div>
            </div>
        </div>

        <!-- Acciones Inferiores -->"""

new_close_div = """            <!-- Sección Componentes Omitidos por Faltantes de Inventario -->
            <div class="space-y-1.5 min-w-0">
                <h4 class="text-xs font-black text-rose-800 uppercase tracking-wider flex items-center gap-1.5">
                    <span>🚫</span> <span>Componentes Omitidos por Falta de Stock</span>
                </h4>
                <div id="flash-resumen-omitidos-lista" class="border border-rose-200 bg-rose-50/50 rounded-2xl p-2.5 text-xs text-rose-900 space-y-1.5 max-h-40 overflow-y-auto">
                    <!-- Dinámico -->
                </div>
            </div>
        </div> <!-- Fin flash-resumen-vista-estandar -->

        <!-- Acciones Inferiores -->"""

if old_close_div in html:
    html = html.replace(old_close_div, new_close_div, 1)
    print("15. Div structure closed cleanly")
else:
    print("WARNING 15: old_close_div not found")

# 16. Update cambiarAlcanceResumen to handle 'auditoria'
old_alcance_js = """function cambiarAlcanceResumen(scope) {
    resumenScope = scope;
    const bTurno = document.getElementById('btn-resumen-scope-turno');
    const bHoy = document.getElementById('btn-resumen-scope-hoy');
    
    const claseActivo = 'flex-1 py-1.5 px-2.5 rounded-xl text-xs font-bold transition shadow-xs bg-white text-indigo-950 cursor-pointer';
    const claseInactivo = 'flex-1 py-1.5 px-2.5 rounded-xl text-xs font-bold transition text-slate-600 hover:text-slate-900 cursor-pointer';
    
    if (bTurno) bTurno.className = (scope === 'turno') ? claseActivo : claseInactivo;
    if (bHoy) bHoy.className = (scope === 'hoy') ? claseActivo : claseInactivo;
    
    renderizarModalResumen();
}"""

new_alcance_js = """function cambiarAlcanceResumen(scope) {
    resumenScope = scope;
    const bTurno = document.getElementById('btn-resumen-scope-turno');
    const bHoy = document.getElementById('btn-resumen-scope-hoy');
    const bAudit = document.getElementById('btn-resumen-scope-auditoria');
    
    const claseActivo = 'flex-1 py-1.5 px-2 rounded-xl text-xs font-bold transition shadow-xs bg-white text-indigo-950 cursor-pointer whitespace-nowrap text-center';
    const claseInactivo = 'flex-1 py-1.5 px-2 rounded-xl text-xs font-bold transition text-slate-600 hover:text-slate-900 cursor-pointer whitespace-nowrap text-center';
    
    if (bTurno) bTurno.className = (scope === 'turno') ? claseActivo : claseInactivo;
    if (bHoy) bHoy.className = (scope === 'hoy') ? claseActivo : claseInactivo;
    if (bAudit) bAudit.className = (scope === 'auditoria') ? claseActivo : claseInactivo;
    
    const vEstandar = document.getElementById('flash-resumen-vista-estandar');
    const vAudit = document.getElementById('flash-resumen-vista-auditoria');
    
    if (scope === 'auditoria') {
        if (vEstandar) vEstandar.classList.add('hidden');
        if (vAudit) vAudit.classList.remove('hidden');
        cargarAuditoriaFlash();
    } else {
        if (vAudit) vAudit.classList.add('hidden');
        if (vEstandar) vEstandar.classList.remove('hidden');
        renderizarModalResumen();
    }
}

async function cargarAuditoriaFlash(fechaParam = null) {
    const inputFecha = document.getElementById('flash-auditoria-fecha');
    let fecha = fechaParam;
    if (!fecha) {
        fecha = inputFecha && inputFecha.value ? inputFecha.value : new Date().toISOString().split('T')[0];
    }
    if (inputFecha) inputFecha.value = fecha;

    try {
        const resp = await fetch(`/api/caja/${SLUG}/auditoria-flash?fecha=${fecha}`);
        const d = await resp.json();
        if (!d.ok) {
            toast(d.error || 'Error consultando auditoría', true);
            return;
        }

        const elHorario = document.getElementById('auditoria-horario-turno');
        if (elHorario) {
            elHorario.textContent = (d.hora_inicio && d.hora_fin) ? `${d.hora_inicio} a ${d.hora_fin}` : (d.hora_inicio || 'Sin ventas');
        }

        const elRango = document.getElementById('auditoria-rango-docs');
        if (elRango) {
            elRango.textContent = d.rango_documentos || 'Sin facturas';
        }

        const elGranTot = document.getElementById('auditoria-gran-total');
        if (elGranTot) {
            elGranTot.textContent = '$' + (d.gran_total || 0).toLocaleString('es-CO');
        }

        const elTotalUnds = document.getElementById('auditoria-total-unds');
        if (elTotalUnds) {
            elTotalUnds.textContent = `${d.total_unidades || 0} sándwiches`;
        }

        const elDocsCount = document.getElementById('auditoria-docs-count');
        if (elDocsCount) {
            elDocsCount.textContent = `${d.total_facturas || 0} facturas`;
        }

        // Productos
        const prodsCont = document.getElementById('auditoria-prods-lista');
        if (prodsCont) {
            if (!d.resumen_productos || !d.resumen_productos.length) {
                prodsCont.innerHTML = `<div class="text-center text-slate-400 py-2">Sin ventas</div>`;
            } else {
                prodsCont.innerHTML = d.resumen_productos.map(p => `
                    <div class="flex items-center justify-between py-0.5 border-b border-slate-50 last:border-0">
                        <span class="font-bold text-slate-800">${p.cantidad}x ${p.nombre}</span>
                        <span class="font-mono text-slate-900">$${(p.total||0).toLocaleString('es-CO')}</span>
                    </div>
                `).join('');
            }
        }

        // Métodos
        const metCont = document.getElementById('auditoria-metodos-lista');
        if (metCont) {
            if (!d.resumen_metodos || !d.resumen_metodos.length) {
                metCont.innerHTML = `<div class="text-center text-slate-400 py-2">Sin pagos</div>`;
            } else {
                metCont.innerHTML = d.resumen_metodos.map(m => `
                    <div class="flex items-center justify-between py-0.5 border-b border-slate-50 last:border-0">
                        <span class="text-slate-700">${m.nombre}</span>
                        <span class="font-mono font-bold text-slate-900">$${(m.total||0).toLocaleString('es-CO')}</span>
                    </div>
                `).join('');
            }
        }

        // Badges OK / Inc
        const badgeOk = document.getElementById('auditoria-val-ok-badge');
        const badgeInc = document.getElementById('auditoria-val-inc-badge');
        const vals = d.validaciones_totales || {ok: 0, incorrecto: 0};
        if (badgeOk) badgeOk.textContent = `${vals.ok} OK`;
        if (badgeInc) badgeInc.textContent = `${vals.incorrecto} Con Discrepancia`;

        // Lista de validaciones
        const valLista = document.getElementById('auditoria-validaciones-lista');
        if (valLista) {
            if (!d.validaciones || !d.validaciones.length) {
                valLista.innerHTML = `<div class="text-center text-slate-400 py-3">No hay validaciones registradas en esta fecha</div>`;
            } else {
                valLista.innerHTML = d.validaciones.map(v => {
                    const esOk = (v.resultado === 'ok');
                    const badgeCls = esOk ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-rose-100 text-rose-800 border-rose-200';
                    const icon = esOk ? '✅ OK' : '❌ INCORRECTO';
                    const motivoHtml = (!esOk && v.motivo) ? `<span class="block text-[11px] font-black text-rose-700 mt-0.5">Motivo: ${v.motivo}</span>` : '';
                    return `
                        <div class="p-2.5 rounded-xl border ${badgeCls} bg-white shadow-2xs space-y-1">
                            <div class="flex items-center justify-between">
                                <span class="font-black text-slate-900">${v.numero_documento || ('#' + v.pedido_id)} • ${v.hora || ''}</span>
                                <span class="text-[10px] font-black px-2 py-0.5 rounded-full ${badgeCls} border">${icon}</span>
                            </div>
                            <div class="text-slate-700 text-[11px]">${v.items_resumen || ''}</div>
                            ${motivoHtml}
                            <div class="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-100">
                                <span>Cajero: ${v.cajero || 'Caja'}</span>
                                <span class="font-mono font-bold text-slate-800">$${(v.total||0).toLocaleString('es-CO')}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        }
    } catch (e) {
        console.warn('Error en cargarAuditoriaFlash:', e);
    }
}"""

if old_alcance_js in html:
    html = html.replace(old_alcance_js, new_alcance_js, 1)
    print("16. cambiarAlcanceResumen and cargarAuditoriaFlash implemented")
else:
    print("WARNING 16: old_alcance_js not found")

with open('templates/caja.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Finished patching templates/caja.html successfully!")
