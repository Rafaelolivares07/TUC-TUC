"""Regression: modificar una entrada dispara recosteo automatico (motor unico).

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_entrada_modificacion.py
Cubre (sin BD real, via inspect sobre _registrar_entrada_inventario):
  - modificacion reune prods viejos (_prod_ids_to_recost) + nuevos (lineas)
  - modificacion invoca el MISMO motor con origen='entrada_modificacion'
  - el resumen recosteo_automatico se llena tambien en modificacion
  - la advertencia menciona la modificacion (no solo retroactiva)
Regla: guardar cambios sobre un documento existente re-registra sus lineas
y recostea los productos afectados con _recostear_producto (motor unico).
"""
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.blueprints.inventarios import _registrar_entrada_inventario  # noqa: E402

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


SRC = inspect.getsource(_registrar_entrada_inventario)

check('modif reune prods del doc viejo', "'_prod_ids_to_recost'" in SRC)
check('modif reune prods de lineas nuevas', "prods_to_recost.add(ln['producto_id'])" in SRC)
check("origen='entrada_modificacion'", "origen='entrada_modificacion'" in SRC)
check('mismo motor (llamada existe)', '_recostear_producto(' in SRC)
check('resumen se llena en modif', "'recosteo_automatico': recosteo_auto" in SRC)
check('aviso menciona modificacion', 'Modificaci' in SRC and 'recosteo autom' in SRC)

EN = (ROOT / 'templates' / 'entradas.html').read_text(encoding='utf-8')
AD = (ROOT / 'templates' / 'inventario_admin.html').read_text(encoding='utf-8')
check('boton explicito al modificar',
      'function actualizarBotonEntrada' in EN and 'function actualizarBotonEntrada' in AD)
check('boton dice guardar cambios',
      'Guardar cambios de la entrada' in EN and 'Guardar cambios de la entrada' in AD)
check('toast dice modificada', "'Entrada modificada'" in EN and "'Entrada modificada'" in AD)
check('boton se actualiza al cambiar modo',
      EN.count('actualizarBotonEntrada()') >= 3 and AD.count('actualizarBotonEntrada()') >= 3)

print(f'{10 - len(fails)}/10 checks, {len(fails)} fallos')
sys.exit(1 if fails else 0)
