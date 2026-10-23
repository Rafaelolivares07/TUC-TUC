import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('templates/inventario_admin.html', 'r', encoding='utf-8') as f:
    html = f.read()

old_btn_desc = "Si en la tabla ajustaste las cantidades (ej. más salsa o menos sal) y quieres que esa sea la <b>nueva receta estándar para siempre</b>, este botón actualiza la base de datos oficial. Las futuras órdenes usarán esta nueva proporción por unidad."
new_btn_desc = "Si en la tabla ajustaste las cantidades (ej. más salsa o menos sal) y quieres que esa sea la <b>nueva receta estándar para siempre</b>, este botón actualiza la base de datos oficial dividiendo los insumos de la tabla entre tu <b>Cantidad Real Obtenida</b> para fijar el nuevo estándar por unidad."

if old_btn_desc in html:
    html = html.replace(old_btn_desc, new_btn_desc, 1)
    print("Refined button card text successfully")

old_mod_desc = "Cada insumo consumido en la tabla se dividirá entre las <strong><span id=\"ajuste-cant-producir\" class=\"font-mono font-black text-indigo-950\"></span> unidades</strong> producidas para fijar la nueva proporción por <strong>1 unidad</strong> de producto terminado."
new_mod_desc = "Cada insumo consumido en la tabla se dividirá entre las <strong><span id=\"ajuste-cant-producir\" class=\"font-mono font-black text-indigo-950\"></span> unidades</strong> (tu Cantidad Real Obtenida) para fijar la nueva proporción por <strong>1 unidad</strong> de producto terminado."

if old_mod_desc in html:
    html = html.replace(old_mod_desc, new_mod_desc, 1)
    print("Refined modal text successfully")

with open('templates/inventario_admin.html', 'w', encoding='utf-8') as f:
    f.write(html)
