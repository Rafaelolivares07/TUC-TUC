import os
import sys
import json
import time
import requests
from datetime import datetime
import subprocess
import psycopg2

# Configuración básica
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_config.json")

# Detectar rutas según sistema operativo
IS_WINDOWS = os.name == 'nt'
if IS_WINDOWS:
    BRIDGE_FILE = r"C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\bridge_chat.md"
    PEM_FILE = r"C:\Users\RAFAEL OLIVARES\Documents\tuctuc-linux.pem"
    SERVER_PATH = "ubuntu@18.217.231.167:/home/ubuntu/tuctucv2/bridge_chat.md"
    DB_CONN_STR = "postgresql://postgres:halo23032001@localhost:5435/tuctuc" # Puerto local de túnel
else:
    BRIDGE_FILE = "/home/ubuntu/tuctucv2/bridge_chat.md"
    PEM_FILE = None
    SERVER_PATH = None
    DB_CONN_STR = "postgresql://postgres:halo23032001@localhost:5432/tuctuc" # Puerto directo en servidor

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def deploy_to_aws():
    """Copia el bridge_chat.md a AWS mediante scp (solo si corre en Windows)."""
    if not IS_WINDOWS:
        return  # Ya está corriendo en el servidor, no necesita scp
    try:
        cmd = f'scp -o StrictHostKeyChecking=no -i "{PEM_FILE}" "{BRIDGE_FILE}" {SERVER_PATH}'
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[Bridge] Sincronizado bridge_chat.md con AWS.")
    except Exception as e:
        print(f"[Bridge] Error al sincronizar con AWS: {e}")


def sync_from_aws():
    """Descarga bridge_chat.md desde AWS si tiene más contenido que el local."""
    if not IS_WINDOWS:
        return
    try:
        tmp = f"{BRIDGE_FILE}.aws_tmp"
        cmd = f'scp -o StrictHostKeyChecking=no -i "{PEM_FILE}" {SERVER_PATH} "{tmp}"'
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode != 0 or not os.path.exists(tmp):
            return
        aws_size = os.path.getsize(tmp)
        local_size = os.path.getsize(BRIDGE_FILE) if os.path.exists(BRIDGE_FILE) else 0
        if aws_size > local_size:
            with open(tmp, 'r', encoding='utf-8') as f:
                aws_content = f.read()
            if os.path.exists(BRIDGE_FILE):
                with open(BRIDGE_FILE, 'r', encoding='utf-8') as f:
                    local_content = f.read()
                new_part = aws_content[len(local_content):]
            else:
                new_part = aws_content
            if new_part.strip():
                with open(BRIDGE_FILE, 'a', encoding='utf-8') as f:
                    f.write(new_part)
                print(f"[AWS -> Bridge] Nuevas tareas sincronizadas ({len(new_part)} chars)")
        os.remove(tmp)
    except Exception as e:
        print(f"[AWS -> Bridge] Error: {e}")

def get_telegram_updates(token, offset):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"offset": offset, "timeout": 10}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json().get("result", [])
    except Exception as e:
        print(f"[Telegram] Error al consultar actualizaciones: {e}")
    return []

def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[Telegram] Error al enviar mensaje: {e}")

def insert_message_to_db(text):
    """Inserta el mensaje en la tabla mensajes de la base de datos."""
    try:
        conn = psycopg2.connect(DB_CONN_STR)
        cur = conn.cursor()
        # Rafael ID = 38, Merlin ID = 47, Conversacion ID = 1
        cur.execute("""
            INSERT INTO mensajes (remitente_id, destinatario_id, mensaje, tipo, conversacion_id, estado, fecha)
            VALUES (38, 47, %s, 'texto', 1, 'pendiente', CURRENT_TIMESTAMP)
        """, (text,))
        conn.commit()
        cur.close()
        conn.close()
        print("[DB] Insertado mensaje pendiente de Rafael en BD.")
    except Exception as e:
        print(f"[DB] Error insertando mensaje en BD: {e}")

