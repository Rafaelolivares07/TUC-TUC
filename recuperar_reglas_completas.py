#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para recuperar TODAS las reglas del archivo original sugerir_sintomas_flask.py
y generar archivo completo de reglas
"""

import re

# Leer archivo original
with open('sugerir_sintomas_flask.py', 'r', encoding='utf-8') as f:
    contenido_original = f.read()

# Extraer el diccionario REGLAS_DIAGNOSTICOS completo
match = re.search(r'REGLAS_DIAGNOSTICOS = \{(.*?)\n\}', contenido_original, re.DOTALL)

if match:
    reglas_texto = match.group(1)

    # Contar reglas
    reglas_count = len(re.findall(r"'[^']+'\s*:\s*\[", reglas_texto))

    print(f"OK Se encontraron {reglas_count} reglas en el archivo original")
    print("\nGuardando reglas completas...")

    # Guardar en archivo temporal para revisión
    with open('REGLAS_COMPLETAS_ORIGINAL.txt', 'w', encoding='utf-8') as f:
        f.write("REGLAS_DIAGNOSTICOS = {\n")
        f.write(reglas_texto)
        f.write("\n}")

    print("OK Reglas guardadas en REGLAS_COMPLETAS_ORIGINAL.txt")
    print("\nPuedes revisar el archivo y luego copiar las reglas faltantes")
else:
    print("ERROR No se pudo encontrar REGLAS_DIAGNOSTICOS")
