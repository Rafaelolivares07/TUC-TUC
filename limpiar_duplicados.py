# -*- coding: utf-8 -*-
"""
Script para limpiar duplicados en 1_medicamentos.py
"""

with open('1_medicamentos.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total de líneas original: {len(lines)}")

# Encontrar el bloque duplicado
inicio_duplicado = None
fin_duplicado = None

for i, line in enumerate(lines):
    # El bloque duplicado empieza con el comentario "ESTE CÓDIGO SE DEBE INSERTAR"
    if i > 15000 and "# ESTE CÓDIGO SE DEBE INSERTAR EN 1_medicamentos.py" in line:
        inicio_duplicado = i
        print(f"Inicio del bloque duplicado encontrado en línea {i+1}")
        break

# El bloque duplicado termina antes del if __name__
for i in range(inicio_duplicado + 1 if inicio_duplicado else 15000, len(lines)):
    if "if __name__ == '__main__':" in lines[i]:
        fin_duplicado = i
        print(f"if __name__ encontrado en línea {i+1}")
        break

if inicio_duplicado and fin_duplicado:
    # Eliminar bloque duplicado (desde inicio_duplicado hasta fin_duplicado-1)
    print(f"Eliminando líneas {inicio_duplicado+1} a {fin_duplicado}")
    lines_limpias = lines[:inicio_duplicado] + lines[fin_duplicado:]

    # Ahora limpiar el contenido corrupto después de app.run()
    # Buscar la línea con app.run()
    for i, line in enumerate(lines_limpias):
        if "app.run(debug=True, host='0.0.0.0')" in line:
            print(f"app.run() encontrado en línea {i+1}")
            # Eliminar todo lo que esté en la misma línea después de app.run()
            if "# 1. Obtener competidores" in line:
                lines_limpias[i] = "    app.run(debug=True, host='0.0.0.0')\n"
                print(f"Línea {i+1} limpiada")

            # Eliminar todas las líneas después de app.run() que no deberían estar
            j = i + 1
            while j < len(lines_limpias):
                if lines_limpias[j].strip().startswith("competidores") or \
                   lines_limpias[j].strip().startswith("# 1. Obtener") or \
                   lines_limpias[j].strip().startswith("# 2. Productos"):
                    print(f"Eliminando línea basura {j+1}: {lines_limpias[j].strip()[:50]}")
                    del lines_limpias[j]
                else:
                    break
            break

    # Escribir archivo limpio
    with open('1_medicamentos.py', 'w', encoding='utf-8') as f:
        f.writelines(lines_limpias)

    print(f"Total de líneas después de limpieza: {len(lines_limpias)}")
    print("Archivo limpiado exitosamente")
else:
    print("ERROR: No se encontraron los marcadores para limpiar")
