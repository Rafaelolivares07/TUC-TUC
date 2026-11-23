# -*- coding: utf-8 -*-
"""Pin: 7 ventajas compras (orden y texto vigentes) + defaults min8/max15.
Doctrinas Rafa: marco 'Como funciona', cada punto se defiende solo;
cuando = momento de empezar; #1 avisa cuando SE AGOTA (2 estados);
dias primero (8/15 por defecto, dueno personaliza)."""
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

# Pantalla: rotulos Cuándo pedir, palabra clave intacta
check("header columna Cuándo pedir x1",
      tpl.count('<th class="px-3 py-2 text-center">Cuándo pedir</th>') == 1)
check("tarjeta Cuándo pedir: x1", tpl.count(">Cuándo pedir:</span>") == 1)
check("sin 'Límite Compra' visible", "Límite Compra" not in tpl)
check("sin 'Fecha límite' visible", "Fecha límite" not in tpl)
check("backend key fecha_limite intacta", "fecha_limite" in tpl)
check("ids compras-fecha-limite intactos", "compras-fecha-limite-" in tpl)

# Manual ventas: 7 ventajas autocontenidas (dias primero)
check("ventas titulo Las 7 ventajas", "## Las 7 ventajas" in ventas)
check("ventas sin titulo Las 8", "## Las 8 ventajas" not in ventas)
check("ventas #1 es dias primero",
      "**1. Usted pone los días, el consumo pone las cantidades.**" in ventas)
check("ventas #1 trae 8/15 por defecto", "8/15 por defecto" in ventas)
check("ventas #1 habilita que comprar",
      "el algoritmo ya define qué comprar" in ventas)
check("ventas #1 explica minimos", "días mínimos (su colchón" in ventas)
check("ventas #1 explica maximos", "días máximos (hasta dónde" in ventas)
check("ventas #2 entra en agotado",
      "**2. Qué comprar: entra en agotado.**" in ventas)
check("ventas #2 dos estados",
      "Solo dos estados: incluido o no incluido" in ventas)
check("ventas sin viejo #1 titulo", "**1. Qué comprar: lo ve venir.**" not in ventas)
check("ventas sin viejo #1 cuerpo",
      "avisa qué se va a agotar antes de que falte" not in ventas)
check("ventas #2 sin jerga cobertura", "cobertura de un ítem" not in ventas)
check("ventas #2 re-ancla dias", "días mínimos que usted definió" in ventas)
check("ventas #3 es cuando",
      "**3. Cuándo comprar: el momento justo de empezar.**" in ventas)
check("ventas cuando ni antes ni después",
      "ni antes (se sobrestockea) ni después (sufre agotados)" in ventas)
check("ventas cuando en usted",
      "te sobrestockeas" not in ventas and "te cae un aviso" not in ventas)
check("ventas cuando trae el aviso", "le cae un aviso oportuno al celular" in ventas)
check("ventas #4 es cuanto", "**4. Cuánto comprar: la cantidad exacta.**" in ventas)
check("ventas #4 ancla maximos", "hasta sus días máximos" in ventas)
check("ventas #5 es a cuanto",
      "**5. A cuánto comprar: caza el mejor precio.**" in ventas)
check("ventas #6 es a quien",
      "**6. A quién comprar, de punta a punta.**" in ventas)
check("ventas #7 es confirmacion",
      "**7. Nada se pide sin que usted lo confirme.**" in ventas)
check("ventas sin #8", "**8. Nada" not in ventas)
check("ventas sin #6 avisos standalone", "**6. Avisos oportunos" not in ventas)
check("ventas sin fecha límite", "fecha límite" not in ventas and "Fecha límite" not in ventas)
check("ventas pitch momento justo",
      "el momento justo de empezar a pedir cada cosa" in ventas)

# Manual usuario: coherente con pantalla
check("usuario columna Cuándo pedir", "| Cuándo pedir |" in usuario)
check("usuario explica sobrestock/agotados",
      "Antes te sobrestockeas, después sufres agotados" in usuario)
check("usuario sin fecha límite", "fecha límite" not in usuario and "Fecha límite" not in usuario)

# Defaults min 8 / max 15 cuando no definido (fuera respaldo a entrega)
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

TOTAL = 44
print(f"--- {TOTAL - len(fails)}/{TOTAL} ---")
sys.exit(1 if fails else 0)
