import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)
from app.db import get_db_connection

conn = get_db_connection()
try:
    rows = conn.execute("SELECT * FROM parametros_metodos_pago_negocio WHERE negocio_id = 59").fetchall()
    print("Total rows in parametros_metodos_pago_negocio for 59:", len(rows))
    for r in rows:
        print(dict(r))
    
    cfg = conn.execute("SELECT metodos_pago FROM config_negocio WHERE tercero_id = 59").fetchone()
    print("config_negocio.metodos_pago for 59:", cfg['metodos_pago'] if cfg else None)
    
    cat = conn.execute("SELECT * FROM metodos_pago_catalogo").fetchall()
    print("Total in metodos_pago_catalogo:", len(cat))
    for c in cat:
        print(dict(c))
finally:
    conn.close()
