# -*- coding: utf-8 -*-
"""Pin: COMO FUNCIONA final (5 puntos + cierre) + defaults min8/max15.
Doctrinas Rafa: cada punto se defiende solo; #1 fusionado (dias+que);
avisa cuando SE AGOTA; a-precio define proveedor; app asiste, usted decide."""
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

# Manual ventas: COMO FUNCIONA final (5 + cierre)
check("ventas titulo Como funciona", "## ¿Cómo funciona?" in ventas)
check("ventas sin titulo Las 7", "## Las 7 ventajas" not in ventas)
check("ventas #1 fusionado",
      "**1. ¿QUÉ COMPRAR? -> Lo que entra en agotado.**" in ventas)
check("ventas #1 trae 8/15", "8/15 por defecto" in ventas)
check("ventas #1 solicitud", "se incluye en la solicitud de compra" in ventas)
check("ventas #1 detecta solo", "el algoritmo lo detecta solo" in ventas)
check("ventas sin viejo #1 dias", "**1. Usted pone los días" not in ventas)
check("ventas #2 es cuando",
      "**2. Cuándo comprar.**" in ventas)
check("ventas cuando ni antes ni después",
      "ni antes (se sobrestockea) ni después (sufre agotados)" in ventas)
check("ventas cuando trae el aviso", "le cae un aviso oportuno al celular" in ventas)
check("ventas #3 es cuanto", "**3. Cuánto comprar: la cantidad exacta.**" in ventas)
check("ventas #3 ancla maximos", "hasta sus días máximos" in ventas)
check("ventas #4 es a precio",
      "**4. A qué precio comprar: selecciona el mejor precio.**" in ventas)
check("ventas #4 descarte calidad", "fallan en calidad de producto o servicio" in ventas)
check("ventas #4 asiste decide", "La aplicación asiste, usted decide" in ventas)
check("ventas sin viejo a-cuanto", "A cuánto comprar" not in ventas)
check("ventas sin paga-menos", "Paga menos sin buscarlo" not in ventas)
check("ventas #5 es a quien",
      "**5. A quién comprar.**" in ventas)
check("ventas #5 precio define", "El mejor precio define al proveedor" in ventas)
check("ventas #5 orden de compra", "orden de compra viaja con enlace propio" in ventas)
check("ventas #5 proveedor explicito", "el proveedor la confirma o la ajusta" in ventas)
check("ventas cierre sin numero",
      "*La app propone, usted chulea, ajusta y confirma.*" in ventas)
check("ventas sin #6 numerado", "**6." not in ventas)
check("ventas sin #7", "**7. Nada" not in ventas)
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
