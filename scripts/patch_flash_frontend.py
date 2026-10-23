import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('templates/caja.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add quick navigation button in the top bar of Venta Rapida
old_top_bar_buttons = """            <div class="flex items-center gap-1 sm:gap-1.5 shrink-0">
                <button type="button" onclick="abrirModalFacturasGuardadas()" """

new_top_bar_buttons = """            <div class="flex items-center gap-1 sm:gap-1.5 shrink-0">
                <button type="button" onclick="hacerScrollAResumenFlash()" 
                        class="bg-amber-100 hover:bg-amber-200 text-amber-950 font-black px-2 sm:px-2.5 py-1.5 rounded-xl text-xs flex items-center gap-1 transition shadow-xs cursor-pointer active:scale-95 shrink-0"
                        title="Ver resumen del turno en vivo al pie de página">
                    <span class="text-sm">📊</span> <span>Resumen (<b id="flash-nav-unds-count">0</b>) ↓</span>
                </button>
                <button type="button" onclick="abrirModalFacturasGuardadas()" """

if old_top_bar_buttons in html:
    html = html.replace(old_top_bar_buttons, new_top_bar_buttons, 1)
    print("Top bar navigation button added successfully")
else:
    print("WARNING: old_top_bar_buttons not found")

# 2. Add the Live Ticket Summary after paso-3-facturar inside pantalla-venta-rapida
old_paso3_end = """            <p id="flash-modo-auto-nota" class="text-[11px] text-gray-400 text-center font-medium mt-1.5">
                ⚡ Modo Ultra Flash activo (guardado instantáneo)
            </p>
        </div>
    </div>
</div>"""

new_paso3_and_ticket = """            <p id="flash-modo-auto-nota" class="text-[11px] text-gray-400 text-center font-medium mt-1.5">
                ⚡ Modo Ultra Flash activo (guardado instantáneo)
            </p>
        </div>

        <!-- ── RESUMEN EN VIVO: IDÉNTICO A LA TIRILLA / PDF IMPRESO ── -->
        <div id="flash-resumen-ticket-en-vivo" class="pt-4 scroll-mt-6">
            <!-- Tarjeta tipo Ticket Térmico -->
            <div class="bg-white border-2 border-slate-300 rounded-3xl p-5 shadow-lg max-w-sm mx-auto font-mono text-slate-900 leading-tight space-y-3.5">
                
                <div class="text-center font-black text-sm tracking-wider uppercase text-slate-900" id="ticket-vivo-tienda-nombre">
                    LOS SANDWICHES DEL PITT
                </div>
                
                <div class="text-center font-black text-xs sm:text-sm text-slate-800">
                    📊 RESUMEN VENTA RÁPIDA (TURNO)
                </div>

                <div class="text-[11px] text-center text-slate-600 space-y-0.5">
                    <div id="ticket-vivo-inicio">Inicio Turno: Hoy</div>
                    <div id="ticket-vivo-cierre">Última Venta: Sin ventas aún</div>
                    <div id="ticket-vivo-cajero">Cajero: Administrador</div>
                </div>

                <div class="border-t-2 border-dashed border-slate-300 my-2"></div>

                <!-- PRODUCTOS VENDIDOS -->
                <div>
                    <div class="text-center font-black text-xs tracking-wider mb-2 text-slate-800">PRODUCTOS VENDIDOS</div>
                    <div id="ticket-vivo-prods-lista" class="space-y-1.5 text-xs">
                        <div class="text-center text-slate-400 py-2">Sin productos vendidos aún</div>
                    </div>
                </div>

                <div class="border-t-2 border-dashed border-slate-300 my-2"></div>

                <!-- RECAUDO POR FORMA DE PAGO -->
                <div>
                    <div class="text-center font-black text-xs tracking-wider mb-2 text-slate-800">RECAUDO POR FORMA DE PAGO</div>
                    <div id="ticket-vivo-pagos-lista" class="space-y-1.5 text-xs">
                        <div class="text-center text-slate-400 py-2">Sin pagos registrados</div>
                    </div>
                </div>

                <div class="border-t-2 border-slate-800 my-2.5"></div>

                <!-- TOTAL RECAUDADO Y TOTALES CLAROS -->
                <div class="flex items-center justify-between font-black text-sm sm:text-base">
                    <span>TOTAL RECAUDADO</span>
                    <span id="ticket-vivo-gran-total" class="font-mono text-base sm:text-lg text-emerald-800">$0</span>
                </div>
                
                <div class="flex items-center justify-between text-xs font-black text-indigo-900 pt-1">
                    <span>Total Sándwiches / Unidades:</span>
                    <span id="ticket-vivo-total-unidades" class="font-mono text-sm bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-lg text-indigo-950">0</span>
                </div>

                <div class="flex items-center justify-between text-[11px] text-slate-600">
                    <span>Total Ventas / Transacciones:</span>
                    <span id="ticket-vivo-total-transacciones" class="font-mono font-bold">0</span>
                </div>

                <!-- COMPONENTES OMITIDOS SI LOS HAY -->
                <div id="ticket-vivo-omitidos-bloque" class="hidden">
                    <div class="border-t-2 border-dashed border-slate-300 my-2"></div>
                    <div class="text-center font-black text-[11px] text-rose-800 mb-1">COMPONENTES OMITIDOS POR STOCK</div>
                    <div id="ticket-vivo-omitidos-lista" class="space-y-0.5 text-[10px] text-rose-700"></div>
                </div>

                <div class="border-t-2 border-dashed border-slate-300 my-2"></div>
                <div class="text-center text-[10px] text-slate-500 font-bold">*** FIN RESUMEN ***</div>

                <!-- Botón Volver Arriba a Facturar -->
                <div class="pt-3">
                    <button type="button" onclick="hacerScrollAFacturacionFlash()"
                            class="w-full py-3.5 px-4 rounded-2xl bg-indigo-600 hover:bg-indigo-700 active:scale-98 text-white font-black text-xs sm:text-sm flex items-center justify-center gap-2 shadow-md transition cursor-pointer">
                        <span>⬆️</span> <span>Volver Arriba a Facturar</span>
                    </button>
                </div>
            </div>
        </div>

    </div>
</div>"""

if old_paso3_end in html:
    html = html.replace(old_paso3_end, new_paso3_and_ticket, 1)
    print("Live Ticket Summary inserted successfully")
else:
    print("WARNING: old_paso3_end not found")

# 3. Add Modal de Validación Post-Facturación Flash
modal_validacion_html = """
<!-- Modal de Validación Post-Facturación Flash -->
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
</div>
"""

idx_resumen_modal = html.find('<!-- Modal: Resumen y Cierre de Turno de Venta Rápida -->')
if idx_resumen_modal != -1 and 'id="modal-validacion-flash"' not in html:
    html = html[:idx_resumen_modal] + modal_validacion_html + "\n" + html[idx_resumen_modal:]
    print("Modal de validacion flash added successfully")
else:
    print("WARNING: idx_resumen_modal not found or modal-validacion-flash already present")

# 4. Update JavaScript:
# A) renderProductosFlash with stable IDs and card template
old_render_prods = """    cont.innerHTML = lista.map(p => {
        const cant = pedidoFlash[p.id] || 0;
        const selClass = cant > 0 
            ? 'border-emerald-500 bg-emerald-50/50 shadow-md ring-2 ring-emerald-400/40' 
            : 'border-gray-200 hover:border-gray-300 bg-white shadow-xs';
        const formattedPrice = '$' + (p.precio || 0).toLocaleString('es-CO');

        return `
            <div onclick="tocarProductoFlash(${p.id})"
                 class="flash-card relative p-3.5 sm:p-4 rounded-3xl border-2 ${selClass} flex flex-col justify-between min-h-[118px] sm:min-h-[132px] cursor-pointer transition select-none">
                
                <!-- Badge de Cantidad -->
                ${cant > 0 ? `
                    <div class="absolute -top-2.5 -right-2 bg-emerald-600 text-white font-black text-xs px-2.5 py-0.5 rounded-full shadow-md flex items-center gap-1 animate-in zoom-in duration-100">
                        <span>x${cant}</span>
                    </div>
                ` : ''}

                <!-- Nombre y Stock -->
                <div class="min-w-0 flex-1 mb-1">
                    <h3 class="font-black text-gray-900 text-xs sm:text-sm md:text-base leading-tight break-words">${p.nombre}</h3>
                    ${p.stock !== undefined && p.stock !== null && p.stock < 10 ? `
                        <span class="text-[10px] text-amber-600 font-bold block mt-0.5">Stock: ${p.stock}</span>
                    ` : ''}
                </div>

                <!-- Precio y Botón Restar -->
                <div class="flex items-center justify-between mt-auto pt-1.5 border-t border-gray-100/90">
                    <span class="text-sm sm:text-base font-black font-mono text-emerald-700">${formattedPrice}</span>
                    ${cant > 0 ? `
                        <button type="button" onclick="event.stopPropagation(); cambiarCantidadFlash(${p.id}, -1)" 
                                class="w-7 h-7 bg-red-100 hover:bg-red-200 text-red-700 rounded-full font-black text-sm flex items-center justify-center transition active:scale-90 shadow-xs"
                                title="Restar uno">
                            −
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');"""

new_render_prods = """    cont.innerHTML = lista.map(p => {
        const cant = pedidoFlash[p.id] || 0;
        const selClass = cant > 0 
            ? 'border-emerald-500 bg-emerald-50/50 shadow-md ring-2 ring-emerald-400/40' 
            : 'border-gray-200 hover:border-gray-300 bg-white shadow-xs';
        const formattedPrice = '$' + (p.precio || 0).toLocaleString('es-CO');

        return `
            <div id="flash-card-${p.id}" onclick="tocarProductoFlash(${p.id})"
                 class="flash-card relative p-3.5 sm:p-4 rounded-3xl border-2 ${selClass} flex flex-col justify-between min-h-[118px] sm:min-h-[132px] cursor-pointer transition select-none">
                
                <!-- Badge de Cantidad (persistente en DOM para cero toques perdidos) -->
                <div id="flash-badge-${p.id}" class="absolute -top-2.5 -right-2 bg-emerald-600 text-white font-black text-xs sm:text-sm px-2.5 py-0.5 rounded-full shadow-md flex items-center gap-1 ${cant > 0 ? '' : 'hidden'}">
                    <span>x${cant}</span>
                </div>

                <!-- Nombre y Stock -->
                <div class="min-w-0 flex-1 mb-1">
                    <h3 class="font-black text-gray-900 text-xs sm:text-sm md:text-base leading-tight break-words">${p.nombre}</h3>
                    ${p.stock !== undefined && p.stock !== null && p.stock < 10 ? `
                        <span class="text-[10px] text-amber-600 font-bold block mt-0.5">Stock: ${p.stock}</span>
                    ` : ''}
                </div>

                <!-- Precio y Botón Restar -->
                <div class="flex items-center justify-between mt-auto pt-1.5 border-t border-gray-100/90">
                    <span class="text-sm sm:text-base font-black font-mono text-emerald-700">${formattedPrice}</span>
                    <button type="button" id="flash-btn-minus-${p.id}" onclick="event.stopPropagation(); cambiarCantidadFlash(${p.id}, -1)" 
                            class="w-7 h-7 bg-red-100 hover:bg-red-200 text-red-700 rounded-full font-black text-sm flex items-center justify-center transition active:scale-90 shadow-xs ${cant > 0 ? '' : 'hidden'}"
                            title="Restar uno">
                        −
                    </button>
                </div>
            </div>
        `;
    }).join('');"""

if old_render_prods in html:
    html = html.replace(old_render_prods, new_render_prods, 1)
    print("renderProductosFlash updated with persistent card elements")
else:
    print("WARNING: old_render_prods not found")

# B) tocarProductoFlash and cambiarCantidadFlash with in-place DOM updates (NO DROPPED TAPS)
old_tocar_funcs = """function tocarProductoFlash(prodId) {
    pedidoFlash[prodId] = (pedidoFlash[prodId] || 0) + 1;
    renderProductosFlash();
    actualizarTotalesFlash();
}

function cambiarCantidadFlash(prodId, delta) {
    const act = (pedidoFlash[prodId] || 0) + delta;
    if (act <= 0) {
        delete pedidoFlash[prodId];
    } else {
        pedidoFlash[prodId] = act;
    }
    renderProductosFlash();
    actualizarTotalesFlash();
}"""

new_tocar_funcs = """function tocarProductoFlash(prodId) {
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

if old_tocar_funcs in html:
    html = html.replace(old_tocar_funcs, new_tocar_funcs, 1)
    print("tocarProductoFlash updated for zero-latency tapping")
else:
    print("WARNING: old_tocar_funcs not found")

# C) Logic for Live Ticket Summary, Navigation and Validation Modal
extra_flash_js = """
// ── NAVEGACIÓN Y RESUMEN EN VIVO VENTA RÁPIDA (FORMATO TIRILLA / PDF) ────────

function hacerScrollAResumenFlash() {
    renderizarTicketVivoFlash();
    const el = document.getElementById('flash-resumen-ticket-en-vivo');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function hacerScrollAFacturacionFlash() {
    const el = document.getElementById('paso-1-productos');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderizarTicketVivoFlash() {
    cargarSesionVentaRapida();
    const sess = sessionVentaRapida;
    const ahora = new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
    
    const tNombre = document.getElementById('ticket-vivo-tienda-nombre');
    if (tNombre) tNombre.textContent = TIENDA_NOMBRE || 'LOS SANDWICHES DEL PITT';

    const tInicio = document.getElementById('ticket-vivo-inicio');
    if (tInicio) {
        const d = new Date(sess.fechaInicio);
        tInicio.textContent = `Inicio Turno: ${d.toLocaleDateString('es-CO')} ${d.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })}`;
    }

    const tCierre = document.getElementById('ticket-vivo-cierre');
    if (tCierre) {
        tCierre.textContent = sess.ventasCount > 0 ? `Última Venta: Hoy ${ahora}` : 'Última Venta: Sin ventas aún';
    }

    const tCajero = document.getElementById('ticket-vivo-cajero');
    if (tCajero) tCajero.textContent = `Cajero: ${cajeroNombre || 'Administrador'}`;

    // Productos vendidos
    const prodsList = Object.values(sess.productos || {});
    let totalUnidades = 0;
    const prodsCont = document.getElementById('ticket-vivo-prods-lista');
    if (prodsCont) {
        if (!prodsList.length) {
            prodsCont.innerHTML = `<div class="text-center text-slate-400 py-2">Sin ventas registradas en este turno</div>`;
        } else {
            prodsCont.innerHTML = prodsList.map(p => {
                totalUnidades += (p.cantidad || 0);
                return `
                    <div class="flex items-center justify-between text-xs py-0.5">
                        <span class="font-bold text-slate-800">${p.cantidad}x ${p.nombre}</span>
                        <span class="font-mono font-black text-slate-900">$${(p.total || 0).toLocaleString('es-CO')}</span>
                    </div>
                `;
            }).join('');
        }
    }

    // Pagos
    const pagosList = Object.values(sess.metodosPago || {});
    const pagosCont = document.getElementById('ticket-vivo-pagos-lista');
    if (pagosCont) {
        if (!pagosList.length) {
            pagosCont.innerHTML = `<div class="text-center text-slate-400 py-2">Sin pagos registrados</div>`;
        } else {
            pagosCont.innerHTML = pagosList.map(m => `
                <div class="flex items-center justify-between text-xs py-0.5">
                    <span class="text-slate-700">${m.nombre}</span>
                    <span class="font-mono font-bold text-slate-900">$${(m.total || 0).toLocaleString('es-CO')}</span>
                </div>
            `).join('');
        }
    }

    // Totales
    const elGranTotal = document.getElementById('ticket-vivo-gran-total');
    if (elGranTotal) elGranTotal.textContent = '$' + (sess.granTotal || 0).toLocaleString('es-CO');

    const elTotalUnds = document.getElementById('ticket-vivo-total-unidades');
    if (elTotalUnds) elTotalUnds.textContent = `${totalUnidades} sándwiches`;

    const elTotalTrans = document.getElementById('ticket-vivo-total-transacciones');
    if (elTotalTrans) elTotalTrans.textContent = sess.ventasCount || 0;

    // Badge en navegación superior
    const navBadge = document.getElementById('flash-nav-unds-count');
    if (navBadge) navBadge.textContent = totalUnidades;

    // Omitidos
    const omits = Object.values(sess.componentesOmitidos || {});
    const omitBloque = document.getElementById('ticket-vivo-omitidos-bloque');
    const omitLista = document.getElementById('ticket-vivo-omitidos-lista');
    if (omitBloque && omitLista) {
        if (!omits.length) {
            omitBloque.classList.add('hidden');
        } else {
            omitBloque.classList.remove('hidden');
            omitLista.innerHTML = omits.map(o => `
                <div class="flex items-center justify-between">
                    <span>* ${o.nombre}</span>
                    <span class="font-bold">${o.cantidadOmitida} veces</span>
                </div>
            `).join('');
        }
    }
}

// ── MODAL VALIDACIÓN POST-FACTURACIÓN FLASH ──────────────────────────────────
let ultimaVentaParaValidar = null;

function abrirModalValidacionFlash(d, total, items, pagos) {
    ultimaVentaParaValidar = {
        pedido_id: d.pedido_id || null,
        numero_documento: d.numero_documento || (d.pedido_id ? '#' + d.pedido_id : '---'),
        total: total,
        items: items,
        pagos: pagos,
        hora: new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
    };

    const docEl = document.getElementById('val-flash-num-doc');
    if (docEl) docEl.textContent = ultimaVentaParaValidar.numero_documento;

    const horaEl = document.getElementById('val-flash-hora');
    if (horaEl) horaEl.textContent = `Hora: ${ultimaVentaParaValidar.hora}`;

    const itemsCont = document.getElementById('val-flash-items-lista');
    let totalUnds = 0;
    if (itemsCont) {
        itemsCont.innerHTML = items.map(it => {
            const cant = it.cantidad || 1;
            totalUnds += cant;
            return `
                <div class="flex items-center justify-between py-0.5">
                    <span class="truncate">${cant}x ${it.nombre_producto}</span>
                    <span class="text-slate-600 font-bold ml-2">$${((it.precio_unitario || 0) * cant).toLocaleString('es-CO')}</span>
                </div>
            `;
        }).join('');
    }

    const undsEl = document.getElementById('val-flash-total-unds');
    if (undsEl) undsEl.textContent = `${totalUnds} sándwich${totalUnds !== 1 ? 'es' : ''}`;

    const totalEl = document.getElementById('val-flash-total-monto');
    if (totalEl) totalEl.textContent = '$' + (total || 0).toLocaleString('es-CO');

    const metEl = document.getElementById('val-flash-metodo-pago');
    if (metEl) {
        metEl.textContent = pagos.length ? pagos.map(p => p.nombre).join(' + ') : 'Efectivo';
    }

    const modal = document.getElementById('modal-validacion-flash');
    if (modal) modal.classList.remove('hidden');
}

async function responderValidacionFlash(resultado) {
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
}
"""

idx_finalizar = html.find('function finalizarFacturacionFlashExitosa(')
if idx_finalizar != -1 and 'renderizarTicketVivoFlash' not in html:
    html = html[:idx_finalizar] + extra_flash_js + "\n" + html[idx_finalizar:]
    print("Extra Flash JS functions inserted successfully")
else:
    print("WARNING: idx_finalizar not found or extra_flash_js already present")

# D) In finalizarFacturacionFlashExitosa, call abrirModalValidacionFlash and renderizarTicketVivoFlash
old_call_end = """    reiniciarPedidoFlash();
    if (btn) btn.disabled = true;
    if (label) label.textContent = 'FACTURAR ($0)';

    const elPaso1 = document.getElementById('paso-1-productos');
    if (elPaso1) elPaso1.scrollIntoView({ behavior: 'smooth', block: 'start' });

    cargarProductos();
    cargarTiposDocumento();
}"""

new_call_end = """    reiniciarPedidoFlash();
    if (btn) btn.disabled = true;
    if (label) label.textContent = 'FACTURAR ($0)';

    const elPaso1 = document.getElementById('paso-1-productos');
    if (elPaso1) elPaso1.scrollIntoView({ behavior: 'smooth', block: 'start' });

    renderizarTicketVivoFlash();
    abrirModalValidacionFlash(d, total, items, pagos);

    cargarProductos();
    cargarTiposDocumento();
}"""

if old_call_end in html:
    html = html.replace(old_call_end, new_call_end, 1)
    print("finalizarFacturacionFlashExitosa hooked with validation modal successfully")
else:
    print("WARNING: old_call_end not found")

# E) Also update imprimirResumenVentaRapida to print Total Unidades Vendidas
old_print_total = """            <div class="linea total-line">
                <span>TOTAL RECAUDADO</span>
                <span>$${(granTotal || 0).toLocaleString('es-CO')}</span>
            </div>
            <div class="linea" style="font-size:11px; margin-top:2px;">
                <span>Total Ventas / Transacciones:</span>
                <span>${ventasCount || 0}</span>
            </div>"""

new_print_total = """            <div class="linea total-line">
                <span>TOTAL RECAUDADO</span>
                <span>$${(granTotal || 0).toLocaleString('es-CO')}</span>
            </div>
            <div class="linea" style="font-size:12px; font-weight:bold; margin-top:3px;">
                <span>Total Sándwiches / Unidades:</span>
                <span>${Object.values(sess.productos || {}).reduce((s, p) => s + (p.cantidad || 0), 0)} unds</span>
            </div>
            <div class="linea" style="font-size:11px; margin-top:2px; color:#555;">
                <span>Total Ventas / Transacciones:</span>
                <span>${ventasCount || 0}</span>
            </div>"""

if old_print_total in html:
    html = html.replace(old_print_total, new_print_total, 1)
    print("imprimirResumenVentaRapida updated with Total Unidades Vendidas")
else:
    print("WARNING: old_print_total not found")

with open('templates/caja.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Patch applied to caja.html successfully!")
