# -*- coding: utf-8 -*-
"""Pin: concepto cuando-comprar = momento de empezar (Cuándo pedir), no fecha limite.
Doctrina Rafa 2026-11-23: ni antes (sobrestock) ni despues (agotados).
Fusion 2026-11-23: #6 avisos absorbido por #2, quedan 7 ventajas."""
import sys

fails = []


def check(nombre, cond):
    print(("PASS " if cond else "FAIL ") + nombre)
    if not cond:
        fails.append(nombre)


TPL = "templates/inventario_admin.html"
VENTAS = "docs/ventas_modulo_compras.md"
USUARIO = "docs/manuales/compras_usuario.md"
INV = "app/blueprints/inventarios.py"

tpl = open(TPL, encoding="utf-8").read()
ventas = open(VENTAS, encoding="utf-8").read()
usuario = open(USUARIO, encoding="utf-8").read()
inv = open(INV, encoding="utf-8").read()

# Pantalla: rotulos nuevos, palabra clave Cuando intacta
check("header columna Cuándo pedir x1",
      tpl.count('<th class="px-3 py-2 text-center">Cuándo pedir</th>') == 1)
check("tarjeta Cuándo pedir: x1", tpl.count(">Cuándo pedir:</span>") == 1)
check("sin 'Límite Compra' visible", "Límite Compra" not in tpl)
check("sin 'Fecha límite' visible", "Fecha límite" not in tpl)
# Contrato interno intacto (solo cambio rotulos)
check("backend key fecha_limite intacta", "fecha_limite" in tpl)
check("ids compras-fecha-limite intactos", "compras-fecha-limite-" in tpl)

# Manual ventas: #2 conserva keyword, reza momento de empezar + aviso
check("ventas conserva 'Cuándo comprar'",
      "**2. Cuándo comprar: el momento justo de empezar.**" in ventas)
check("ventas explica ni antes ni después",
      "ni antes (te sobrestockeas) ni después (sufres agotados)" in ventas)
check("ventas sin fecha límite", "fecha límite" not in ventas and "Fecha límite" not in ventas)
check("ventas pitch momento justo",
      "el momento justo de empezar a pedir cada cosa" in ventas)
# Fusion #6 -> #2: 7 ventajas
check("ventas titulo Las 7 ventajas", "## Las 7 ventajas" in ventas)
check("ventas sin titulo Las 8", "## Las 8 ventajas" not in ventas)
check("ventas #2 trae el aviso", "te cae un aviso oportuno al celular" in ventas)
check("ventas sin #6 avisos standalone", "**6. Avisos oportunos" not in ventas)
check("ventas #6 es dias/consumo", "**6. Usted pone los días" in ventas)
check("ventas #7 es confirmacion", "**7. Nada se pide sin que usted lo confirme.**" in ventas)
check("ventas sin #8", "**8. Nada" not in ventas)

# Manual usuario: columna + explicacion coherentes con pantalla
check("usuario columna Cuándo pedir", "| Cuándo pedir |" in usuario)
check("usuario explica sobrestock/agotados",
      "Antes te sobrestockeas, después sufres agotados" in usuario)
check("usuario sin fecha límite", "fecha límite" not in usuario and "Fecha límite" not in usuario)

# Defaults min 8 / max 15 cuando no definido (orden Rafa 2026-11-23, fuera respaldo a entrega)
check("motor min default 8 x2",
      inv.count("'inventario_stock_min_dias', 8, 1, 365") == 2)
check("sin min->None", "'inventario_stock_min_dias', None" not in inv)
check("sin respaldo min->entrega", "dias_entrega_global or 3" not in inv)
check("sin fallback entrega como min", "_motor_param_int(conn, negocio_id, 'inventario_dias_entrega', 3, 1, 365)" not in inv)
check("red seguridad min 8", "dias_min if (dias_min and dias_min > 0) else 8" in inv)
check("api params min default 8", "'dias_stock_min_global': 8" in inv)
check("pantalla cfg min value 8", 'id="cfg-compras-stock-min" value="8"' in tpl)
check("pantalla placeholder min 8", "dias_min_stock_aplicado || 8}" in tpl)
check("manual usuario min inicial 8", "| Stock Mín (días) | 8 |" in usuario)

TOTAL = 29
print(f"--- {TOTAL - len(fails)}/{TOTAL} ---")
sys.exit(1 if fails else 0)
