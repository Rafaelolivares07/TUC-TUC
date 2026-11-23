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

tpl = open(TPL, encoding="utf-8").read()
ventas = open(VENTAS, encoding="utf-8").read()
usuario = open(USUARIO, encoding="utf-8").read()

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

TOTAL = 20
print(f"--- {TOTAL - len(fails)}/{TOTAL} ---")
sys.exit(1 if fails else 0)
