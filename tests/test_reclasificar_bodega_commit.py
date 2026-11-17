"""Regression: reclasificar_bodega persiste el recosteo (commit tras recostear).

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_reclasificar_bodega_commit.py
Cubre el endpoint de inventarios.py (conn falsa, sin BD):
  api_inventario_movimiento_reclasificar_bodega (rama un movimiento)
Regla: el recosteo de origen+destino debe quedar ANTES del commit final;
sin ese commit, close() revierte saldos/costos y el globo del kardex
queda viejo mientras la tabla si muestra el movimiento (lechuga 2026-11-17).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.blueprints.inventarios as inv  # noqa: E402

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


class FakeResp:
    def __init__(self, payload):
        self.payload = payload


class FakeCur:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


MOV = {'id': 777, 'negocio_id': 59, 'producto_id': 343, 'tipo': 'entrada',
       'motivo': 'compra', 'cantidad': 2740, 'valor_unitario': 4,
       'valor_total': 10960, 'costo_und': 4, 'bodega': 2,
       'tipo_documento': 'FACTURA_PROVEEDOR', 'documento_numero': '41400',
       'numero_documento': '41400'}
CU_DEST = {'id': 3, 'codigo': 'ENV', 'nombre': 'Local ENVIGADO'}
CU_ORIG = {'id': 2, 'codigo': 'PRIN', 'nombre': 'SEDE PRINCIPAL'}


class FakeConn:
    def __init__(self):
        self.events = []
        self.recosteos = []

    def execute(self, sql, params=()):
        s = ' '.join(str(sql).split())
        if s.startswith('SELECT id, negocio_id, producto_id'):
            return FakeCur([dict(MOV)])
        if 'FROM centros_utilidad' in s and 'activo = TRUE' in s:
            return FakeCur([dict(CU_DEST)])
        if 'FROM centros_utilidad' in s:
            return FakeCur([dict(CU_ORIG)])
        self.events.append(('sql', s[:70]))
        return FakeCur([])

    def commit(self):
        self.events.append(('commit',))

    def rollback(self):
        self.events.append(('rollback',))

    def close(self):
        self.events.append(('close',))


fake_conn = FakeConn()


def fake_recostear(conn, negocio_id, producto_id, bodega=None, **kw):
    conn.execute('UPDATE saldos_inventario SET stock = 1 WHERE 1 = 0')
    conn.recosteos.append(bodega)
    return {'producto_nombre': 'LECHUGA X GRS'}


class Req:
    def get_json(self, silent=True):
        return {'nueva_bodega_id': 3}


_orig = (inv.get_db_connection, inv._recostear_producto,
         inv._validar_negocio_json, inv.jsonify, inv.session, inv.request)
inv.get_db_connection = lambda: fake_conn
inv._recostear_producto = fake_recostear
inv._validar_negocio_json = lambda conn, neg: ({}, None)
inv.jsonify = lambda d: FakeResp(d)
inv.session = {'usuario_id': 1, 'usuario_nombre': 't'}
inv.request = Req()
try:
    out = inv.api_inventario_movimiento_reclasificar_bodega(777)
finally:
    (inv.get_db_connection, inv._recostear_producto,
     inv._validar_negocio_json, inv.jsonify, inv.session, inv.request) = _orig

check('responde ok', isinstance(out, FakeResp) and out.payload.get('ok') is True,
      repr(getattr(out, 'payload', out)))
p = out.payload if isinstance(out, FakeResp) else {}
check('un movimiento', p.get('movimientos_afectados') == 1, repr(p))
check('origen 2 destino 3', p.get('bodega_origen') == 2 and p.get('bodega_destino') == 3, repr(p))
check('recostea origen+destino', fake_conn.recosteos == [2, 3], repr(fake_conn.recosteos))
check('mueve MI a bodega 3', any(e[0] == 'sql' and 'UPDATE movimientos_inventario' in e[1]
                                 for e in fake_conn.events), repr(fake_conn.events))

idx_commit = [i for i, e in enumerate(fake_conn.events) if e[0] == 'commit']
idx_saldo = [i for i, e in enumerate(fake_conn.events)
             if e[0] == 'sql' and 'saldos_inventario' in e[1]]
check('recosteo corre', len(idx_saldo) == 2, repr(fake_conn.events))
check('commit tras recosteo (no se pierde)',
      bool(idx_commit) and bool(idx_saldo) and max(idx_commit) > max(idx_saldo),
      repr(fake_conn.events))
check('cierra al final', fake_conn.events and fake_conn.events[-1][0] == 'close',
      repr(fake_conn.events))

print(f'--- {len(fails)} fallos ---')
sys.exit(1 if fails else 0)
