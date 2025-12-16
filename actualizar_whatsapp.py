import os
from sqlalchemy import create_engine, text

# URL de la base de datos
DATABASE_URL = 'postgresql://tuc_tuc_admin:1kfLANdRV90pUXUNQZkNjHg81mBgZR8i@dpg-cu66g4pu0jms738fepq0-a.oregon-postgres.render.com/tuc_tuc'

engine = create_engine(DATABASE_URL)

print("Actualizando numero de WhatsApp en la base de datos...\n")

with engine.connect() as conn:
    # Actualizar el número de WhatsApp
    conn.execute(text("""
        UPDATE "CONFIGURACION_SISTEMA"
        SET whatsapp_numero = '573166686397',
            fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id = 1
    """))

    conn.commit()

    # Verificar el cambio
    result = conn.execute(text('SELECT whatsapp_numero FROM "CONFIGURACION_SISTEMA" WHERE id = 1'))
    nuevo_numero = result.fetchone()[0]

    print(f"[OK] Numero actualizado correctamente: {nuevo_numero}")
