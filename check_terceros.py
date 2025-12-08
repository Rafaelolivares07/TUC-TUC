import sqlite3

conn = sqlite3.connect('medicamentos.db')
cursor = conn.cursor()

cursor.execute("SELECT id, nombre FROM terceros ORDER BY nombre")
terceros = cursor.fetchall()

print('Terceros en la base de datos:')
print('-' * 60)
for row in terceros:
    print(f'ID: {row[0]:3d} | Nombre: {row[1]}')
print('-' * 60)
print(f'Total: {len(terceros)} terceros')

conn.close()
