import os

caja_path = r"C:\Users\RAFAEL OLIVARES\Documents\tuctucv2\templates\caja.html"
with open(caja_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. In generarHtmlTicketFactura
target_html_ticket = "${r.cliente ? `<div class=\"centro\" style=\"font-size:11px;\">Cliente: ${r.cliente}</div>` : ''}"
replacement_html_ticket = """${r.cliente ? `<div class=\"centro\" style=\"font-size:11px;\">Cliente: ${r.cliente}</div>` : ''}
            ${(CENTRO_ACTIVO && CENTRO_ACTIVO.imprimir_tipo_entrega !== false && r.entrega) ? `<div class=\"centro\" style=\"font-size:11px;\">Entrega: ${r.entrega}</div>` : ''}"""

if target_html_ticket in code:
    code = code.replace(target_html_ticket, replacement_html_ticket)

# 2. In construirBytesEscPosFactura
target_escpos = "if (r.cliente) builder.line(`Cliente: ${r.cliente}`);\n    builder.separator('-');"
replacement_escpos = """if (r.cliente) builder.line(`Cliente: ${r.cliente}`);
    if (CENTRO_ACTIVO && CENTRO_ACTIVO.imprimir_tipo_entrega !== false && r.entrega) {
        builder.line(`Entrega: ${r.entrega}`);
    }
    builder.separator('-');"""

if target_escpos in code:
    code = code.replace(target_escpos, replacement_escpos)

# 3. In recFlash (Flash sales)
target_flash = "cajero: cajeroNombre,\n                pedido_id: d.pedido_id || null,"
replacement_flash = """cajero: cajeroNombre,
                entrega: (CENTRO_ACTIVO && CENTRO_ACTIVO.imprimir_tipo_entrega !== false) ? (d.entrega_texto || 'Entrega en el local / caja.') : null,
                pedido_id: d.pedido_id || null,"""

if target_flash in code:
    code = code.replace(target_flash, replacement_flash)

# 4. In ultimoRecibo (POS traditional sales)
target_pos = "cajero: cajeroNombre,\n                pedido_id: d.pedido_id || null,"
replacement_pos = """cajero: cajeroNombre,
                entrega: (CENTRO_ACTIVO && CENTRO_ACTIVO.imprimir_tipo_entrega !== false) ? (d.entrega_texto || 'Entrega en el local / caja.') : null,
                pedido_id: d.pedido_id || null,"""

if target_pos in code:
    code = code.replace(target_pos, replacement_pos)

with open(caja_path, "w", encoding="utf-8") as f:
    f.write(code)

print("caja.html updated successfully.")
