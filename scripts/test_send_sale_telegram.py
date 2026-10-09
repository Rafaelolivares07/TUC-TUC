import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.db import get_db_connection
from app.blueprints.tiendas import _enviar_telegram_tienda, _telegram_detalle_entrega_tienda, _telegram_resumen_pagos

def test_send_order_196():
    app = create_app()
    with app.app_context():
        conn = get_db_connection()
        p = conn.execute("SELECT * FROM pedidos WHERE id = 196").fetchone()
        r = conn.execute("SELECT * FROM restaurantes WHERE id = %s", (p['restaurante_id'],)).fetchone()
        chat_id = r['telegram_chat_id']
        print(f"Enviando copia de Factura 163 a {chat_id} ({r['nombre']})...")
        
        doc_label = "🧾 VENTA CAJA POS"
        num_doc_txt = f"\n📄 Factura #{p['numero_documento']}"
        items_txt = "  • 4x SANDWICH ESPECIAL ($96.000)"
        entrega = "🛒 Venta en Caja (Mostrador)"
        pagos_txt = "💵 Efectivo: $96.000"
        
        msg = f"{doc_label} en *{r['nombre']}*{num_doc_txt}\n\n👤 Cliente: {p['nombre_cliente']}\n📱 {p['telefono_cliente']}\n{entrega}\n\n{items_txt}\n\n💰 Total: ${int(p['total']):,}\n{pagos_txt}"
        
        _enviar_telegram_tienda(conn, chat_id, msg)
        print("Enviado con éxito a Telegram!")
        conn.close()

if __name__ == "__main__":
    test_send_order_196()
