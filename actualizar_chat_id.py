# -*- coding: utf-8 -*-
import requests
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Datos
url = "https://tuc-tuc.onrender.com/admin/actualizar-telegram-chat-id"
usuario_id = 16
chat_id = "6055213826"

# Session cookie (copia tu cookie de sesión desde el navegador)
session_cookie = ".eJwlzjkOwzAIAMC_sGdkMNjAZ0RhsFRV6dL_d5FOXb9hn2Mfy_bIz3mcz7Lfow7ZhCkHBQYNUqglRRNV00BrrQjGmWa1xjmWdFYwkWyqKUprgjTJkgkTNHOsNiexrCE-QRmIJpZSF93d3TzEHIeP6Qf79g_7"

headers = {
    "Content-Type": "application/json",
    "Cookie": f"session={session_cookie}"
}

data = {
    "usuario_id": usuario_id,
    "chat_id": chat_id
}

try:
    response = requests.post(url, json=data, headers=headers)

    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            print(f"\n✅ ÉXITO: {result.get('mensaje')}")
            print(f"Usuario: {result.get('usuario')}")
            print(f"Chat ID: {result.get('chat_id')}")
        else:
            print(f"\n❌ ERROR: {result.get('error')}")
    else:
        print(f"\n❌ Error HTTP: {response.status_code}")

except Exception as e:
    print(f"\n❌ Error: {e}")
