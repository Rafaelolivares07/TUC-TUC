# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('templates/caja.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update HTML in #flash-resumen-ticket-en-vivo
old_ticket_html = """                <!-- COMPONENTES OMITIDOS SI LOS HAY -->
                <div id="ticket-vivo-omitidos-bloque" class="hidden">
                    <div class="border-t-2 border-dashed border-slate-300 my-2"></div>
                    <div class="text-center font-black text-[11px] text-rose-800 mb-1">COMPONENTES OMITIDOS POR STOCK</div>
                    <div id="ticket-vivo-omitidos-lista" class="space-y-0.5 text-[10px] text-rose-700"></div>
                </div>"""

new_ticket_html = """                <!-- COMPONENTES OMITIDOS POR STOCK (Siempre visible para confirmación) -->
                <div id="ticket-vivo-omitidos-bloque">
                    <div class="border-t-2 border-dashed border-slate-300 my-2"></div>
                    <div class="text-center font-black text-[11px] text-slate-800 mb-1 flex items-center justify-center gap-1">
                        <span>🚫</span> <span>COMPONENTES OMITIDOS POR STOCK</span>
                    </div>
                    <div id="ticket-vivo-omitidos-lista" class="space-y-0.5 text-[10px]"></div>
                </div>"""

assert old_ticket_html in html, "old_ticket_html not found"
html = html.replace(old_ticket_html, new_ticket_html, 1)
print("1. Ticket vivo HTML updated")

# 2. Update renderizarTicketVivoFlash JS
old_ticket_js = """    // Omitidos
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
    }"""

new_ticket_js = """    // Omitidos
    const omits = Object.values(sess.componentesOmitidos || {});
    const omitLista = document.getElementById('ticket-vivo-omitidos-lista');
    if (omitLista) {
        if (!omits.length) {
            omitLista.innerHTML = `
                <div class="text-center py-1 text-emerald-700 font-semibold flex items-center justify-center gap-1.5">
                    <span class="text-xs">✓</span> <span>No hubo omisiones de ingredientes por falta de stock.</span>
                </div>
            `;
        } else {
            omitLista.innerHTML = omits.map(o => `
                <div class="flex items-center justify-between text-rose-700 py-0.5">
                    <span>* ${o.nombre}</span>
                    <span class="font-bold">${o.cantidadOmitida} omisión${o.cantidadOmitida !== 1 ? 'es' : ''}</span>
                </div>
            `).join('');
        }
    }"""

assert old_ticket_js in html, "old_ticket_js not found"
html = html.replace(old_ticket_js, new_ticket_js, 1)
print("2. renderizarTicketVivoFlash updated to always display omission status")

# 3. Update imprimirResumenVentaRapida (HTML / PDF print)
old_print_omit = """    let omitHtml = '';
    const omits = Object.values(sess.componentesOmitidos || {});
    if (omits.length > 0) {
        omitHtml = `
            <div class="sep"></div>
            <div class="centro" style="font-size:11px; font-weight:bold;">COMPONENTES OMITIDOS POR STOCK</div>
            ${omits.map(o => `<div class="linea" style="font-size:10px; color:#555;"><span>* ${o.nombre}</span><span>${o.cantidadOmitida} veces</span></div>`).join('')}
        `;
    }"""

new_print_omit = """    let omitHtml = '';
    const omits = Object.values(sess.componentesOmitidos || {});
    if (omits.length > 0) {
        omitHtml = `
            <div class="sep"></div>
            <div class="centro" style="font-size:11px; font-weight:bold;">COMPONENTES OMITIDOS POR STOCK</div>
            ${omits.map(o => `<div class="linea" style="font-size:10px; color:#c62828;"><span>* ${o.nombre}</span><span>${o.cantidadOmitida} omisión${o.cantidadOmitida !== 1 ? 'es' : ''}</span></div>`).join('')}
        `;
    } else {
        omitHtml = `
            <div class="sep"></div>
            <div class="centro" style="font-size:11px; font-weight:bold;">COMPONENTES OMITIDOS POR STOCK</div>
            <div class="centro" style="font-size:10px; color:#2e7d32; font-weight:bold; padding:2px 0;">✓ No hubo omisiones de ingredientes por falta de stock.</div>
        `;
    }"""

assert old_print_omit in html, "old_print_omit not found"
html = html.replace(old_print_omit, new_print_omit, 1)
print("3. imprimirResumenVentaRapida updated with omissions in PDF print")

# 4. Update imprimirResumenVentaRapidaBluetooth
old_bt_omit = """    if (omits && omits.length > 0) {
        builder.separator('-');
        builder.align('center').bold(true).line('COMPONENTES OMITIDOS POR STOCK').bold(false);
        for (const o of omits) {
            builder.twoCol(`* ${o.nombre}`, `${o.cantidadOmitida} veces`, 48);
        }
    }"""

new_bt_omit = """    builder.separator('-');
    builder.align('center').bold(true).line('COMPONENTES OMITIDOS POR STOCK').bold(false);
    if (omits && omits.length > 0) {
        for (const o of omits) {
            builder.twoCol(`* ${o.nombre}`, `${o.cantidadOmitida} omis`, 48);
        }
    } else {
        builder.align('center').line('No hubo omisiones por falta de stock');
    }"""

assert old_bt_omit in html, "old_bt_omit not found"
html = html.replace(old_bt_omit, new_bt_omit, 1)
print("4. imprimirResumenVentaRapidaBluetooth updated")

with open('templates/caja.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("All updates to templates/caja.html applied successfully!")
