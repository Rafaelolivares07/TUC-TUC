import os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env', encoding='utf-8-sig')

from app.db import get_db_connection
from app.blueprints.inventarios import _calcular_demanda_y_ciclo

conn = get_db_connection()
ddp, frecuencia, growth = _calcular_demanda_y_ciclo(
    conn, 59, 258, 173, 30, 7, 7, 1.0, -0.5, True
)
print(f"DDP: {ddp}, Frecuencia: {frecuencia}, Growth: {growth}")
demanda_proy = ddp * (1.0 + growth)
print(f"Demanda proy: {demanda_proy}")
max_comprar = demanda_proy * 3
print(f"Max comprar con 3 dias: {max_comprar}")
print(f"Stock actual: 173")
print(f"Cantidad neta: {max_comprar - 173}")
conn.close()
