#!/usr/bin/env python3
"""
Script para configurar el webhook de Telegram.
Esto le dice al bot de Telegram que envíe las actualizaciones a nuestra URL.
"""
import requests
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Token del bot (obtener de test_telegram.py o base de datos)
TOKEN = "8486881295:AAFjs-SU74er_shs4KnQYImMtyU5OTXycng"

# URL del webhook (debe ser HTTPS)
WEBHOOK_URL = "https://tuc-tuc.onrender.com/telegram/webhook"

def configurar_webhook():
    """Configura el webhook de Telegram"""

    print("=" * 60)
    print("CONFIGURAR WEBHOOK DE TELEGRAM")
    print("=" * 60)
    print()

    print(f"Token: {TOKEN[:20]}...")
    print(f"Webhook URL: {WEBHOOK_URL}")
    print()

    # Primero, eliminar cualquier webhook existente
    print("[1] Eliminando webhook anterior...")
    delete_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    response = requests.get(delete_url)

    if response.status_code == 200:
        print("    [OK] Webhook anterior eliminado")
    else:
        print(f"    [ERROR] No se pudo eliminar: {response.status_code}")
        print(f"    Response: {response.text}")

    print()

    # Configurar el nuevo webhook
    print("[2] Configurando nuevo webhook...")
    set_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    data = {
        'url': WEBHOOK_URL,
        'allowed_updates': ['message', 'callback_query']  # Solo recibir mensajes y callbacks de botones
    }

    response = requests.post(set_url, json=data)

    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            print("    [OK] Webhook configurado correctamente")
            print(f"    Descripción: {result.get('description')}")
        else:
            print(f"    [ERROR] Falló la configuración: {result}")
    else:
        print(f"    [ERROR] No se pudo configurar: {response.status_code}")
        print(f"    Response: {response.text}")

    print()

    # Verificar configuración del webhook
    print("[3] Verificando webhook configurado...")
    info_url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
    response = requests.get(info_url)

    if response.status_code == 200:
        info = response.json()
        if info.get('ok'):
            webhook_info = info.get('result', {})
            print("    [OK] Información del webhook:")
            print(f"      URL: {webhook_info.get('url')}")
            print(f"      Pending updates: {webhook_info.get('pending_update_count')}")
            print(f"      Allowed updates: {webhook_info.get('allowed_updates')}")

            if webhook_info.get('last_error_date'):
                from datetime import datetime
                error_date = datetime.fromtimestamp(webhook_info['last_error_date'])
                print(f"      [WARN] Último error: {error_date}")
                print(f"             Mensaje: {webhook_info.get('last_error_message')}")
        else:
            print(f"    [ERROR] No se pudo obtener info: {info}")
    else:
        print(f"    [ERROR] No se pudo verificar: {response.status_code}")

    print()
    print("=" * 60)
    print("CONFIGURACIÓN COMPLETADA")
    print("=" * 60)
    print()
    print("Para probar el bot:")
    print("1. Abre Telegram")
    print("2. Busca: @TucTucMedicamentosBot")
    print("3. Envía: /start")
    print("4. Envía: /vincular TU_TELEFONO")
    print()

if __name__ == '__main__':
    configurar_webhook()
