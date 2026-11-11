"""F1+F2 FV-650: piso anti-negativo en residual 61 + sync respeta bajas ajenas.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_residual_61_f1f2.py
F1: _recostear_producto jamas escribe un debito 61 negativo al cuadrar el
    residual 14-vs-61 (caso 650: 2669.21 + -5780.18); lo omite y avisa.
F2: _reparar_venta no borra bajas 14 de otros platos (padre NULL, ej. la
    Coca de la 650) y atiende venta directa (MI propio sin padre).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.blueprints.inventarios as inv  # noqa: E402

fails = []
total = [0]


def check(name, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


# ---------- F1: helper puro ----------
check('F1 helper existe', hasattr(inv, '_aplica_residual_61'))
if hasattr(inv, '_aplica_residual_61'):
    f = inv._aplica_residual_61
    check('F1 caso 650 se omite', f(2669.21, -5780.18) == (False, -3110.97),
          repr(f(2669.21, -5780.18)))
    check('F1 cero exacto aplica', f(5780.18, -5780.18) == (True, 0.0))
    check('F1 positivo aplica', f(100.0, 0.05) == (True, 100.05))
    check('F1 negativo puro se omite', f(0.0, -0.5) == (False, -0.5))
    check('F1 None seguro', f(None, -1.0) == (False, -1.0))

# ---------- F1: pines en _recostear_producto ----------
import inspect  # noqa: E402

src_rec = inspect.getsource(inv._recostear_producto)
check('F1 recosteo usa helper', '_aplica_residual_61(' in src_rec)
check('F1 recosteo lee monto+concepto',
      'SELECT id, monto, concepto FROM movimientos_contables' in src_rec)
check('F1 recosteo junta alertas', "'alertas_61'" in src_rec)
check('F1 recosteo cuenta omitidos', "'residuales_61_omitidos'" in src_rec)


# ---------- F2: _reparar_venta con conn falsa ----------
class FakeCur:
    def __init__(self, router, sql, params):
        self._router = router
        self._sql = sql
        self._params = params

    def fetchall(self):
        return self._router(self._sql, self._params, True)

    def fetchone(self):
        return self._router(self._sql, self._params, False)


class FakeConn:
    def __init__(self, router):
        self._router = router
        self.records = []

    def execute(self, sql, params=()):
        self.records.append((sql, tuple(params)))
        return FakeCur(self._router, sql, tuple(params))


PECHUGA_MI = {'producto_id': 302, 'nombre_producto': 'PECHUGA POLLO PREPARADA GRS',
              'cantidad': 100.0, 'costo_und': 26.692083, 'total': 2669.21,
              'documento_fecha': None, 'created_at': None}
COCA_MI = {'producto_id': 343, 'nombre_producto': 'Cocacola x250 ml',
           'cantidad': 4.0, 'costo_und': 1445.045135, 'total': 5780.1805,
           'documento_fecha': None, 'created_at': None}


def baja14(_id, producto_id, padre_id, monto, concepto):
    return {'id': _id, 'monto': monto, 'cuenta': '140505', 'concepto': concepto,
            'producto_id': producto_id, 'producto_padre_id': padre_id,
            'comprobante_id': 1464, 'tipo_documento_id': 6,
            'tipo_documento': 'FACTURA_DE_VENTA', 'fecha': '2026-11-07'}


_next_id = [9000]


def make_router(contab14, cogs_rows, doc_ref):
    def router(sql, params, many):
        s = ' '.join(sql.split())
        if many:
            if 'FROM movimientos_inventario' in s and "tipo = 'salida'" in s:
                ppid = params[1]
                if ppid == 331:
                    return [dict(PECHUGA_MI)]
                if ppid == 343 and 'producto_padre_id IS NULL' in s:
                    return [dict(COCA_MI)]
                return []
            if "cuenta LIKE '14%%'" in s:
                return [dict(r) for r in contab14]
            if 'LEFT(cuenta, 2)' in s and "'61'" in s:
                return [dict(r) for r in cogs_rows]
            return []
        if 'SELECT id, comprobante_id' in s:
            return dict(doc_ref) if doc_ref else None
        if "codigo = '140505'" in s:
            return {'id': 131}
        if 'SELECT nombre, categoria FROM productos' in s:
            return {'nombre': 'X', 'categoria': None}
        if "codigo LIKE '61%%'" in s:
            return {'codigo': '614005'}
        if s.startswith('SELECT id FROM cuentas_puc WHERE codigo'):
            return {'id': 140}
        if 'SELECT DISTINCT referencia_tipo' in s:
            return None
        if 'SUM(pi.cantidad)' in s:
            return {'cant_vendida': None, 'max_pi_id': None}
        if s.startswith('INSERT INTO movimientos_contables'):
            _next_id[0] += 1
            return {'id': _next_id[0]}
        return None
    return router


# F2a: plato 331 con baja ajena (Coca, padre NULL) en el mismo comprobante
contab_a = [baja14(1, 302, 331, 2669.21, 'Baja Inv: PECHUGA POLLO PREPARADA GRS'),
            baja14(2, 343, None, 5780.18, 'Baja Inv: Cocacola x250 ml')]
fc = FakeConn(make_router(contab_a, [{'id': 13748, 'monto': 2669.21}], None))
res_a = inv._reparar_venta(fc, 59, 331, '650', {})
dels = [p for (s, p) in fc.records if 'DELETE FROM movimientos_contables' in s]
check('F2a baja ajena no se borra', all(p != (2,) for p in dels), repr(dels))
upds = [(s, p) for (s, p) in fc.records
        if s.startswith('UPDATE movimientos_contables SET monto')]
check('F2a cogs se repone', (2669.21, 331, 331, 13748) in [p for (_, p) in upds],
      repr(upds))
check('F2a sin cambios 14', res_a.get('cambios_contables') == []
      and res_a.get('cogs_modificado') is True, repr(res_a))

# F2b: venta directa 343 (Coca, MI propio sin padre, baja perdida)
doc_ref_b = {'id': 13750, 'comprobante_id': 1464, 'tipo_documento_id': 6,
             'tipo_documento': 'FACTURA_DE_VENTA', 'fecha': '2026-11-07'}
fc2 = FakeConn(make_router([], [{'id': 13750, 'monto': 5780.18}], doc_ref_b))
res_b = inv._reparar_venta(fc2, 59, 343, '650', {})
check('F2b no salta venta directa', res_b.get('skip') is not True, repr(res_b))
ins14 = [p for (s, p) in fc2.records
         if 'INSERT INTO movimientos_contables' in s and "'credito'" in s]
check('F2b crea baja Coca', any(p[3] == 5780.18 and p[4] == 'Baja Inv: Cocacola x250 ml'
                                and p[5] == 343 and p[6] == 343 for p in ins14),
      repr(ins14))

print(f'{total[0] - len(fails)}/{total[0]} checks, {len(fails)} fallos')
sys.exit(1 if fails else 0)
