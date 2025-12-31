# -*- coding: utf-8 -*-
"""
Script para diagnosticar por qué no aparecen medicamentos pendientes
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Conectar a la base de datos
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

print("=" * 80)
print("DIAGNÓSTICO: Medicamentos sin síntomas")
print("=" * 80)

# 1. Total de medicamentos
total = conn.execute("SELECT COUNT(*) as total FROM medicamentos").fetchone()
print(f"\n1. Total medicamentos: {total['total']}")

# 2. Medicamentos activos
activos = conn.execute("SELECT COUNT(*) as total FROM medicamentos WHERE activo = 'TRUE'").fetchone()
print(f"2. Medicamentos activos: {activos['total']}")

# 3. Medicamentos con al menos un síntoma
con_sintomas = conn.execute("""
    SELECT COUNT(DISTINCT m.id) as total
    FROM medicamentos m
    INNER JOIN medicamento_sintoma ms ON m.id = ms.medicamento_id
""").fetchone()
print(f"3. Medicamentos con síntomas: {con_sintomas['total']}")

# 4. Medicamentos SIN síntomas (activos)
sin_sintomas = conn.execute("""
    SELECT COUNT(DISTINCT m.id) as total
    FROM medicamentos m
    LEFT JOIN medicamento_sintoma ms ON m.id = ms.medicamento_id
    WHERE ms.sintoma_id IS NULL AND m.activo = 'TRUE'
""").fetchone()
print(f"4. Medicamentos ACTIVOS sin síntomas: {sin_sintomas['total']}")

# 5. Valores únicos del campo activo
valores_activo = conn.execute("""
    SELECT DISTINCT activo, COUNT(*) as cantidad
    FROM medicamentos
    GROUP BY activo
""").fetchall()
print(f"\n5. Valores del campo 'activo':")
for v in valores_activo:
    print(f"   - '{v['activo']}': {v['cantidad']} medicamentos")

# 6. Primeros 5 medicamentos sin síntomas
primeros = conn.execute("""
    SELECT m.id, m.nombre, m.activo, m.componente_activo_id
    FROM medicamentos m
    LEFT JOIN medicamento_sintoma ms ON m.id = ms.medicamento_id
    WHERE ms.sintoma_id IS NULL
    ORDER BY m.nombre
    LIMIT 5
""").fetchall()
print(f"\n6. Primeros 5 medicamentos sin síntomas (sin filtro de activo):")
for med in primeros:
    print(f"   - ID {med['id']}: {med['nombre']} (activo='{med['activo']}')")

# 7. La query exacta que usa el código
query_real = conn.execute("""
    SELECT m.id
    FROM medicamentos m
    LEFT JOIN medicamento_sintoma ms ON m.id = ms.medicamento_id
    WHERE ms.sintoma_id IS NULL AND m.activo = 'TRUE'
    ORDER BY
        CASE WHEN m.componente_activo_id IS NULL THEN 0 ELSE 1 END,
        (SELECT CASE WHEN p.precio > 0 THEN 0 ELSE 1 END FROM precios p WHERE p.medicamento_id = m.id LIMIT 1),
        m.nombre
    LIMIT 1
""").fetchone()
print(f"\n7. Resultado de la query exacta del código:")
if query_real:
    print(f"   ✓ Encontró medicamento ID: {query_real['id']}")
else:
    print(f"   ✗ NO encontró ningún medicamento pendiente")

conn.close()
print("\n" + "=" * 80)
