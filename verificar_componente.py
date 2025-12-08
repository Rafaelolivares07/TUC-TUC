import sqlite3

conn = sqlite3.connect('medicamentos.db')
conn.row_factory = sqlite3.Row

componente_id = 3877

print(f"\n🔍 Verificando si ID {componente_id} es componente activo de otros medicamentos:\n")

cursor = conn.execute("""
    SELECT id, nombre, componente_activo_id 
    FROM medicamentos 
    WHERE componente_activo_id = ?
""", (componente_id,))

medicamentos = cursor.fetchall()

if len(medicamentos) == 0:
    print(f"❌ NO se encontraron medicamentos que usen ID {componente_id} como componente activo")
else:
    print(f"✅ Se encontraron {len(medicamentos)} medicamento(s):\n")
    for med in medicamentos:
        print(f"   - [{med['id']}] {med['nombre']}")

conn.close()
