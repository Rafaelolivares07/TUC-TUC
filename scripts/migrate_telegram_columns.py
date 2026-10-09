import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.blueprints.db import get_db_connection

def migrate():
    conn = get_db_connection()
    sqls = [
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50)",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50)",
        "ALTER TABLE terceros ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50)",
        "ALTER TABLE centros_utilidad ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50)",
    ]
    for sql in sqls:
        try:
            conn.execute(sql)
            conn.commit()
            print("OK:", sql)
        except Exception as e:
            conn.rollback()
            print("ERR:", sql, e)
    conn.close()
    print("Migration finished!")

if __name__ == "__main__":
    migrate()
