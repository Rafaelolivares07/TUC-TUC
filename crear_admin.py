# -*- coding: utf-8 -*-
"""
Script para crear o verificar usuario administrador
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Conectar a la base de datos
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cursor = conn.cursor()

print("=" * 80)
print("VERIFICAR/CREAR USUARIO ADMINISTRADOR")
print("=" * 80)

# Buscar usuario admin
cursor.execute("SELECT * FROM \"USUARIOS\" WHERE rol = 'Administrador'")
admin = cursor.fetchone()

if admin:
    print(f"\nUsuario administrador encontrado:")
    print(f"  ID: {admin['id']}")
    print(f"  Usuario: {admin['usuario']}")
    print(f"  Nombre: {admin['nombre']}")
    print(f"  Rol: {admin['rol']}")
else:
    print("\nNo se encontró usuario administrador.")
    print("Creando usuario admin por defecto...")

    cursor.execute("""
        INSERT INTO "USUARIOS" (usuario, password, nombre, rol, activo)
        VALUES ('admin', 'admin123', 'Administrador', 'Administrador', '1')
        RETURNING id
    """)
    new_id = cursor.fetchone()['id']
    conn.commit()

    print(f"\nUsuario administrador creado:")
    print(f"  ID: {new_id}")
    print(f"  Usuario: admin")
    print(f"  Password: admin123")
    print(f"  Rol: Administrador")

conn.close()
print("\n" + "=" * 80)
