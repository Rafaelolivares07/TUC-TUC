import sqlite3

# Abrir la base de datos
conn = sqlite3.connect("medicamentos.db")
cursor = conn.cursor()

# Ver las tablas
print("Tablas existentes:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())

# Ver columnas de la tabla medicamentos
print("\nColumnas de medicamentos:")
cursor.execute("PRAGMA table_info(medicamentos);")
print(cursor.fetchall())

conn.close()
