"""Regression: autoguardado de dias min/max en Compras al salir del campo.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_compras_autoguardado.py
Pin estatico sobre inventario_admin.html (sin BD/DOM):
  - inputs Mín/Máx por línea + 3 globales guardan con onchange (sin botón)
  - estado visual guardando/guardado/error en cada punto
  - recalculo local y recalcular-todo intactos
Regla: no existe botón Guardar para días; salir del campo persiste y
el punto de estado lo hace evidente (… ámbar, ✓ verde, ! rojo).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / 'templates' / 'inventario_admin.html'

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


raw = HTML.read_bytes()
html = raw.decode('utf-8')

ini = html.find('async function guardarStockParamsProducto')
fin = html.find('const guardarMaxStockProducto')
cuerpo_linea = html[ini:fin] if ini >= 0 and fin > ini else ''

ini2 = html.find('async function guardarParametroNegocio')
fin2 = html.find('function recalcularLineaMaxStock')
cuerpo_glob = html[ini2:fin2] if ini2 >= 0 and fin2 > ini2 else ''

check('funcion linea localizada', bool(cuerpo_linea))
check('funcion global localizada', bool(cuerpo_glob))
check('linea min/max con onchange', html.count('onchange="guardarStockParamsProducto') >= 2,
      str(html.count('onchange="guardarStockParamsProducto')))
check('max conserva recalc local', "oninput=\"recalcularLineaMaxStock" in html)
check('sin boton Guardar por linea', '<button onclick="guardarStockParamsProducto' not in html)
check('punto estado por linea', 'id="save-stock-prod-${prod.producto_id}"' in html)
check('linea pinta guardando', "pintarEstado('\u2026'" in cuerpo_linea)
check('linea pinta guardado', "pintarEstado('\u2713'" in cuerpo_linea)
check('linea pinta error', "pintarEstado('!'" in cuerpo_linea)
check('3 globales con onchange', html.count('onchange="guardarParametroNegocio') == 3,
      str(html.count('onchange="guardarParametroNegocio')))
check('sin botones floppy', 'title="Guardar en BD"' not in html)
check('sin onclick param', 'onclick="guardarParametroNegocio' not in html)
check('puntos estado globales',
      'id="save-cfg-compras-stock-max"' in html
      and 'id="save-cfg-compras-stock-min"' in html
      and 'id="save-cfg-compras-dias-entrega"' in html)
check('global pinta guardando', "pintarEstado('\u2026'" in cuerpo_glob)
check('global pinta guardado', "pintarEstado('\u2713'" in cuerpo_glob)
check('global pinta error', "pintarEstado('!'" in cuerpo_glob)
check('recalcular-todo intacto',
      'guardarParametroNegocio(\'inventario_stock_max_dias\'' in html
      and 'cargarSugerenciasCompras();' in html)
check('CRLF puro', raw.count(b'\n') == raw.count(b'\r\n') and raw.count(b'\r\n') > 0)

print(f'--- {len(fails)} fallos ---')
sys.exit(1 if fails else 0)
