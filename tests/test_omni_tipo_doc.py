# -*- coding: utf-8 -*-
"""Omni tipos de documento: url al tab real + fila sin badge de codigo. Fake conn, stdlib."""
import importlib.util
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MOTOR = os.path.join(ROOT, 'app', 'buscador_motor.py')
PART = os.path.join(ROOT, 'templates', 'partials', 'buscador_omni.html')
fails = []
total = [0]


def check(nombre, cond):
    total[0] += 1
    print(('PASS' if cond else 'FAIL'), nombre)
    if not cond:
        fails.append(nombre)


class FakeCur:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConn:
    def __init__(self):
        self.queries = []
        self.tipos = [
            {'id': 7, 'codigo': 'GASTO_DE_ENTREGAS', 'nombre': 'RELACION DE DESEMBOLSOS',
             'tipo_movimiento': 'gasto', 'mueve_inventario': False,
             'consecutivo': 63, 'numero_inicio': 64},
        ]

    def execute(self, sql, params=None):
        self.queries.append(sql)
        if 'tipos_documento_negocio' in sql:
            return FakeCur(self.tipos)
        return FakeCur([])


spec = importlib.util.spec_from_file_location('motor_under_test', MOTOR)
motor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motor)

check('api existe', hasattr(motor, 'buscar_datos_tipos_doc'))
f = motor.buscar_datos_tipos_doc
check('q corta -> []', f(FakeConn(), 'd', 59) == [])
res = f(FakeConn(), 'desembol', 59)
check('trae 1 tipo', len(res) == 1)
t = res[0] if res else {}
check('nombre intacto', t.get('nombre') == 'RELACION DE DESEMBOLSOS')
check('consecutivo sano', t.get('consecutivo') == 63 and t.get('proximo_numero') == 64)
check('url al tab tipos', t.get('url') == '/contabilidad/59?tab=tipos')
check('url sin tab roto', 'tipos_doc' not in (t.get('url') or ''))

part = open(PART, encoding='utf-8').read()
check('fila sin badge codigo', 'td.codigo' not in part)
check('fila conserva Ver', '${escapeHtml(td.url)}' in part)
check('fila conserva nombre+consecutivo', '${escapeHtml(td.nombre)}' in part and 'td.proximo_numero' in part)

print('%d/%d checks' % (total[0] - len(fails), total[0]))
sys.exit(1 if fails else 0)
