import sqlite3
import json

# Conectar a BD
conn = sqlite3.connect('medicamentos.db')
conn.row_factory = sqlite3.Row

# Cargar configuración
config = conn.execute("SELECT * FROM CONFIGURACION_PRECIOS LIMIT 1").fetchone()
CONFIG = dict(config)

print("=" * 80)
print("CONFIGURACIÓN CARGADA:")
print(f"  Recargo 1 cotización: {CONFIG['recargo_1_cotizacion']}%")
print(f"  Recargo 2 cotizaciones: {CONFIG['recargo_escaso']}%")
print(f"  Ganancia mínima: ${CONFIG['ganancia_min_escaso']:,}")
print(f"  Ganancia máxima: ${CONFIG['ganancia_max_escaso']:,}")
print(f"  Brecha 2 cot baja: ${CONFIG['umbral_brecha_2cot_baja']:,}")
print(f"  Brecha 2 cot alta: ${CONFIG['umbral_brecha_2cot_alta']:,}")
print(f"  Brecha 3 cot: ${CONFIG['umbral_brecha_3cot']:,}")
print(f"  Brecha 4+ cot: ${CONFIG['umbral_brecha_4cot']:,}")
print("=" * 80)

# Obtener productos con sus cotizaciones - 5 de cada tipo
query = """
WITH productos_con_cot AS (
    SELECT
        p.id as precio_id,
        p.medicamento_id,
        p.fabricante_id,
        p.precio as precio_actual,
        m.nombre as medicamento_nombre,
        f.nombre as fabricante_nombre,
        (SELECT COUNT(*) FROM precios_competencia pc
         WHERE pc.medicamento_id = p.medicamento_id
         AND pc.fabricante_id = p.fabricante_id) as num_cotizaciones
    FROM precios p
    INNER JOIN medicamentos m ON p.medicamento_id = m.id
    INNER JOIN fabricantes f ON p.fabricante_id = f.id
    WHERE p.precio > 0
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY num_cotizaciones ORDER BY precio_actual DESC) as rn
    FROM productos_con_cot
    WHERE num_cotizaciones > 0
)
SELECT precio_id, medicamento_id, fabricante_id, precio_actual, medicamento_nombre, fabricante_nombre, num_cotizaciones
FROM ranked
WHERE rn <= 5
ORDER BY num_cotizaciones ASC, precio_actual DESC
"""

productos = conn.execute(query).fetchall()

print(f"\nANALISIS DE {len(productos)} PRODUCTOS\n")

resultados = []

for prod in productos:
    # Obtener cotizaciones de este producto
    cotizaciones_query = """
    SELECT precio
    FROM precios_competencia
    WHERE medicamento_id = ? AND fabricante_id = ?
    ORDER BY precio ASC
    """
    cotizaciones = conn.execute(cotizaciones_query,
                               (prod['medicamento_id'], prod['fabricante_id'])).fetchall()

    precios_cot = [c['precio'] for c in cotizaciones]
    num_cot = len(precios_cot)

    # Calcular precio según reglas
    precio_nuevo = 0
    estrategia = ""

    if num_cot == 0:
        estrategia = "Sin cotizaciones - No publicar"
        precio_nuevo = prod['precio_actual']

    elif num_cot == 1:
        # 1 cotización: usar recargo_1_cotizacion
        precio_base = precios_cot[0]
        recargo = precio_base * (CONFIG['recargo_1_cotizacion'] / 100)
        precio_nuevo = precio_base + max(recargo, CONFIG['ganancia_min_escaso'])
        precio_nuevo = min(precio_nuevo, precio_base + CONFIG['ganancia_max_escaso'])
        estrategia = f"1 cot: Base ${precio_base:,} + {CONFIG['recargo_1_cotizacion']}%"

    elif num_cot == 2:
        # 2 cotizaciones: según brecha
        brecha = precios_cot[1] - precios_cot[0]

        if brecha < CONFIG['umbral_brecha_2cot_baja']:
            precio_base = precios_cot[0]  # Usar mínimo
            estrategia = f"2 cot (brecha ${brecha:,}): Usar mínimo ${precio_base:,}"
        elif brecha > CONFIG['umbral_brecha_2cot_alta']:
            precio_base = precios_cot[1]  # Usar máximo
            estrategia = f"2 cot (brecha ${brecha:,}): Usar máximo ${precio_base:,}"
        else:
            precio_base = sum(precios_cot) / 2  # Usar promedio
            estrategia = f"2 cot (brecha ${brecha:,}): Usar promedio ${precio_base:,}"

        recargo = precio_base * (CONFIG['recargo_escaso'] / 100)
        precio_nuevo = precio_base + max(recargo, CONFIG['ganancia_min_escaso'])
        precio_nuevo = min(precio_nuevo, precio_base + CONFIG['ganancia_max_escaso'])

    elif num_cot == 3:
        # 3 cotizaciones: según brecha 2da-3ra
        brecha_2_3 = precios_cot[2] - precios_cot[1]

        if brecha_2_3 < CONFIG['umbral_brecha_3cot']:
            # Precio entre 2da y 3ra
            precio_base = (precios_cot[1] + precios_cot[2]) / 2
            estrategia = f"3 cot (brecha 2-3: ${brecha_2_3:,}): Entre 2da-3ra ${precio_base:,}"
        else:
            # Precio = 3ra
            precio_base = precios_cot[2]
            estrategia = f"3 cot (brecha 2-3: ${brecha_2_3:,}): Igual 3ra ${precio_base:,}"

        precio_nuevo = precio_base + CONFIG['ganancia_min_escaso']
        precio_nuevo = min(precio_nuevo, precio_base + CONFIG['ganancia_max_escaso'])

    else:  # 4+ cotizaciones
        # 4+ cotizaciones: según brecha 3ra-4ta
        brecha_3_4 = precios_cot[3] - precios_cot[2]

        if brecha_3_4 < CONFIG['umbral_brecha_4cot']:
            # Precio = 3ra
            precio_base = precios_cot[2]
            estrategia = f"{num_cot} cot (brecha 3-4: ${brecha_3_4:,}): Igual 3ra ${precio_base:,}"
        else:
            # Precio entre 3ra y 4ta
            precio_base = (precios_cot[2] + precios_cot[3]) / 2
            estrategia = f"{num_cot} cot (brecha 3-4: ${brecha_3_4:,}): Entre 3ra-4ta ${precio_base:,}"

        precio_nuevo = precio_base + CONFIG['ganancia_min_escaso']
        precio_nuevo = min(precio_nuevo, precio_base + CONFIG['ganancia_max_escaso'])

    # Calcular ganancias (asumiendo domicilio $5k y entrega $3.333)
    ganancia_bruta_anterior = prod['precio_actual'] - (min(precios_cot) if precios_cot else 0)
    ganancia_bruta_nueva = precio_nuevo - (min(precios_cot) if precios_cot else 0)

    # Ganancia neta (incluye domicilio y entrega si aplica)
    domicilio = 5000 if prod['precio_actual'] < 50000 else 0
    costo_entrega = 3333
    ganancia_neta_anterior = ganancia_bruta_anterior + domicilio - costo_entrega
    ganancia_neta_nueva = ganancia_bruta_nueva + domicilio - costo_entrega

    resultado = {
        'nombre': f"{prod['medicamento_nombre']} - {prod['fabricante_nombre']}",
        'num_cotizaciones': num_cot,
        'cotizaciones': precios_cot,
        'precio_anterior': prod['precio_actual'],
        'precio_nuevo': round(precio_nuevo),
        'ganancia_bruta_anterior': round(ganancia_bruta_anterior),
        'ganancia_bruta_nueva': round(ganancia_bruta_nueva),
        'ganancia_neta_anterior': round(ganancia_neta_anterior),
        'ganancia_neta_nueva': round(ganancia_neta_nueva),
        'estrategia': estrategia,
        'cambio': round(precio_nuevo - prod['precio_actual'])
    }

    resultados.append(resultado)

    # Imprimir solo si hay cambio significativo (para no saturar)
    # Los detalles se verán en la tabla final

