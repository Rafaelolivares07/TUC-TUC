import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

def summarize_comp(comp_id):
    cur.execute('''
        SELECT id, cuenta, concepto, tipo, monto, fecha, tipo_documento, numero_documento, origen_tipo, origen_id
        FROM movimientos_contables
        WHERE comprobante_id = %s
        ORDER BY tipo, id ASC;
    ''', (comp_id,))
    rows = cur.fetchall()
    if not rows: return
    deb = sum(r[4] for r in rows if r[3] in ('debito', 'D'))
    cred = sum(r[4] for r in rows if r[3] in ('credito', 'C'))
    r0 = rows[0]
    diff = deb - cred
    
    # Buscar inventario relacionado
    num_doc = r0[7]
    orig_id = r0[9]
    ref_sub = str(orig_id).split(':')[-1] if orig_id else str(num_doc)
    cur.execute('''
        SELECT count(*), COALESCE(SUM(valor_total), 0), string_agg(DISTINCT tipo, ', ')
        FROM movimientos_inventario
        WHERE negocio_id = 59 AND (
            documento_numero = %s 
            OR CAST(referencia_id AS text) = %s
            OR CAST(numero_documento AS text) = %s
        );
    ''', (str(num_doc), ref_sub, str(num_doc)))
    inv_stat = cur.fetchone()

    print(f"\n--- COMP {comp_id}: {r0[6]} #{r0[7]} ({r0[5]}) | Origen: {r0[8]}:{r0[9]} ---")
    print(f"    Contabilidad: Deb = ${deb:,.2f} | Cred = ${cred:,.2f} | DESCUADRE = ${diff:,.2f}")
    print(f"    Inventario: {inv_stat[0]} movs | Suma valor_total: ${inv_stat[1]:,.2f} | Tipos: {inv_stat[2]}")
    debs = [f"{r[1]} ({r[2]}): ${r[4]:,.2f}" for r in rows if r[3] in ('debito', 'D')]
    creds = [f"{r[1]} ({r[2]}): ${r[4]:,.2f}" for r in rows if r[3] in ('credito', 'C')]
    print(f"    Debitos contables ({len(debs)}): " + " // ".join(debs))
    print(f"    Creditos contables ({len(creds)}): " + " // ".join(creds))

print("=== 1. FACTURAS DE PROVEEDOR ===")
for c in [14, 698, 512, 444, 588, 313, 19]:
    summarize_comp(c)

print("\n=== 2. PRODUCCIONES ===")
for c in [423, 373, 805]:
    summarize_comp(c)

cur.close()
conn.close()
