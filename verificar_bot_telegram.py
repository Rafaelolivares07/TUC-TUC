# -*- coding: utf-8 -*-
import requests
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

TOKEN = "8486881295:AAFjs-SU74er_shs4KnQYImMtyU5OTXycng"

def verificar_bot():
    """Verifica la información del bot de Telegram"""

    print("Verificando informacion del bot de Telegram...")
    print()

    # Obtener información del bot
    url = f"https://api.telegram.org/bot{TOKEN}/getMe"

    try:
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            if data.get('ok'):
                bot_info = data.get('result', {})

                print("INFORMACION DEL BOT:")
                print("=" * 60)
                print(f"ID: {bot_info.get('id')}")
                print(f"Nombre: {bot_info.get('first_name')}")
                print(f"Username: @{bot_info.get('username')}")
                print(f"Es bot: {bot_info.get('is_bot')}")
                print(f"Puede unirse a grupos: {bot_info.get('can_join_groups')}")
                print(f"Puede leer todos los mensajes: {bot_info.get('can_read_all_group_messages')}")
                print(f"Soporta inline queries: {bot_info.get('supports_inline_queries')}")
                print("=" * 60)
                print()
                print(f"Para buscar el bot en Telegram, usa: @{bot_info.get('username')}")
                print()

                # Verificar webhook
                webhook_url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
                webhook_response = requests.get(webhook_url)

                if webhook_response.status_code == 200:
                    webhook_data = webhook_response.json()

                    if webhook_data.get('ok'):
                        webhook_info = webhook_data.get('result', {})

                        print("CONFIGURACION DEL WEBHOOK:")
                        print("=" * 60)
                        print(f"URL: {webhook_info.get('url', 'No configurado')}")
                        print(f"Actualizaciones pendientes: {webhook_info.get('pending_update_count', 0)}")

                        if webhook_info.get('last_error_date'):
                            print(f"Ultimo error: {webhook_info.get('last_error_message')}")
                        else:
                            print("Sin errores recientes")

                        print("=" * 60)

            else:
                print(f"ERROR: {data.get('description')}")
        else:
            print(f"ERROR HTTP: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    verificar_bot()
