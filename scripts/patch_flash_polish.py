import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('templates/caja.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update cambiarModoCaja
old_modo = """        if (vistaFlash) {
            vistaFlash.classList.remove('hidden');
            renderProductosFlash();
            actualizarHeaderFlash();
            actualizarTotalesFlash();
        }"""

new_modo = """        if (vistaFlash) {
            vistaFlash.classList.remove('hidden');
            renderProductosFlash();
            actualizarHeaderFlash();
            actualizarTotalesFlash();
            renderizarTicketVivoFlash();
        }"""

if old_modo in html:
    html = html.replace(old_modo, new_modo, 1)
    print("cambiarModoCaja updated to render live ticket")

# 2. Update Bluetooth print summary
old_bt_tot = """    builder.separator('=');
    builder.bold(true).doubleHeight(true).twoCol('TOTAL RECAUDADO:', `$${(granTotal || 0).toLocaleString('es-CO')}`, 48).doubleHeight(false).bold(false);
    builder.twoCol('Transacciones:', `${ventasCount || 0}`, 48);"""

new_bt_tot = """    builder.separator('=');
    builder.bold(true).doubleHeight(true).twoCol('TOTAL RECAUDADO:', `$${(granTotal || 0).toLocaleString('es-CO')}`, 48).doubleHeight(false).bold(false);
    const totalUndsBT = prods.reduce((s, p) => {
        const m = p.desc.match(/^(\\d+)x/);
        return s + (m ? parseInt(m[1]) : 0);
    }, 0);
    builder.bold(true).twoCol('Total Sandwiches / Unds:', `${totalUndsBT} unds`, 48).bold(false);
    builder.twoCol('Transacciones / Clientes:', `${ventasCount || 0}`, 48);"""

if old_bt_tot in html:
    html = html.replace(old_bt_tot, new_bt_tot, 1)
    print("Bluetooth summary updated with total units")

with open('templates/caja.html', 'w', encoding='utf-8') as f:
    f.write(html)
