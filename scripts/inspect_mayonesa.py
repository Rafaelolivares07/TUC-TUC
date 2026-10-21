import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# 1. Productos con mayonesa en su nombre
cur.execute("""
    SELECT id, nombre, categoria, costo FROM productos WHERE negocio_id = 59 AND nombre ILIKE '%MAYONESA%';
""")
prods_mayo = cur.fetchall()
print("=== PRODUCTOS MAYONESA EN NEGOCIO 59 ===")
for p in prods_mayo:
    print(f"ID {p[0]} | {p[1]} | Categoria: {p[2]} | Costo: {p[3]}")

# 2. Donde se usa la mayonesa como componente en tarjeta_estandar
cur.execute("""
    SELECT te.producto_id, p_padre.nombre AS producto_padre, p_comp.id AS comp_id, p_comp.nombre AS componente, te.cantidad
    FROM tarjeta_estandar te
    JOIN productos p_padre ON p_padre.id = te.producto_id
    JOIN productos p_comp ON p_comp.id = te.componente_id
    WHERE p_padre.negocio_id = 59 AND p_comp.nombre ILIKE '%MAYONESA%';
""")
donde_se_usa = cur.fetchall()
print("\n=== RECETAS (tarjeta_estandar) DONDE SE USA MAYONESA COMO INGREDIENTE ===")
for r in donde_se_usa:
    print(f"Producto Padre: [{r[0]}] {r[1]} <-- USA {r[4]} de [{r[2]}] {r[3]}")

# 3. Y si la mayonesa misma tiene receta:
cur.execute("""
    SELECT te.producto_id, p_padre.nombre AS producto_padre, p_comp.id AS comp_id, p_comp.nombre AS componente, te.cantidad
    FROM tarjeta_estandar te
    JOIN productos p_padre ON p_padre.id = te.producto_id
    JOIN productos p_comp ON p_comp.id = te.componente_id
    WHERE p_padre.negocio_id = 59 AND p_padre.nombre ILIKE '%MAYONESA%';
""")
receta_de_mayo = cur.fetchall()
print("\n=== SI LA MAYONESA TIENE RECETA: ===")
for r in receta_de_mayo:
    print(f"Mayonesa [{r[0]}] {r[1]} <-- TIENE INGREDIENTE {r[4]} de [{r[2]}] {r[3]}")

# 4. Que salsas se usan en los sandwiches?
cur.execute("""
    SELECT te.producto_id, p_padre.nombre AS producto_padre, p_comp.id AS comp_id, p_comp.nombre AS componente, te.cantidad
    FROM tarjeta_estandar te
    JOIN productos p_padre ON p_padre.id = te.producto_id
    JOIN productos p_comp ON p_comp.id = te.componente_id
    WHERE p_padre.negocio_id = 59 AND (p_comp.nombre ILIKE '%SALSA%' OR p_comp.nombre ILIKE '%PITT%')
    LIMIT 10;
""")
salsas_en_sandwiches = cur.fetchall()
print("\n=== SALSAS USADAS EN PRODUCTOS/SANDWICHES: ===")
for r in salsas_en_sandwiches:
    print(f"[{r[0]}] {r[1]} <-- USA {r[4]} de [{r[2]}] {r[3]}")

cur.close()
conn.close()
