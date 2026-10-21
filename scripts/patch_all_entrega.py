import os
import re

BASE_DIR = r"C:\Users\RAFAEL OLIVARES\Documents\tuctucv2"

# ── 1. PATCH app/blueprints/tiendas.py ──────────────────────────────────────────
t_path = os.path.join(BASE_DIR, "app", "blueprints", "tiendas.py")
with open(t_path, "r", encoding="utf-8") as f:
    t_code = f.read()

# Replace _telegram_detalle_entrega_tienda
old_fn = re.compile(r'def _telegram_detalle_entrega_tienda\(tipo_entrega, direccion, nombre_cajero\):.*?return f"\{tipo_entrega or \'Pedido\'\}: \{direccion or \'N/A\'\}"', re.DOTALL)
new_fn = '''def _telegram_detalle_entrega_tienda(tipo_entrega, direccion, nombre_cajero, textos_config=None, imprimir_entrega=True):
    if not imprimir_entrega:
        return ""
    cfg = textos_config or {}
    te = (tipo_entrega or 'caja').strip().lower()
    if te == 'domicilio':
        base = (cfg.get('domicilio') or {}).get('texto') or "Domicilio. Llevar a:"
        return f"{base} {direccion or 'direccion pendiente'}"
    if te == 'recoger':
        return (cfg.get('recoger') or {}).get('texto') or "Cliente recoge en el local."
    if te == 'caja':
        caja_cfg = cfg.get('caja') or {}
        base = caja_cfg.get('texto') or "Entrega en el local / caja."
        incluir_cajero = caja_cfg.get('incluir_cajero', True)
        if incluir_cajero and nombre_cajero:
            return f"{base}\\nAtendio: {nombre_cajero}"
        return base
    if te == 'mesa':
        base = (cfg.get('mesa') or {}).get('texto') or "Consumo en mesa:"
        return f"{base} {direccion or 'N/A'}"
    return f"{tipo_entrega or 'Pedido'}: {direccion or 'N/A'}"'''

if old_fn.search(t_code):
    t_code = old_fn.sub(new_fn, t_code)

# In api_tienda_pedido_crear, handle imprimir_tipo_entrega and textos_entrega
old_cu_select = '"SELECT codigo, nombre, tipo, telegram_chat_id FROM centros_utilidad WHERE id = %s"'
new_cu_select = '"SELECT codigo, nombre, tipo, telegram_chat_id, COALESCE(imprimir_tipo_entrega, TRUE) AS imprimir_tipo_entrega FROM centros_utilidad WHERE id = %s"'
if old_cu_select in t_code:
    t_code = t_code.replace(old_cu_select, new_cu_select)

old_notif_block = """        chats_a_notificar = set()
        if chat_id:
            chats_a_notificar.add(str(chat_id).strip())
        if cu_chat_id:
            chats_a_notificar.add(str(cu_chat_id).strip())

        if chats_a_notificar:
            items_txt = '\\n'.join([f"  {it['cantidad']}x {it['nombre_producto']} - ${it['precio_unitario'] * it['cantidad']:,.0f}" for it in items_validos])
            entrega = _telegram_detalle_entrega_tienda(tipo_entrega, direccion_cliente, nombre_cajero)
            pagos_txt = _telegram_resumen_pagos(pagos_validos, metodo_pago, total)
            cliente_txt = nombre_cliente or nombre_cajero or 'Cliente en local'
            telefono_txt = telefono_cliente or 'Sin telefono'
            cu_line = f"🏢 <b>Sede / Centro:</b> {cu_info}\\n" if cu_info else ""
            doc_line = f" ({numero_documento})" if numero_documento else ""
            msg = (
                f"🛒 <b>Nuevo pedido en {tienda['nombre']}</b>\\n"
                f"{cu_line}"
                f"🧾 Pedido #{pedido_id}{doc_line}\\n"
                f"👤 {cliente_txt} - {telefono_txt}\\n"
                f"📦 Entrega: {entrega}\\n"
                f"💳 Pago elegido: {pagos_txt}\\n\\n"
                f"{items_txt}\\n\\n"
                f"Subtotal productos: ${subtotal_productos:,.0f}\\n"
                f"Domicilio: {'por confirmar' if domicilio_estado == 'por_confirmar' else '$' + format(float(valor_domicilio or 0), ',.0f')}\\n"
                f"💰 Total: ${total:,.0f}"
            )"""

