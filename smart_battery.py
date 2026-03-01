"""
smart_battery.py — Monitor de batería para automatización solar TUC TUC
Corre localmente en el laptop, reporta al servidor cada N minutos.

Configuración en .env (misma carpeta):
  SMART_DEVICE_TOKEN=<token del dispositivo en /domotica>
  SMART_SERVER_URL=https://tuc-tuc.onrender.com
  SMART_CHECK_INTERVAL=5   (minutos, opcional, default 5)
"""

import time
import os
import sys

try:
    import psutil
except ImportError:
    print("[ERROR] Instalar psutil: pip install psutil")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[ERROR] Instalar requests: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # sin dotenv, se usan variables de entorno del sistema


DEVICE_TOKEN    = os.getenv('SMART_DEVICE_TOKEN', '').strip()
SERVER_URL      = os.getenv('SMART_SERVER_URL', 'https://tuc-tuc.onrender.com').rstrip('/')
CHECK_INTERVAL  = int(os.getenv('SMART_CHECK_INTERVAL', '5'))  # minutos

if not DEVICE_TOKEN:
    print("[ERROR] SMART_DEVICE_TOKEN no configurado en .env")
    sys.exit(1)


def leer_bateria():
    """Retorna (pct, cargando) o (None, None) si no hay batería."""
    bat = psutil.sensors_battery()
    if bat is None:
        return None, None
    return int(bat.percent), bat.power_plugged


def reportar(bat_pct, cargando):
    """Envía reporte al servidor. Retorna la respuesta JSON."""
    url = f"{SERVER_URL}/api/domotica/reporte"
    payload = {
        'device_token': DEVICE_TOKEN,
        'bat_pct': bat_pct,
        'cargando': cargando,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def loop():
    print(f"[smart_battery] Iniciando — servidor: {SERVER_URL}")
    print(f"[smart_battery] Intervalo: {CHECK_INTERVAL} min | Token: {DEVICE_TOKEN[:8]}...")

    while True:
        try:
            bat_pct, cargando = leer_bateria()
            if bat_pct is None:
                print("[smart_battery] Sin batería detectada (desktop?). Esperando...")
            else:
                data = reportar(bat_pct, cargando)
                if data.get('ok'):
                    acciones = data.get('acciones', [])
                    msg = f"[smart_battery] Bat: {bat_pct}% {'⚡' if cargando else '🔋'} | hora: {data.get('hora')}h"
                    if acciones:
                        msg += f" | acciones: {[a['accion'] + ' ' + a['switch'] for a in acciones]}"
                    print(msg)
                else:
                    print(f"[smart_battery] Error servidor: {data.get('error')}")
        except requests.exceptions.RequestException as e:
            print(f"[smart_battery] Error de red: {e}")
        except Exception as e:
            print(f"[smart_battery] Error: {e}")

        time.sleep(CHECK_INTERVAL * 60)


if __name__ == '__main__':
    loop()
