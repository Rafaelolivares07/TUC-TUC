# -*- coding: utf-8 -*-
"""Acceso a centros por (tercero, negocio) (04/11): la tabla
usuarios_centros_utilidad usaba usuario_id pelado (ambiguo: fila de
usuarios o id de tercero). Se alinea al molde bueno sin cambiar
respuestas ni aceptaciones. Uso: python tests/test_centros_acceso_tercero.py
"""
import os
import sys

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Contrato 13/11: el wrapper corre 1x/worker; los pines van contra el impl
from app.blueprints.inventarios import (  # noqa: E402
    _asegurar_acceso_centros_impl as _asegurar_acceso_centros,
    _tercero_sesion_centros,
)


class _Cur:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Conn:
    def __init__(self, ids_validos, boom=False):
        self.ids = set(ids_validos)
        self.boom = boom
        self.rollbacks = 0
        self.commits = 0
        self.sqls = []

    def execute(self, q, p=None):
        self.sqls.append(q)
        if self.boom:
            raise Exception('boom')
        if p:
            uid = p[0]
            return _Cur({'id': uid} if uid in self.ids else None)
        return _Cur(None)

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1


check('chat manda', _tercero_sesion_centros(_Conn({58}), {'chat_tercero_id': 58, 'usuario_id': 58}) == 58)
check('fallback usuario-tercero', _tercero_sesion_centros(_Conn({58}), {'usuario_id': 58}) == 58)
check('usuario no-tercero da None', _tercero_sesion_centros(_Conn({58}), {'usuario_id': 999}) is None)
check('sesion vacia da None', _tercero_sesion_centros(_Conn({58}), {}) is None)

c = _Conn({58})
_asegurar_acceso_centros(c)
todo = ' '.join(c.sqls)
check('asegurar crea tabla', 'CREATE TABLE IF NOT EXISTS usuarios_centros_utilidad' in todo)
check('asegurar agrega tercero_id', 'ADD COLUMN IF NOT EXISTS tercero_id' in todo)
check('asegurar agrega negocio_id', 'ADD COLUMN IF NOT EXISTS negocio_id' in todo)
check('asegurar indice nuevo', 'idx_ucu_tercero_negocio' in todo)
check('asegurar rellena negocio', 'SET negocio_id = c.negocio_id' in todo)
check('asegurar rellena tercero', 'SET tercero_id = u.usuario_id' in todo)
check('asegurar hace commit', c.commits >= 1)
c2 = _Conn({58}, boom=True)
_asegurar_acceso_centros(c2)
check('asegurar tolera error', c2.rollbacks >= 1)

SRC = open(os.path.join(ROOT, 'app', 'blueprints', 'inventarios.py'), encoding='utf-8').read()
check('list usa join centros', SRC.count('JOIN centros_utilidad c ON c.id = u.centro_utilidad_id') >= 2)
check('lecturas llave nueva + respaldo', SRC.count('(u.tercero_id = %s OR (u.tercero_id IS NULL AND u.usuario_id = %s))') >= 2)
check('crear escribe llaves nuevas', 'tercero_id, negocio_id, centro_utilidad_id' in SRC)
check('crear conserva usuario_id', 'INSERT INTO usuarios_centros_utilidad (usuario_id, tercero_id' in SRC)
check('3 endpoints aseguran', SRC.count('_asegurar_acceso_centros(conn)') >= 3)
for campo in ('autorizado', 'es_predeterminado', 'es_activo', 'es_multisede', 'puede_crear', 'centro_activo'):
    check(f'respuesta conserva {campo}', f"'{campo}'" in SRC)

print(f'--- {total[0] - len(fails)}/{total[0]} ---')
sys.exit(1 if fails else 0)