new_notif_block = """        imprimir_entrega = True
        try:
            if cu_row and cu_row.get('imprimir_tipo_entrega') is not None:
                imprimir_entrega = bool(cu_row['imprimir_tipo_entrega'])
        except Exception:
            imprimir_entrega = True

        textos_cfg = {}
        try:
            if negocio.get('tercero_id'):
                cn_row = conn.execute("SELECT textos_entrega FROM config_negocio WHERE tercero_id = %s", (negocio['tercero_id'],)).fetchone()
                if cn_row and cn_row['textos_entrega']:
                    textos_cfg = cn_row['textos_entrega'] if isinstance(cn_row['textos_entrega'], dict) else json.loads(cn_row['textos_entrega'])
        except Exception:
            textos_cfg = {}

        entrega = _telegram_detalle_entrega_tienda(tipo_entrega, direccion_cliente, nombre_cajero, textos_config=textos_cfg, imprimir_entrega=imprimir_entrega)

        chats_a_notificar = set()
        if chat_id:
            chats_a_notificar.add(str(chat_id).strip())
        if cu_chat_id:
            chats_a_notificar.add(str(cu_chat_id).strip())

        if chats_a_notificar:
            items_txt = '\\n'.join([f"  {it['cantidad']}x {it['nombre_producto']} - ${it['precio_unitario'] * it['cantidad']:,.0f}" for it in items_validos])
            pagos_txt = _telegram_resumen_pagos(pagos_validos, metodo_pago, total)
            cliente_txt = nombre_cliente or nombre_cajero or 'Cliente en local'
            telefono_txt = telefono_cliente or 'Sin telefono'
            cu_line = f"🏢 <b>Sede / Centro:</b> {cu_info}\\n" if cu_info else ""
            doc_line = f" ({numero_documento})" if numero_documento else ""
            entrega_line = f"📦 Entrega: {entrega}\\n" if (imprimir_entrega and entrega) else ""
            msg = (
                f"🛒 <b>Nuevo pedido en {tienda['nombre']}</b>\\n"
                f"{cu_line}"
                f"🧾 Pedido #{pedido_id}{doc_line}\\n"
                f"👤 {cliente_txt} - {telefono_txt}\\n"
                f"{entrega_line}"
                f"💳 Pago elegido: {pagos_txt}\\n\\n"
                f"{items_txt}\\n\\n"
                f"Subtotal productos: ${subtotal_productos:,.0f}\\n"
                f"Domicilio: {'por confirmar' if domicilio_estado == 'por_confirmar' else '$' + format(float(valor_domicilio or 0), ',.0f')}\\n"
                f"💰 Total: ${total:,.0f}"
            )"""

if old_notif_block in t_code:
    t_code = t_code.replace(old_notif_block, new_notif_block)

# In api_tienda_pedido_crear return dict, include entrega_texto
old_ret = "return jsonify({'ok': True, 'pedido_id': pedido_id, 'total': total, 'numero_documento': numero_documento})"
new_ret = "return jsonify({'ok': True, 'pedido_id': pedido_id, 'total': total, 'numero_documento': numero_documento, 'entrega_texto': entrega if (imprimir_entrega and entrega) else None})"
if old_ret in t_code:
    t_code = t_code.replace(old_ret, new_ret)

with open(t_path, "w", encoding="utf-8") as f:
    f.write(t_code)
print("tiendas.py updated.")

# ── 2. PATCH app/blueprints/restaurantes.py ─────────────────────────────────────
r_path = os.path.join(BASE_DIR, "app", "blueprints", "restaurantes.py")
with open(r_path, "r", encoding="utf-8") as f:
    r_code = f.read()

old_r_fn = re.compile(r'def _telegram_detalle_entrega_restaurante\(tipo_entrega, direccion, mesa\):.*?return f"\{tipo_entrega or \'Pedido\'\}: \{direccion or mesa or \'N/A\'\}"', re.DOTALL)
new_r_fn = '''def _telegram_detalle_entrega_restaurante(tipo_entrega, direccion, mesa, nombre_cajero=None, textos_config=None, imprimir_entrega=True):
    if not imprimir_entrega:
        return ""
    cfg = textos_config or {}
    te = (tipo_entrega or 'caja').strip().lower()
    if te == 'domicilio':
        base = (cfg.get('domicilio') or {}).get('texto') or "Domicilio. Llevar a:"
        return f"{base} {direccion or 'direccion pendiente'}"
    if te == 'recoger':
        return (cfg.get('recoger') or {}).get('texto') or "Cliente recoge en el local."
    if te == 'caja':
        caja_cfg = cfg.get('caja') or {}
        base = caja_cfg.get('texto') or "Entrega en el local / caja."
        incluir_cajero = caja_cfg.get('incluir_cajero', True)
        if incluir_cajero and nombre_cajero:
            return f"{base}\\nAtendio: {nombre_cajero}"
        return base
    if te == 'mesa':
        base = (cfg.get('mesa') or {}).get('texto') or "Consumo en mesa:"
        return f"{base} {mesa or 'mesa sin nombre'}"
    return f"{tipo_entrega or 'Pedido'}: {direccion or mesa or 'N/A'}"'''

if old_r_fn.search(r_code):
    r_code = old_r_fn.sub(new_r_fn, r_code)

