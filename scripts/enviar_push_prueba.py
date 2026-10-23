import os
import json
import dotenv

dotenv.load_dotenv()

from app.db import init_db, get_db_connection
from pywebpush import webpush, WebPushException

init_db(None)

keys_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'vapid_keys.json')
with open(keys_path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

conn = get_db_connection()
subs = conn.execute("""
    SELECT id, tercero_id, endpoint, p256dh, auth, user_agent, activo
    FROM chat_push_subscriptions
    WHERE activo = TRUE
""").fetchall()
conn.close()

print(f"Total suscripciones activas encontradas: {len(subs)}")

if not subs:
    print("\n⚠️ AÚN NO HAY DISPOSITIVOS REGISTRADOS.")
    print("Para que tu celular y tu computador reciban la alerta Web Push:")
    print("1. Abre https://admin.tuc-tuc.co/chat2 en el navegador de tu computador o celular.")
    print("2. Abre el menú de Perfil (o haz clic en el botón 'Activar alertas con app cerrada').")
    print("3. Concede el permiso de notificaciones cuando el navegador te lo pida.")
    print("4. Vuelve a ejecutar este script o haz clic en 'Probar sonido y timbre ahora'.\n")
    exit(0)

payload = {
    'title': '🔔 Prueba de Timbre TUC TUC',
    'body': '¡Sonido y alerta verificados! Tu dispositivo está recibiendo avisos en segundo plano.',
    'icon': '/static/icons/icon-192.png',
    'badge': '/static/icons/icon-192.png',
    'vibrate': [300, 120, 300, 120, 450],
    'url': '/chat2',
    'token': ''
}

payload_str = json.dumps(payload)
priv_key = cfg['private_key']
claims = {'sub': cfg.get('claims_sub') or 'mailto:admin@tuc-tuc.co'}

conn = get_db_connection()
for s in subs:
    sub_info = {
        'endpoint': s['endpoint'],
        'keys': {
            'p256dh': s['p256dh'],
            'auth': s['auth']
        }
    }
    ua = s['user_agent'] or 'Desconocido'
    print(f"\nEnviando push a [ID={s['id']} | Tercero={s['tercero_id']} | UA={ua[:60]}]...")
    try:
        res = webpush(
            subscription_info=sub_info,
            data=payload_str,
            vapid_private_key=priv_key,
            vapid_claims=claims,
            timeout=8
        )
        print(f"✓ Éxito! Código HTTP: {res.status_code if res else 'OK'}")
    except WebPushException as ex:
        print(f"✗ Falló WebPush: {ex}")
        resp = getattr(ex, 'response', None)
        status_code = getattr(resp, 'status_code', None)
        if status_code in (404, 410):
            print(f"  Endpoint expirado o revocado (HTTP {status_code}). Desactivando...")
            conn.execute("UPDATE chat_push_subscriptions SET activo = FALSE WHERE id = %s", (s['id'],))
            conn.commit()
    except Exception as e:
        print(f"✗ Error: {e}")

conn.close()
print("\nProceso de prueba finalizado.")
