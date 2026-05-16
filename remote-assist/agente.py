"""
RemoteAssist — Agente (corre en el PC controlado)

- Captura pantalla con mss → comprime JPEG → envía al relay
- Recibe comandos del visor (click, move, key, scroll) → ejecuta con pyautogui
- Se reconecta automáticamente si pierde conexión

Uso:
  py agente.py
  py agente.py --server https://remote.tuc-tuc.co --token mi-token --session default
"""

import argparse
import base64
import io
import time
import sys
import random
import threading
import tkinter as tk

try:
    import mss
    import mss.tools
except ImportError:
    print("Falta mss: pip install mss")
    sys.exit(1)

try:
    import pyautogui
    pyautogui.FAILSAFE = False  # evita que al mover mouse a esquina detenga el agente
    pyautogui.PAUSE = 0
except ImportError:
    print("Falta pyautogui: pip install pyautogui")
    sys.exit(1)

try:
    import socketio as sio_lib
except ImportError:
    print("Falta python-socketio: pip install 'python-socketio[client]'")
    sys.exit(1)

from PIL import Image


def generar_codigo():
    digits = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return digits[:3] + '-' + digits[3:]


def mostrar_ventana(codigo):
    root = tk.Tk()
    root.title("TUC TUC Remote")
    root.geometry("300x200")
    root.resizable(False, False)
    root.configure(bg='#111827')
    try:
        root.attributes('-topmost', True)
    except Exception:
        pass
    tk.Label(root, text="TUC TUC Remote", bg='#111827', fg='#f3f4f6',
             font=('Arial', 13, 'bold')).pack(pady=(18, 2))
    tk.Label(root, text="Tu código de sesión:", bg='#111827', fg='#9ca3af',
             font=('Arial', 10)).pack()
    tk.Label(root, text=codigo, bg='#111827', fg='#22c55e',
             font=('Courier New', 38, 'bold')).pack(pady=6)
    tk.Label(root, text="Comparte este código con el técnico",
             bg='#111827', fg='#4b5563', font=('Arial', 9)).pack(pady=(2, 0))
    root.mainloop()


# ─── Config por defecto ───────────────────────────────────────────────────────
DEFAULT_SERVER  = "https://remote.tuc-tuc.co"
DEFAULT_TOKEN   = "tuctuc-remote-2026"
DEFAULT_SESSION = "default"
FPS_TARGET      = 8        # frames por segundo
QUALITY         = 70       # calidad JPEG (1-95) — menor = más rápido pero peor imagen
SCALE           = 0.85     # escalar pantalla antes de enviar (reduce ancho de banda)
# ─────────────────────────────────────────────────────────────────────────────

sio = sio_lib.Client(reconnection=True, reconnection_delay=3, reconnection_attempts=0)
screen_w = screen_h = 0  # se llena al conectar


def capturar_frame():
    """Captura pantalla, escala, comprime a JPEG, retorna base64."""
    with mss.mss() as sc:
        monitor = sc.monitors[1]  # monitor principal
        sct_img = sc.grab(monitor)
        img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')

    w = int(img.width * SCALE)
    h = int(img.height * SCALE)
    img = img.resize((w, h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=QUALITY, optimize=False)
    return base64.b64encode(buf.getvalue()).decode(), img.width, img.height


def ejecutar_comando(data):
    tipo = data.get('type')
    try:
        if tipo == 'move':
            rx, ry = data['x'], data['y']
            x = int(rx * screen_w)
            y = int(ry * screen_h)
            pyautogui.moveTo(x, y, duration=0)

        elif tipo == 'click':
            rx, ry = data['x'], data['y']
            x = int(rx * screen_w)
            y = int(ry * screen_h)
            btn = data.get('button', 'left')
            pyautogui.click(x, y, button=btn)

        elif tipo == 'double_click':
            rx, ry = data['x'], data['y']
            x = int(rx * screen_w)
            y = int(ry * screen_h)
            pyautogui.doubleClick(x, y)

        elif tipo == 'scroll':
            dy = data.get('dy', 0)
            pyautogui.scroll(int(dy))

        elif tipo == 'key':
            key = data.get('key', '')
            key_map = {
                'Enter': 'enter', 'Backspace': 'backspace', 'Tab': 'tab',
                'Escape': 'esc', 'Delete': 'delete', 'ArrowUp': 'up',
                'ArrowDown': 'down', 'ArrowLeft': 'left', 'ArrowRight': 'right',
                'Home': 'home', 'End': 'end', 'PageUp': 'pageup',
                'PageDown': 'pagedown', 'F1': 'f1', 'F2': 'f2', 'F3': 'f3',
                'F4': 'f4', 'F5': 'f5', 'F11': 'f11', 'F12': 'f12',
                'Control': None, 'Shift': None, 'Alt': None, 'Meta': None,
            }
            mapped = key_map.get(key, key if len(key) == 1 else None)
            if mapped:
                pyautogui.press(mapped)

    except Exception as e:
        print(f'  ✗ Error ejecutando {tipo}: {e}')


# ─── Eventos SocketIO ─────────────────────────────────────────────────────────

@sio.event
def connect():
    print('✓ Conectado al relay')


@sio.on('agent_ready')
def on_ready():
    print('✓ Agente autenticado — esperando visor...')


@sio.on('agent_error')
def on_error(data):
    print(f'✗ Error: {data.get("msg")}')
    sio.disconnect()


@sio.on('command')
def on_command(data):
    ejecutar_comando(data)


@sio.event
def disconnect():
    print('  Desconectado del relay — reconectando...')


# ─── Loop principal ───────────────────────────────────────────────────────────

def main():
    global screen_w, screen_h, QUALITY, SCALE

    parser = argparse.ArgumentParser(description='RemoteAssist Agente')
    parser.add_argument('--server',  default=DEFAULT_SERVER)
    parser.add_argument('--token',   default=DEFAULT_TOKEN)
    parser.add_argument('--fps',     type=int, default=FPS_TARGET)
    parser.add_argument('--quality', type=int, default=QUALITY)
    parser.add_argument('--scale',   type=float, default=SCALE)
    args = parser.parse_args()
    QUALITY = args.quality
    SCALE   = args.scale
    interval = 1.0 / args.fps

    # Detectar resolución de pantalla real
    with mss.mss() as sc:
        m = sc.monitors[1]
        screen_w = m['width']
        screen_h = m['height']

    codigo = generar_codigo()
    session_id = codigo.replace('-', '')  # "847293" sin guion

    print('=' * 50)
    print('  RemoteAssist — Agente')
    print(f'  Servidor : {args.server}')
    print(f'  Código   : {codigo}')
    print(f'  Sesión   : {session_id}')
    print('=' * 50)

    # Socket loop en thread daemon
    def socket_loop():
        while True:
            try:
                sio.connect(args.server, transports=['websocket'])
                sio.emit('agent_join', {'token': args.token, 'session_id': session_id})
                while sio.connected:
                    t0 = time.time()
                    try:
                        img_b64, _, _ = capturar_frame()
                        sio.emit('frame', {'session_id': session_id, 'img': img_b64})
                    except Exception as e:
                        print(f'  ✗ Frame: {e}')
                    elapsed = time.time() - t0
                    sleep_time = max(0, interval - elapsed)
                    time.sleep(sleep_time)
                sio.wait()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f'  ✗ Conexión: {e} — reintentando en 5s...')
                time.sleep(5)

    t = threading.Thread(target=socket_loop, daemon=True)
    t.start()

    # Ventana tkinter en main thread
    mostrar_ventana(codigo)


if __name__ == '__main__':
    main()