old_r_cu_select = '"SELECT codigo, nombre, tipo, telegram_chat_id FROM centros_utilidad WHERE id = %s"'
new_r_cu_select = '"SELECT codigo, nombre, tipo, telegram_chat_id, COALESCE(imprimir_tipo_entrega, TRUE) AS imprimir_tipo_entrega FROM centros_utilidad WHERE id = %s"'
if old_r_cu_select in r_code:
    r_code = r_code.replace(old_r_cu_select, new_r_cu_select)

old_r_msg_block = """    items_txt = '\\n'.join(f"  {item}" for item in items) or '  Pedido registrado'
    entrega = _telegram_detalle_entrega_restaurante(tipo_entrega, direccion, mesa)
    pago_txt = _telegram_label_pago(metodo_pago)
    if (metodo_pago or '').lower() == 'contraentrega':
        pago_txt += "\\n⚠️ Contraentrega: cobrar efectivo al entregar."

    cu_line = f"🏢 <b>Sede / Centro:</b> {cu_info}\\n" if cu_info else ""
    msg = (
        f"🍽️ <b>Nuevo pedido en {nombre_rest}</b>\\n"
        f"{cu_line}"
        f"🧾 Pedido #{pedido_id}\\n"
        f"👤 {cliente or 'Cliente'} - {telefono or 'Sin telefono'}\\n"
        f"📦 Entrega: {entrega}\\n"
        f"💳 Pago elegido: {pago_txt}\\n\\n"
        f"{items_txt}\\n\\n"
        f"💰 Total: ${total:,.0f}"
    )"""

new_r_msg_block = """    imprimir_entrega = True
    try:
        if cu_row and cu_row.get('imprimir_tipo_entrega') is not None:
            imprimir_entrega = bool(cu_row['imprimir_tipo_entrega'])
    except Exception:
        imprimir_entrega = True

    textos_cfg = {}
    try:
        t_id = rest['tercero_id'] if rest and hasattr(rest, 'get') else None
        if t_id:
            cn_row = conn.execute("SELECT textos_entrega FROM config_negocio WHERE tercero_id = %s", (t_id,)).fetchone()
            if cn_row and cn_row['textos_entrega']:
                textos_cfg = cn_row['textos_entrega'] if isinstance(cn_row['textos_entrega'], dict) else json.loads(cn_row['textos_entrega'])
    except Exception:
        textos_cfg = {}

    items_txt = '\\n'.join(f"  {item}" for item in items) or '  Pedido registrado'
    entrega = _telegram_detalle_entrega_restaurante(tipo_entrega, direccion, mesa, textos_config=textos_cfg, imprimir_entrega=imprimir_entrega)
    pago_txt = _telegram_label_pago(metodo_pago)
    if (metodo_pago or '').lower() == 'contraentrega':
        pago_txt += "\\n⚠️ Contraentrega: cobrar efectivo al entregar."

    cu_line = f"🏢 <b>Sede / Centro:</b> {cu_info}\\n" if cu_info else ""
    entrega_line = f"📦 Entrega: {entrega}\\n" if (imprimir_entrega and entrega) else ""
    msg = (
        f"🍽️ <b>Nuevo pedido en {nombre_rest}</b>\\n"
        f"{cu_line}"
        f"🧾 Pedido #{pedido_id}\\n"
        f"👤 {cliente or 'Cliente'} - {telefono or 'Sin telefono'}\\n"
        f"{entrega_line}"
        f"💳 Pago elegido: {pago_txt}\\n\\n"
        f"{items_txt}\\n\\n"
        f"💰 Total: ${total:,.0f}"
    )"""

if old_r_msg_block in r_code:
    r_code = r_code.replace(old_r_msg_block, new_r_msg_block)

with open(r_path, "w", encoding="utf-8") as f:
    f.write(r_code)
print("restaurantes.py updated.")

# ── 3. PATCH app/blueprints/inventarios.py ──────────────────────────────────────
inv_path = os.path.join(BASE_DIR, "app", "blueprints", "inventarios.py")
with open(inv_path, "r", encoding="utf-8") as f:
    inv_code = f.read()

old_inv_sql = """        centros_db = conn.execute(\"\"\"
            SELECT id, codigo, nombre, tipo, direccion, telefono, imagen_url, color_badge, activo, telegram_chat_id
            FROM centros_utilidad"""

new_inv_sql = """        centros_db = conn.execute(\"\"\"
            SELECT id, codigo, nombre, tipo, direccion, telefono, imagen_url, color_badge, activo, telegram_chat_id,
                   COALESCE(imprimir_tipo_entrega, TRUE) AS imprimir_tipo_entrega
            FROM centros_utilidad"""

if old_inv_sql in inv_code:
    inv_code = inv_code.replace(old_inv_sql, new_inv_sql)

with open(inv_path, "w", encoding="utf-8") as f:
    f.write(inv_code)
print("inventarios.py updated.")
