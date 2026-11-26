"""Tipo publicado de una oferta en el catálogo compartido."""
from .asegurar import asegurar_una_vez

TIPOS_OFERTA = ('producto', 'servicio')
TIPO_OFERTA_SQL = "COALESCE(p.tipo_oferta, 'producto')"


def asegurar_tipo_oferta(conn):
    def migrar():
        conn.execute("""
            ALTER TABLE productos ADD COLUMN IF NOT EXISTS tipo_oferta text
            CHECK (tipo_oferta IN ('producto', 'servicio'))
        """)
        conn.execute("""
            DO $$
            BEGIN
                IF to_regclass('marketplace_solicitudes') IS NOT NULL THEN
                    UPDATE productos p SET tipo_oferta = 'servicio'
                     WHERE p.tipo_oferta IS NULL AND p.categoria = 'Servicios'
                       AND EXISTS (
                           SELECT 1 FROM marketplace_solicitudes s WHERE s.producto_id = p.id
                       );
                END IF;
            END;
            $$
        """)
        conn.commit()

    asegurar_una_vez('productos.tipo_oferta', migrar)
