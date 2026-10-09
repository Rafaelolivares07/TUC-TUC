import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.db import get_db_connection

def inspect_desembolsos():
    app = create_app()
    with app.app_context():
        conn = get_db_connection()
        print("=== ULTIMOS 20 MOVIMIENTOS CONTABLES EN GENERAL ===")
        movs = conn.execute("""
            SELECT id, comprobante_id, tipo_documento, numero_documento, cuenta, concepto, tipo, monto, tercero_id, created_at, metodo_desembolso
            FROM movimientos_contables
            ORDER BY id DESC
            LIMIT 20
        """).fetchall()
        for m in movs:
            print(dict(m))

        print("\n=== ULTIMOS 10 COMPROBANTES CONTABLES ===")
        comps = conn.execute("""
            SELECT id, tipo_documento, numero_documento, fecha, concepto_general, total_debito, total_credito, created_at
            FROM comprobantes_contables
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()
        for c in comps:
            print(dict(c))
            
        print("\n=== TIPOS DOCUMENTO NEGOCIO (CONSECUTIVOS) ===")
        tdns = conn.execute("""
            SELECT id, negocio_id, codigo, nombre, consecutivo
            FROM tipos_documento_negocio
            WHERE negocio_id = 59 OR codigo LIKE '%GAS%' OR codigo LIKE '%CE%' OR codigo LIKE '%EG%'
        """).fetchall()
        for t in tdns:
            print(dict(t))
            
        conn.close()

if __name__ == "__main__":
    inspect_desembolsos()
