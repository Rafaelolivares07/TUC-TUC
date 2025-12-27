# -*- coding: utf-8 -*-
import psycopg2
import os
import sys
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Conectar a la base de datos PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    # Usar URL de producción directamente
    DATABASE_URL = 'postgresql://tuc_tuc_admin:1kfLANdRV90pUXUNQZkNjHg81mBgZR8i@dpg-cu66g4pu0jms738fepq0-a.oregon-postgres.render.com/tuc_tuc'
    print("Usando DATABASE_URL de produccion")

try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    print("✅ OK - Conectado a PostgreSQL")
    print("=" * 80)
    print("MIGRACIÓN SISTEMA DE PASTILLEROS COMPARTIDOS")
    print("=" * 80)

    # ============================================
    # 1. CREAR TABLA PASTILLEROS
    # ============================================
    print("\n[1/6] Creando tabla 'pastilleros'...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pastilleros (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            creado_por_usuario_id INTEGER NOT NULL REFERENCES terceros(id) ON DELETE CASCADE,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Tabla 'pastilleros' creada")

    # ============================================
    # 2. CREAR TABLA RELACIONES_PASTILLERO
    # ============================================
    print("\n[2/6] Creando tabla 'relaciones_pastillero'...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS relaciones_pastillero (
            id SERIAL PRIMARY KEY,
            pastillero_id INTEGER NOT NULL REFERENCES pastilleros(id) ON DELETE CASCADE,
            usuario_id INTEGER NOT NULL REFERENCES terceros(id) ON DELETE CASCADE,
            tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('propietario', 'miembro', 'autorizado')),
            fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pastillero_id, usuario_id)
        )
    ''')
    print("✅ Tabla 'relaciones_pastillero' creada")

    # ============================================
    # 3. CREAR TABLA MENSAJES
    # ============================================
    print("\n[3/6] Creando tabla 'mensajes'...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensajes (
            id SERIAL PRIMARY KEY,
            remitente_id INTEGER NOT NULL REFERENCES terceros(id) ON DELETE CASCADE,
            destinatario_id INTEGER NOT NULL REFERENCES terceros(id) ON DELETE CASCADE,
            mensaje TEXT NOT NULL,
            tipo VARCHAR(30) NOT NULL DEFAULT 'texto' CHECK (tipo IN ('texto', 'invitacion_compartir', 'solicitud_acceso')),
            pastillero_id INTEGER REFERENCES pastilleros(id) ON DELETE CASCADE,
            estado VARCHAR(20) NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptado', 'rechazado', 'leido')),
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Tabla 'mensajes' creada")

    # ============================================
    # 4. MIGRAR DATOS EXISTENTES
    # ============================================
    print("\n[4/6] Migrando datos existentes...")

    # Obtener todos los usuarios que tienen medicamentos en el pastillero
    cursor.execute('''
        SELECT DISTINCT usuario_id, t.nombre
        FROM pastillero_usuarios p
        INNER JOIN terceros t ON p.usuario_id = t.id
    ''')
    usuarios_con_pastillero = cursor.fetchall()

    print(f"   📦 Encontrados {len(usuarios_con_pastillero)} usuarios con medicamentos")

    # Crear pastillero por defecto para cada usuario
    for usuario_id, nombre_usuario in usuarios_con_pastillero:
        # Crear pastillero
        cursor.execute('''
            INSERT INTO pastilleros (nombre, creado_por_usuario_id)
            VALUES (%s, %s)
            RETURNING id
        ''', (f"Mi pastillero", usuario_id))

        pastillero_id = cursor.fetchone()[0]

        # Crear relación de propietario
        cursor.execute('''
            INSERT INTO relaciones_pastillero (pastillero_id, usuario_id, tipo)
            VALUES (%s, %s, 'propietario')
        ''', (pastillero_id, usuario_id))

        print(f"   ✅ Pastillero creado para {nombre_usuario} (ID: {pastillero_id})")

    # ============================================
    # 5. AGREGAR COLUMNA pastillero_id A pastillero_usuarios
    # ============================================
    print("\n[5/6] Agregando columna 'pastillero_id' a 'pastillero_usuarios'...")
    cursor.execute('''
        ALTER TABLE pastillero_usuarios
        ADD COLUMN IF NOT EXISTS pastillero_id INTEGER REFERENCES pastilleros(id) ON DELETE CASCADE
    ''')
    print("✅ Columna 'pastillero_id' agregada")

    # Migrar medicamentos al nuevo sistema
    print("\n   Migrando medicamentos al nuevo sistema...")
    cursor.execute('''
        UPDATE pastillero_usuarios pu
        SET pastillero_id = p.id
        FROM pastilleros p
        WHERE pu.usuario_id = p.creado_por_usuario_id
        AND pu.pastillero_id IS NULL
    ''')

    medicamentos_migrados = cursor.rowcount
    print(f"   ✅ {medicamentos_migrados} medicamentos migrados")

    # ============================================
    # 6. HACER pastillero_id NOT NULL (después de migración)
    # ============================================
    print("\n[6/6] Configurando restricciones finales...")
    cursor.execute('''
        ALTER TABLE pastillero_usuarios
        ALTER COLUMN pastillero_id SET NOT NULL
    ''')
    print("✅ Columna 'pastillero_id' configurada como NOT NULL")

    # Confirmar cambios
    conn.commit()

    print("\n" + "=" * 80)
    print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 80)
    print("\n📊 RESUMEN:")
    print(f"   • Pastilleros creados: {len(usuarios_con_pastillero)}")
    print(f"   • Medicamentos migrados: {medicamentos_migrados}")
    print(f"   • Tablas nuevas: pastilleros, relaciones_pastillero, mensajes")
    print("\n💡 NOTA: La columna 'usuario_id' en 'pastillero_usuarios' se puede")
    print("   eliminar después de verificar que todo funciona correctamente.")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    if 'conn' in locals():
        conn.rollback()
