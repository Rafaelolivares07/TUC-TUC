import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable', cursor_factory=RealDictCursor)
cur = conn.cursor()

# 1. Update presentaciones
print("1. Actualizando presentaciones...")
cur.execute("""
    UPDATE presentaciones SET equivalencia = 1810.0, nombre = 'Tarro x 1810 grs' WHERE id = 30;
    UPDATE presentaciones SET equivalencia = 793800.0, nombre = 'Tarro x 793800 mlgr' WHERE id = 21;
    UPDATE presentaciones SET equivalencia = 453000.0, nombre = 'Tarro x 453000 mlgrs' WHERE id = 27;
    UPDATE presentaciones SET equivalencia = 680400.0, nombre = 'Tarro x 680400 mlgrs' WHERE id = 23;
""")

# 2. Fix the 4 PriceSmart movements in movimientos_inventario
print("2. Corrigiendo movimientos de entrada de PriceSmart...")
cur.execute("""
    UPDATE movimientos_inventario
    SET cantidad = 1810.0,
        valor_unitario = 22900.0 / 1810.0
    WHERE id = 2724;

    UPDATE movimientos_inventario
    SET cantidad = 793800.0,
        valor_unitario = 42500.0 / 793800.0
    WHERE id = 2723;

    UPDATE movimientos_inventario
    SET cantidad = 453000.0,
        valor_unitario = 52900.0 / 453000.0
    WHERE id = 2722;

    UPDATE movimientos_inventario
    SET cantidad = 680400.0,
        valor_unitario = 30900.0 / 680400.0
    WHERE id = 2721;
""")

# 3. Recalculate full chain for each of the 4 products
prods = [310, 300, 304, 272]
print("3. Recalculando cadena de Kardex, saldos y costos promedio ponderados...")

for pid in prods:
    cur.execute("""
        SELECT id, created_at, documento_fecha, tipo, motivo, cantidad, valor_unitario, valor_total,
               stock_anterior, stock_nuevo, costo_und, documento_numero, proveedor_nombre
        FROM movimientos_inventario
        WHERE producto_id = %s
        ORDER BY id ASC
    """, (pid,))
    movs = cur.fetchall()
    
    current_stock = Decimal('0.0')
    current_avg_cost = Decimal('0.0')
    
    for m in movs:
        m_id = m['id']
        m_tipo = (m['tipo'] or '').lower()
        m_motivo = (m['motivo'] or '').lower()
        cant = Decimal(str(m['cantidad'] or 0))
        
        stock_ant = current_stock
        
        if m_tipo == 'entrada' or (m_tipo == 'ajuste' and m_motivo != 'ajuste_negativo'):
            # Entrada de inventario
            v_total = Decimal(str(m['valor_total'] or (cant * Decimal(str(m['valor_unitario'] or 0)))))
            v_unit = v_total / cant if cant > 0 else Decimal('0.0')
            
            # Recalcular costo promedio ponderado
            total_val_before = current_stock * current_avg_cost
            new_stock = current_stock + cant
            
            if new_stock > 0:
                current_avg_cost = (total_val_before + v_total) / new_stock
            else:
                current_avg_cost = v_unit
            
            current_stock = new_stock
            
            cur.execute("""
                UPDATE movimientos_inventario
                SET stock_anterior = %s,
                    stock_nuevo = %s,
                    costo_und = %s,
                    valor_unitario = %s,
                    valor_total = %s
                WHERE id = %s
            """, (stock_ant, current_stock, current_avg_cost, v_unit, v_total, m_id))
            
        else:
            # Salida de inventario (venta, produccion, ajuste_negativo, etc.)
            new_stock = current_stock - cant
            current_stock = new_stock
            salida_costo_unit = current_avg_cost
            salida_total = cant * salida_costo_unit
            
            cur.execute("""
                UPDATE movimientos_inventario
                SET stock_anterior = %s,
                    stock_nuevo = %s,
                    costo_und = %s,
                    valor_unitario = %s,
                    valor_total = %s
                WHERE id = %s
            """, (stock_ant, current_stock, current_avg_cost, salida_costo_unit, salida_total, m_id))
            
    # Update saldos_inventario and productos
    valor_existencia = current_stock * current_avg_cost
    cur.execute("""
        UPDATE saldos_inventario
        SET stock = %s,
            costo_und = %s,
            valor_existencia = %s,
            updated_at = NOW()
        WHERE producto_id = %s;

        UPDATE productos
        SET costo = %s
        WHERE id = %s;
    """, (current_stock, current_avg_cost, valor_existencia, pid, current_avg_cost, pid))
    
    cur.execute("SELECT nombre FROM productos WHERE id = %s", (pid,))
    p_nom = cur.fetchone()['nombre']
    print(f"  -> {p_nom} (ID {pid}): Stock final = {current_stock}, Costo unitario = ${current_avg_cost:.6f}, Valor existencia = ${valor_existencia:.2f}")

conn.commit()
print("¡Recálculo exitoso y base de datos sincronizada!")
