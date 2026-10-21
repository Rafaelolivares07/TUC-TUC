import os
import re

BASE_DIR = r"C:\Users\RAFAEL OLIVARES\Documents\tuctucv2"

# 1. Update app/blueprints/negocios.py
neg_path = os.path.join(BASE_DIR, "app", "blueprints", "negocios.py")
with open(neg_path, "r", encoding="utf-8") as f:
    neg_code = f.read()

# Make sure init_config_negocio has texts_entrega and imprimir_tipo_entrega
if "textos_entrega JSONB DEFAULT" not in neg_code:
    neg_code = neg_code.replace(
        'conn.execute("ALTER TABLE config_negocio ADD COLUMN IF NOT EXISTS permitir_inventario_negativo BOOLEAN DEFAULT TRUE")',
        'conn.execute("ALTER TABLE config_negocio ADD COLUMN IF NOT EXISTS permitir_inventario_negativo BOOLEAN DEFAULT TRUE")\n'
        '    conn.execute("ALTER TABLE config_negocio ADD COLUMN IF NOT EXISTS textos_entrega JSONB DEFAULT \'{}\'")\n'
        '    conn.execute("ALTER TABLE centros_utilidad ADD COLUMN IF NOT EXISTS imprimir_tipo_entrega BOOLEAN DEFAULT TRUE")'
    )

# Replace _telegram_entrega
old_tg_entrega_pattern = re.compile(r'def _telegram_entrega\(tipo_entrega, direccion=None, mesa=None\):.*?return f"\{tipo_entrega or \'Pedido\'\}: \{direccion or mesa or \'N/A\'\}"', re.DOTALL)
new_tg_entrega = '''def _telegram_entrega(tipo_entrega, direccion=None, mesa=None, nombre_cajero=None, textos_config=None, imprimir_entrega=True):
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

if old_tg_entrega_pattern.search(neg_code):
    neg_code = old_tg_entrega_pattern.sub(new_tg_entrega, neg_code)

# In _get_config, add textos_entrega and centros_utilidad
old_get_config = """def _get_config(conn, tercero_id):
    row = conn.execute(
        \"\"\"SELECT modalidades, metodos_pago, aviso_pedido, metodos_info,
                  domicilio_tarifa, domicilio_modo_fuera, domicilio_zona, mapa_region,
                  cambio_efectivo_modo, mensaje_sin_pedidos,
                  COALESCE(facturacion_copias, 1) AS facturacion_copias,
                  COALESCE(mostrar_productos_precio_cero, TRUE) AS mostrar_productos_precio_cero,
                  COALESCE(permitir_inventario_negativo, TRUE) AS permitir_inventario_negativo"""

new_get_config = """def _get_config(conn, tercero_id):
    row = conn.execute(
        \"\"\"SELECT modalidades, metodos_pago, aviso_pedido, metodos_info,
                  domicilio_tarifa, domicilio_modo_fuera, domicilio_zona, mapa_region,
                  cambio_efectivo_modo, mensaje_sin_pedidos,
                  COALESCE(facturacion_copias, 1) AS facturacion_copias,
                  COALESCE(mostrar_productos_precio_cero, TRUE) AS mostrar_productos_precio_cero,
                  COALESCE(permitir_inventario_negativo, TRUE) AS permitir_inventario_negativo,
                  COALESCE(textos_entrega, '{}'::jsonb) AS textos_entrega"""

if old_get_config in neg_code:
    neg_code = neg_code.replace(old_get_config, new_get_config)

# In _get_config return dict, add centros_utilidad and textos_entrega
target_return_cfg = "'permitir_inventario_negativo': bool(row['permitir_inventario_negativo'] if row['permitir_inventario_negativo'] is not None else True),"
replacement_return_cfg = """'permitir_inventario_negativo': bool(row['permitir_inventario_negativo'] if row['permitir_inventario_negativo'] is not None else True),
            'textos_entrega': raw_textos,
            'centros_utilidad': centros_list,"""

if target_return_cfg in neg_code and "'centros_utilidad': centros_list" not in neg_code:
    setup_textos = """    centros_rows = []
    try:
        centros_rows = conn.execute(\"\"\"
            SELECT id, codigo, nombre, tipo, activo, color_badge,
                   COALESCE(imprimir_tipo_entrega, TRUE) AS imprimir_tipo_entrega
            FROM centros_utilidad
            WHERE negocio_id = %s AND activo = TRUE
            ORDER BY CASE WHEN tipo IN ('principal', 'domicilio', 'movil') THEN 0 ELSE 1 END, id ASC
        \"\"\", (tercero_id,)).fetchall()
    except Exception:
        pass
    centros_list = [dict(c) for c in centros_rows]

    raw_textos = {}
    try:
        if row and 'textos_entrega' in row.keys() and row['textos_entrega']:
            raw_textos = row['textos_entrega'] if isinstance(row['textos_entrega'], dict) else json.loads(row['textos_entrega'])
    except Exception:
        raw_textos = {}
    defs = _textos_entrega_default()
    for k, v in defs.items():
        if k not in raw_textos or not isinstance(raw_textos[k], dict):
            raw_textos[k] = v
        else:
            for subk, subv in v.items():
                if subk not in raw_textos[k]:
                    raw_textos[k][subk] = subv
"""
    neg_code = neg_code.replace("if row:\n        return {", setup_textos + "\n    if row:\n        return {")
    neg_code = neg_code.replace(target_return_cfg, replacement_return_cfg)

# In api_config_save, handle centros_entrega and textos_entrega
target_api_save = "conn.commit()\n\n        if 'telegram_chat_id' in data:"
replacement_api_save = """conn.commit()

        if 'centros_entrega' in data and isinstance(data['centros_entrega'], list):
            for item in data['centros_entrega']:
                try:
                    c_id = _int_o_none(item.get('id'))
                    if c_id:
                        val_imp = bool(item.get('imprimir_tipo_entrega', True))
                        conn.execute(
                            "UPDATE centros_utilidad SET imprimir_tipo_entrega = %s WHERE id = %s AND negocio_id = %s",
                            (val_imp, c_id, tercero_id)
                        )
                except Exception as _e_ce:
                    print(f"[api_config_save] error actualizando centro entrega: {_e_ce}")
            conn.commit()

        if 'textos_entrega' in data and isinstance(data['textos_entrega'], dict):
            try:
                conn.execute(\"\"\"
                    UPDATE config_negocio
                    SET textos_entrega = %s::jsonb
                    WHERE tercero_id = %s
                \"\"\", (json.dumps(data['textos_entrega']), tercero_id))
                conn.commit()
            except Exception as _e_txt:
                print(f"[api_config_save] error actualizando textos_entrega: {_e_txt}")

        if 'telegram_chat_id' in data:"""

if target_api_save in neg_code:
    neg_code = neg_code.replace(target_api_save, replacement_api_save)

with open(neg_path, "w", encoding="utf-8") as f:
    f.write(neg_code)

print("negocios.py updated successfully.")
