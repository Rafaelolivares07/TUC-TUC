import sqlite3
import pandas as pd

# 🔗 Conectar a la base de datos
conexion = sqlite3.connect("medicamentos.db")

query = """
SELECT 
    m.id AS ID_Medicamento,
    m.nombre AS Medicamento,
    f.nombre AS Fabricante,
    m.stock_actual AS StockTotal,
    p.stock_fabricante AS StockFabricante,
    p.precio AS Precio,
    p.fecha_actualizacion AS FechaPrecio
FROM medicamentos m
LEFT JOIN precios p ON p.medicamento_id = m.id
LEFT JOIN fabricantes f ON f.id = p.fabricante_id
ORDER BY m.id
LIMIT 20;
"""

df = pd.read_sql_query(query, conexion)
conexion.close()

print("\n====================== RESULTADO ======================\n")
print(df)
print("\n========================================================\n")
