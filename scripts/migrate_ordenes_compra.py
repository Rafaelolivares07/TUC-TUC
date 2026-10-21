import sys, os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
sys.path.insert(0, '/home/ubuntu/tuctucv2')

import app.db as db_mod
db_mod._db_url = os.environ.get('DATABASE_URL')
from app.db import get_db_connection

def migrate():
    conn = get_db_connection()
    try:
        print("1. Agregando columnas a terceros...")
        for col, col_type in [
            ('forma_pago_defecto', 'VARCHAR(50)'),
            ('dias_credito', 'INTEGER'),
            ('modalidad_entrega_defecto', 'VARCHAR(50)'),
            ('direccion_recogida', 'TEXT'),
        ]:
            conn.execute(f"ALTER TABLE terceros ADD COLUMN IF NOT EXISTS {col} {col_type}")

        print("2. Agregando columnas a productos...")
        conn.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS peso_variable BOOLEAN DEFAULT FALSE")
        conn.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS tolerancia_peso_pct NUMERIC(5,2) DEFAULT 10.0")

        print("3. Agregando direccion_entrega a centros_utilidad...")
        conn.execute("ALTER TABLE centros_utilidad ADD COLUMN IF NOT EXISTS direccion_entrega TEXT")

        print("4. Creando tabla ordenes_compra...")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ordenes_compra (
                id SERIAL PRIMARY KEY,
                negocio_id INTEGER NOT NULL REFERENCES terceros(id),
                proveedor_id INTEGER NOT NULL REFERENCES terceros(id),
                numero_oc VARCHAR(50) NOT NULL,
                token_publico VARCHAR(64) UNIQUE NOT NULL,
                fecha_emision TIMESTAMPTZ DEFAULT NOW(),
                estado VARCHAR(30) DEFAULT 'enviada',
                modalidad_entrega VARCHAR(30) DEFAULT 'sede',
                sede_id INTEGER,
                sede_nombre VARCHAR(100),
                direccion_entrega TEXT,
                forma_pago VARCHAR(50),
                dias_credito INTEGER,
                total_estimado NUMERIC(14,2) DEFAULT 0,
                total_confirmado NUMERIC(14,2),
                fecha_entrega_estimada DATE,
                franja_entrega VARCHAR(100),
                observaciones_comprador TEXT,
                observaciones_proveedor TEXT,
                conversacion_id INTEGER REFERENCES conversaciones(id),
                fecha_confirmacion TIMESTAMPTZ,
                fecha_recibida TIMESTAMPTZ,
                entrada_id INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        print("5. Creando tabla ordenes_compra_items...")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ordenes_compra_items (
                id SERIAL PRIMARY KEY,
                orden_compra_id INTEGER NOT NULL REFERENCES ordenes_compra(id) ON DELETE CASCADE,
                producto_id INTEGER NOT NULL REFERENCES productos(id),
                producto_nombre VARCHAR(255) NOT NULL,
                presentacion_id INTEGER,
                presentacion_nombre VARCHAR(100),
                unidades_presentacion NUMERIC(12,4) DEFAULT 1,
                peso_variable BOOLEAN DEFAULT FALSE,
                tolerancia_peso_pct NUMERIC(5,2) DEFAULT 0,
                cantidad_solicitada NUMERIC(12,4) NOT NULL,
                precio_unitario NUMERIC(14,2) NOT NULL,
                total_solicitado NUMERIC(14,2) NOT NULL,
                cantidad_confirmada NUMERIC(12,4),
                precio_confirmado NUMERIC(14,2),
                total_confirmado NUMERIC(14,2),
                estado_item VARCHAR(30) DEFAULT 'pendiente',
                motivo_cambio TEXT
            )
        """)

        conn.commit()
        print("Migración completada con éxito.")
    except Exception as e:
        conn.rollback()
        print("Error en migración:", e)
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
