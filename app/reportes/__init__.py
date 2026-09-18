"""
Auto-discovery: importa todos los .py del folder que tengan atributo ID.
Agregar un reporte = soltar el .py aquí. No tocar este archivo.
"""
import os
import importlib

CATALOGO = {}
_dir = os.path.dirname(__file__)
for _f in sorted(os.listdir(_dir)):
    if _f.endswith('.py') and not _f.startswith('_'):
        _mod = importlib.import_module(f'.{_f[:-3]}', package=__name__)
        if hasattr(_mod, 'ID'):
            CATALOGO[_mod.ID] = _mod