def check_for_agent_replies(token, chat_id):
    """Revisa si hay respuestas pendientes de Merlin para enviarlas a Telegram."""
    try:
        conn = psycopg2.connect(DB_CONN_STR)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, mensaje FROM mensajes
            WHERE conversacion_id = 1 AND remitente_id = 47 AND estado = 'pendiente'
            ORDER BY id ASC
        """)
        rows = cur.fetchall()
        for r in rows:
            msg_id, msg_text = r[0], r[1]
            if msg_text.startswith("🤖 *Antigravity:*") or msg_text.startswith("👨‍💻 *Open Code:*") or msg_text.startswith("🧙‍♂️ *Merlin:*"):
                send_telegram_message(token, chat_id, msg_text)
            else:
                send_telegram_message(token, chat_id, f"🧙‍♂️ *Merlin:* {msg_text}")
            print(f"[DB -> Telegram] Enviada respuesta (ID: {msg_id})")
            cur.execute("UPDATE mensajes SET estado = 'leido' WHERE id = %s", (msg_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        pass  # Evitar spam en la consola por fallos temporales de red

def main():
    config = load_config()
    token = config.get("token")
    chat_id = config.get("chat_id")

    if not token:
        print("="*60)
        print(" CONFIGURACIÓN DEL BOT DE TELEGRAM")
        print(" Por favor, crea un bot con @BotFather en Telegram y copia el Token.")
        print("="*60)
        token = input("Ingresa tu Bot Token: ").strip()
        config["token"] = token
        save_config(config)

    if not chat_id:
        print("\nPara obtener tu Chat ID, abre un chat con tu bot en Telegram y envíale cualquier mensaje.")
        input("Presiona Enter cuando le hayas enviado el mensaje...")
        
        # Buscar el chat_id en las actualizaciones
        updates = get_telegram_updates(token, 0)
        if updates:
            chat_id = updates[-1]["message"]["chat"]["id"]
            config["chat_id"] = chat_id
            save_config(config)
            print(f"✓ Chat ID detectado y guardado: {chat_id}")
            send_telegram_message(token, chat_id, "¡Enlace de Telegram activado correctamente con TucTuc!")
        else:
            print("❌ No se detectaron mensajes en el bot. Intenta de nuevo ejecutando el script.")
            return

    print(f"\n[Bridge] Iniciado. Monitoreando {BRIDGE_FILE} y Base de Datos...")
    
    # Inicializar tamaño del archivo
    if os.path.exists(BRIDGE_FILE):
        last_size = os.path.getsize(BRIDGE_FILE)
    else:
        last_size = 0
        with open(BRIDGE_FILE, "w", encoding="utf-8") as f:
            f.write("# 🤝 Puente Conversacional (Gemini ⇆ Open Code)\n\n")

    offset = 0
    
    # Intentar obtener las actualizaciones previas para evitar procesar mensajes viejos
    updates = get_telegram_updates(token, 0)
    if updates:
        offset = updates[-1]["update_id"] + 1

    while True:
        try:
            # 1. Chequear actualizaciones de Telegram
            updates = get_telegram_updates(token, offset)
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg:
                    continue
                
                from_id = msg["chat"]["id"]
                if str(from_id) != str(chat_id):
                    continue  # Ignorar mensajes de otros usuarios
                
                text = msg.get("text")
                if not text:
                    continue
                
                # Escribir en el bridge_chat.md
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                entry = f"\n---\n\n### [{timestamp}] 👤 Rafael (vía Telegram):\n\n{text}\n"
                
                with open(BRIDGE_FILE, "a", encoding="utf-8") as f:
                    f.write(entry)
                
                # Actualizar el last_size local para que el bridge no se lo auto-envíe
                last_size = os.path.getsize(BRIDGE_FILE)
                print(f"[Telegram -> Bridge] Registrado mensaje de Rafael.")
                
                # Desplegar a AWS
                deploy_to_aws()

                # Insertar en la Base de Datos para activar el Daemon de Merlin
                insert_message_to_db(text)

            # 1b. Sincronizar bridge_chat.md desde AWS → local (tareas de agenda)
            sync_from_aws()

            # 2. Chequear si el bridge_chat.md fue modificado por los agentes
            if os.path.exists(BRIDGE_FILE):
                curr_size = os.path.getsize(BRIDGE_FILE)
                if curr_size > last_size:
                    # Leer la sección añadida
                    with open(BRIDGE_FILE, "r", encoding="utf-8") as f:
                        f.seek(last_size)
                        new_content = f.read().strip()
                    
                    last_size = curr_size
                    
                    if new_content:
                        # No reenviar a Telegram mensajes que vienen del backend (agenda)
                        if '👤 Rafael (Agenda)' not in new_content:
                            send_telegram_message(token, chat_id, f"📝 *Actualización en Sala de Juntas:*\n\n{new_content}")
                            print("[Bridge -> Telegram] Enviada actualización a Rafael.")
                        else:
                            print("[Bridge] Contenido del backend detectado, no reenviado a Telegram.")
                elif curr_size < last_size:
                    # El archivo se redujo o truncó, reajustar
                    last_size = curr_size

            # 3. Consultar respuestas del Agente en la Base de Datos
            check_for_agent_replies(token, chat_id)

            time.sleep(2)
        except KeyboardInterrupt:
            print("\n[Bridge] Detenido por el usuario.")
            break
        except Exception as e:
            print(f"[Bridge] Error en loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
