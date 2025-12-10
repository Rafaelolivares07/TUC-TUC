import os
from sqlalchemy import create_engine, text

# Usar la misma URL de la base de datos que la app
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://tuc_tuc_admin:1kfLANdRV90pUXUNQZkNjHg81mBgZR8i@dpg-cu66g4pu0jms738fepq0-a.oregon-postgres.render.com/tuc_tuc')

engine = create_engine(DATABASE_URL)

print("Verificando configuracion del sistema...\n")

with engine.connect() as conn:
    # Verificar si existe la tabla
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'CONFIGURACION_SISTEMA'
        )
    """))
    existe = result.fetchone()[0]

    if not existe:
        print("[X] La tabla CONFIGURACION_SISTEMA no existe!")
        print("\nCreando tabla...")

        conn.execute(text("""
            CREATE TABLE "CONFIGURACION_SISTEMA" (
                id INTEGER PRIMARY KEY,
                whatsapp_numero TEXT,
                telegram_token TEXT,
                telegram_chat_id TEXT,
                notificaciones_activas BOOLEAN DEFAULT TRUE,
                mensaje_bienvenida_whatsapp TEXT,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.execute(text("""
            INSERT INTO "CONFIGURACION_SISTEMA"
            (id, whatsapp_numero, telegram_token, telegram_chat_id, notificaciones_activas, mensaje_bienvenida_whatsapp)
            VALUES (1, '573166686397', '8486881295:AAFjs-SU74er_shs4KnQYImMtyU5OTXycng', '6055213826', TRUE,
            'Hola! Bienvenido a TUC-TUC Medicamentos. En que podemos ayudarte?')
        """))

        conn.commit()
        print("[OK] Tabla creada e inicializada correctamente\n")
    else:
        print("[OK] La tabla CONFIGURACION_SISTEMA existe\n")

    # Mostrar configuración actual
    result = conn.execute(text("SELECT * FROM \"CONFIGURACION_SISTEMA\" WHERE id = 1"))
    config = result.fetchone()

    if config:
        print("Configuracion actual:")
        print(f"   WhatsApp: {config[1]}")
        print(f"   Telegram Token: {config[2][:20]}...")
        print(f"   Telegram Chat ID: {config[3]}")
        print(f"   Notificaciones activas: {'SI' if config[4] else 'NO'}")
        print(f"   Mensaje bienvenida: {config[5][:50]}...")
    else:
        print("[!] No hay configuracion en la base de datos")
        print("\nInsertando configuracion inicial...")

        conn.execute(text("""
            INSERT INTO "CONFIGURACION_SISTEMA"
            (id, whatsapp_numero, telegram_token, telegram_chat_id, notificaciones_activas, mensaje_bienvenida_whatsapp)
            VALUES (1, '573166686397', '8486881295:AAFjs-SU74er_shs4KnQYImMtyU5OTXycng', '6055213826', TRUE,
            'Hola! Bienvenido a TUC-TUC Medicamentos. En que podemos ayudarte?')
        """))

        conn.commit()
        print("[OK] Configuracion inicial guardada correctamente")

print("\n[OK] Verificacion completada!")
