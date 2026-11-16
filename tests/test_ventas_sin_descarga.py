"""Regression: ventas sin descarga en reparador de costos (caso bondiola 328 / FV-440).

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_ventas_sin_descarga.py
Cubre el helper de inventarios.py (conn falsa, sin BD):
  _ventas_sin_descarga
Regla: productos vendidos en el rango SIN salidas kardex con
producto_padre_id (caso bondiola: POS 1122.03, kardex 0) se listan
aparte, excluidos de la reparacion automatica por copia.
Afinacion 2026-11-16 (caso coca simple): si el producto NO tiene
receta, su salida directa cuenta como descarga y no se lista.
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.blueprints.inventarios import (  # noqa: E402
    _ventas_sin_descarga,
)

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


class FakeCur:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ''
        self.params = ()

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = tuple(params)
        self._rows = self.rows if 'FROM pedido_items pi' in sql else []
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    def __init__(self, rows):
        self.cur = FakeCur(rows)

    def execute(self, sql, params=()):
        return self.cur.execute(sql, params)


BONDIOLA = {
    'producto_id': 328,
    'producto_nombre': 'ADICION DE BONDIOLA',
    'pedido_id': 999,
    'numero_documento': 'FACTURA_DE_VENTA-440',
    'tipo_documento_id': 7,
    'cliente_tercero_id': 123,
    'fecha': date(2026, 10, 26),
    'cantidad': 1,
    'costo_pos_total': 1122.03,
}

# 1) mapeo fila bondiola -> contrato JSON
out = _ventas_sin_descarga(FakeConn([dict(BONDIOLA)]), 59, '2026-10-01', '2026-10-29')
check('1 fila -> 1 item', len(out) == 1, repr(out))
r = out[0] if out else {}
check('producto_id 328', r.get('producto_id') == 328, repr(r))
check('fecha iso', r.get('fecha') == '2026-10-26', repr(r.get('fecha')))
check('cantidad float', r.get('cantidad') == 1.0 and isinstance(r.get('cantidad'), float), repr(r.get('cantidad')))
check('costo float', r.get('costo_pos_total') == 1122.03, repr(r.get('costo_pos_total')))
check('llaves auditoria', r.get('tipo_documento_id') == 7 and r.get('cliente_tercero_id') == 123
      and r.get('numero_documento') == 'FACTURA_DE_VENTA-440', repr(r))

# 2) vacio -> []
check('sin filas -> []', _ventas_sin_descarga(FakeConn([]), 59, '2026-10-01', '2026-10-29') == [])

# 3) SQL: corazon del filtro (sin descarga = NOT EXISTS salidas padre)
fc = FakeConn([])
_ventas_sin_descarga(fc, 59, '2026-10-01', '2026-10-29')
check('SQL NOT EXISTS', 'NOT EXISTS' in fc.cur.sql, fc.cur.sql[:120])
check('SQL padre = producto', 'mi.producto_padre_id = pi.producto_id' in fc.cur.sql)
check('SQL excluye anulados', "'anulado'" in fc.cur.sql and "'premontado'" in fc.cur.sql)
check('SQL params base', fc.cur.params[:3] == (59, '2026-10-01', '2026-10-29'), repr(fc.cur.params))

# 4) filtro producto_padre_id
fc = FakeConn([])
_ventas_sin_descarga(fc, 59, '2026-10-01', '2026-10-29', prod_padre_id=328)
check('filtro producto en SQL', 'pi.producto_id = %s' in fc.cur.sql)
check('filtro producto en params', 328 in fc.cur.params, repr(fc.cur.params))

# 5) filtro numero_doc acepta full y pelado
fc = FakeConn([])
_ventas_sin_descarga(fc, 59, '2026-10-01', '2026-10-29', numero_doc='FACTURA_DE_VENTA-440')
check('doc full en params', 'FACTURA_DE_VENTA-440' in fc.cur.params, repr(fc.cur.params))
check('doc pelado en params', '440' in fc.cur.params, repr(fc.cur.params))

# 6) afinacion 2026-11-16 (caso coca simple): la salida directa del
# producto cuenta como descarga SOLO si no tiene receta; con receta
# sigue exigiendo bajas hijas (casos plato intactos).
fc = FakeConn([])
_ventas_sin_descarga(fc, 59, '2026-10-01', '2026-10-29')
check('SQL rama directa', 'mi.producto_id = pi.producto_id' in fc.cur.sql)
check('SQL directa sin padre', 'mi.producto_padre_id IS NULL' in fc.cur.sql)
check('SQL gate receta', 'tarjeta_estandar' in fc.cur.sql
      and 't.producto_id = pi.producto_id' in fc.cur.sql)
check('SQL sin params nuevos', fc.cur.params == (59, '2026-10-01', '2026-10-29', 59, '2026-10-01', '2026-10-29'),
      repr(fc.cur.params))

print(f'{19 - len(fails)}/19 checks, {len(fails)} fallos')
sys.exit(1 if fails else 0)
