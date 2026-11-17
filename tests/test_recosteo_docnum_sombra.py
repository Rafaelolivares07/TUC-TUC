"""Regression: auditoria_recosteos anota el documento disparador.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_recosteo_docnum_sombra.py
Pin estructural (AST, sin BD) sobre inventarios.py:
  _recostear_producto
Regla: el parametro doc_num (documento que disparo el recosteo) no
puede ser pisado por el loop de movimientos; la fila de auditoria
debe llevar el disparador, no el doc del ultimo movimiento (caso
reclasificacion 2026-11-17: 4 filas mismo microsegundo con docs
mezclados 41400/718/722).
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'app' / 'blueprints' / 'inventarios.py'

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


tree = ast.parse(SRC.read_text(encoding='utf-8'))
fn = next(n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == '_recostear_producto')
check('funcion localizada', fn is not None)
nodes = list(ast.walk(fn))


def asigna_a(n, var):
    if isinstance(n, ast.Assign):
        tgts = n.targets
    elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
        tgts = [n.target]
    elif isinstance(n, ast.NamedExpr):
        tgts = [n.target]
    elif isinstance(n, ast.For):
        tgts = [n.target]
    else:
        return False
    return any(isinstance(t, ast.Name) and t.id == var for t in tgts)


lineas = sorted({n.lineno for n in nodes if asigna_a(n, 'doc_num')})
check('parametro doc_num intacto (sin asignaciones)', not lineas,
      f'lineas {lineas}')
usos = [n.lineno for n in nodes
        if isinstance(n, ast.Name) and n.id == 'doc_num']
check('doc_num solo lo usa la auditoria', len(usos) > 0 and len(set(usos)) == 1,
      f'lineas {sorted(set(usos))}')
check('doc_tipo tampoco sombreado',
      not [n.lineno for n in nodes if asigna_a(n, 'doc_tipo')])

print(f'--- {len(fails)} fallos ---')
sys.exit(1 if fails else 0)
