import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

producto_id = 260
bodega_kardex = 1

cur.execute("""
    SELECT m.id, m.tipo, m.motivo, m.cantidad, m.stock_anterior, m.stock_nuevo,
           m.valor_unitario, m.costo_und, m.valor_total, m.notas, m.tipo_documento,
           m.documento_numero, m.documento_fecha, m.created_at, m.bodega
    FROM movimientos_inventario m
    WHERE m.producto_id = %s AND (m.bodega = %s OR m.bodega IS NULL)
    ORDER BY COALESCE(m.documento_fecha, m.created_at::date) ASC, m.created_at ASC, m.id ASC
""", (producto_id, bodega_kardex))

rows = cur.fetchall()
saldo = 0.0
negativos = []

print(f"Total movimientos consultados: {len(rows)}")
for r in rows:
    m_id, tipo, motivo, cant, st_ant, st_nvo, vu, cu, vt, notas, td, num, f_doc, c_at, bod = r
    cant = float(cant or 0)
    if tipo == 'entrada':
        saldo += cant
    elif tipo == 'salida':
        saldo -= cant
    
    is_neg = (saldo < -0.0001)
    if is_neg:
        negativos.append((m_id, td, num, f_doc, c_at, tipo, cant, saldo))
        print(f"🔴 NEGATIVO [{len(negativos)}]: ID {m_id} | f_doc={f_doc} | c_at={c_at} | Doc: {td} #{num} | {tipo}/{motivo} | Cant: {cant} | Saldo: {saldo:,.4f}")
    else:
        # Imprimir si esta cerca de los negativos (Septiembre)
        f_str = str(f_doc or c_at)[:10]
        if '2026-09-01' <= f_str <= '2026-09-25':
            print(f"   OK: ID {m_id} | f_doc={f_doc} | c_at={c_at} | Doc: {td} #{num} | {tipo}/{motivo} | Cant: {cant} | Saldo: {saldo:,.4f}")

print(f"\nTotal negativos encontrados: {len(negativos)}")

cur.close()
conn.close()