# Resumen final
print(f"\n\n{'='*80}")
print("TABLA COMPARATIVA DE MARGENES NETOS")
print(f"{'='*80}")

# Encabezados
print(f"\n{'Producto':<45} {'Cot':<4} {'Margen Ant':<12} {'Margen Nuevo':<12} {'Dif':<10} {'%':<7}")
print("-" * 100)

# Agrupar por número de cotizaciones
for num_cot in [1, 2, 3, 4]:
    productos_grupo = [r for r in resultados if r['num_cotizaciones'] == num_cot]
    if productos_grupo:
        print(f"\n--- {num_cot} COTIZACION{'ES' if num_cot > 1 else ''} ---")
        for r in productos_grupo:
            nombre_corto = r['nombre'][:44]
            margen_ant = r['ganancia_neta_anterior']
            margen_nuevo = r['ganancia_neta_nueva']
            dif = margen_nuevo - margen_ant
            pct = (dif / margen_ant * 100) if margen_ant != 0 else 0

            signo = '+' if dif >= 0 else ''
            print(f"{nombre_corto:<45} {num_cot:<4} ${margen_ant:>10,} ${margen_nuevo:>10,} {signo}${dif:>8,} {pct:>6.1f}%")

# Totales
print("\n" + "=" * 100)
total_productos = len(resultados)
precios_aumentan = len([r for r in resultados if r['cambio'] > 0])
precios_bajan = len([r for r in resultados if r['cambio'] < 0])
precios_igual = len([r for r in resultados if r['cambio'] == 0])

ganancia_neta_anterior_total = sum(r['ganancia_neta_anterior'] for r in resultados)
ganancia_neta_nueva_total = sum(r['ganancia_neta_nueva'] for r in resultados)
dif_total = ganancia_neta_nueva_total - ganancia_neta_anterior_total
pct_total = (dif_total / ganancia_neta_anterior_total * 100) if ganancia_neta_anterior_total != 0 else 0

print(f"\nTOTAL ({total_productos} productos):")
print(f"  Margen neto anterior: ${ganancia_neta_anterior_total:,}")
print(f"  Margen neto nuevo:    ${ganancia_neta_nueva_total:,}")
print(f"  Diferencia:           {'+' if dif_total >= 0 else ''}{dif_total:,} ({pct_total:+.1f}%)")
print(f"\nCambios en precios:")
print(f"  Aumentan: {precios_aumentan} ({precios_aumentan/total_productos*100:.1f}%)")
print(f"  Bajan:    {precios_bajan} ({precios_bajan/total_productos*100:.1f}%)")
print(f"  Igual:    {precios_igual} ({precios_igual/total_productos*100:.1f}%)")

print("\n(Este script NO modifica datos, solo analiza)")

conn.close()
