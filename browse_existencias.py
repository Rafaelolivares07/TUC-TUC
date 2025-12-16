import psycopg2
import os

DATABASE_URL = 'postgresql://tuc_tuc_admin:1kfLANdRV90pUXUNQZkNjHg81mBgZR8i@dpg-cu66g4pu0jms738fepq0-a.oregon-postgres.render.com/tuc_tuc'

try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    # Obtener últimos 20 registros
    cursor.execute("""
        SELECT id, medicamento_id, fabricante_id, tipo_movimiento,
               cantidad, fecha, id_tercero, pedido_id, estado, numero_documento
        FROM existencias
        ORDER BY id DESC
        LIMIT 20
    """)

    rows = cursor.fetchall()

    print("\nÚltimos 20 registros de EXISTENCIAS:")
    print("=" * 160)
    print(f"{'ID':>5} {'Med_ID':>7} {'Fab_ID':>7} {'Tipo':>10} {'Cant':>5} {'Fecha':>20} {'Tercero':>8} {'Pedido':>7} {'Estado':>12} {'NumDoc':>15}")
    print("-" * 160)

    for r in rows:
        print(f"{r[0]:>5} {r[1]:>7} {r[2]:>7} {r[3]:>10} {r[4]:>5} "
              f"{str(r[5])[:19]:>20} {str(r[6]) if r[6] else 'NULL':>8} "
              f"{str(r[7]) if r[7] else 'NULL':>7} {str(r[8]) if r[8] else 'NULL':>12} "
              f"{str(r[9]) if r[9] else 'NULL':>15}")

    print("-" * 160)
    print(f"\nTotal registros mostrados: {len(rows)}")

    # Contar totales
    cursor.execute("SELECT COUNT(*) FROM existencias")
    total = cursor.fetchone()[0]
    print(f"Total registros en tabla: {total}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
