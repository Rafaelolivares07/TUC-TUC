"""
agente_cliente.py — Versión para el cliente final
- Ventana simple con estado (sin consola negra)
- Doble clic → conecta automáticamente → técnico puede ver y controlar
- Botón "Cerrar sesión" para terminar
"""

import base64
import io
import os
import threading
import time
import sys
import tkinter as tk
from tkinter import ttk

try:
    import mss
    import pyautogui
    import socketio as sio_lib
    from PIL import Image
except ImportError as e:
    import tkinter.messagebox as mb
    mb.showerror("Error", f"Dependencia faltante: {e}\nContacta a tu técnico.")
    sys.exit(1)

pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0

# ─── Config (hardcodeado — el cliente no toca nada) ───────────────────────────
SERVER   = "https://tuc-tuc-remote.onrender.com"
TOKEN    = "tuctuc-remote-2026"
SESSION  = "default"
FPS      = 8
QUALITY  = 70
SCALE    = 0.85
# ─────────────────────────────────────────────────────────────────────────────

sio      = sio_lib.Client(reconnection=True, reconnection_delay=3, reconnection_attempts=0)
screen_w = screen_h = 0
running  = True


# ─── Captura y envío de frames ────────────────────────────────────────────────

def capturar_frame():
    with mss.mss() as sc:
        monitor = sc.monitors[1]
        sct_img = sc.grab(monitor)
        img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
    w = int(img.width * SCALE)
    h = int(img.height * SCALE)
    img = img.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=QUALITY)
    return base64.b64encode(buf.getvalue()).decode()


def loop_frames():
    interval = 1.0 / FPS
    while running:
        if sio.connected:
            try:
                img_b64 = capturar_frame()
                sio.emit('frame', {'session_id': SESSION, 'img': img_b64})
            except Exception:
                pass
        time.sleep(interval)


# ─── Ejecutar comandos recibidos ──────────────────────────────────────────────

def ejecutar_comando(data):
    tipo = data.get('type')
    try:
        if tipo == 'move':
            pyautogui.moveTo(int(data['x'] * screen_w), int(data['y'] * screen_h), duration=0)
        elif tipo == 'click':
            pyautogui.click(int(data['x'] * screen_w), int(data['y'] * screen_h),
                            button=data.get('button', 'left'))
        elif tipo == 'double_click':
            pyautogui.doubleClick(int(data['x'] * screen_w), int(data['y'] * screen_h))
        elif tipo == 'scroll':
            pyautogui.scroll(int(data.get('dy', 0)))
        elif tipo == 'key':
            key = data.get('key', '')
            key_map = {
                'Enter': 'enter', 'Backspace': 'backspace', 'Tab': 'tab',
                'Escape': 'esc', 'Delete': 'delete', 'ArrowUp': 'up',
                'ArrowDown': 'down', 'ArrowLeft': 'left', 'ArrowRight': 'right',
            }
            mapped = key_map.get(key, key if len(key) == 1 else None)
            if mapped:
                pyautogui.press(mapped)
    except Exception:
        pass


# ─── Ventana ──────────────────────────────────────────────────────────────────

class VentanaAsistencia:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Asistencia Técnica TUC TUC")
        self.root.geometry("340x200")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar)

        # Centrar ventana
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 340) // 2
        y = (self.root.winfo_screenheight() - 200) // 2
        self.root.geometry(f"340x200+{x}+{y}")

        # Título
        tk.Label(self.root, text="TUC TUC", font=("Arial", 18, "bold"),
                 fg="#2563eb").pack(pady=(20, 2))
        tk.Label(self.root, text="Asistencia Técnica Remota",
                 font=("Arial", 10), fg="#555").pack()

        # Estado
        self.frame_estado = tk.Frame(self.root)
        self.frame_estado.pack(pady=14)
        self.dot = tk.Label(self.frame_estado, text="●", font=("Arial", 14), fg="#999")
        self.dot.pack(side="left", padx=(0, 6))
        self.lbl_estado = tk.Label(self.frame_estado, text="Conectando...",
                                   font=("Arial", 11))
        self.lbl_estado.pack(side="left")

        # Botón cerrar
        self.btn = tk.Button(self.root, text="Cerrar sesión", command=self.cerrar,
                             bg="#ef4444", fg="white", font=("Arial", 10),
                             relief="flat", padx=16, pady=6, cursor="hand2")
        self.btn.pack(pady=4)

        tk.Label(self.root, text="Tu técnico puede ver y controlar tu pantalla.",
                 font=("Arial", 8), fg="#888").pack()

        self.lbl_archivo = tk.Label(self.root, text="", font=("Arial", 8), fg="#22c55e")
        self.lbl_archivo.pack(pady=(2, 0))

    def set_estado(self, color, texto):
        self.root.after(0, lambda: self._actualizar(color, texto))

    def set_archivo(self, texto, color="#22c55e"):
        self.root.after(0, lambda: self.lbl_archivo.config(text=texto, fg=color))

    def _actualizar(self, color, texto):
        colores = {'verde': '#22c55e', 'amarillo': '#eab308', 'rojo': '#ef4444', 'gris': '#999'}
        self.dot.config(fg=colores.get(color, '#999'))
        self.lbl_estado.config(text=texto)

    def cerrar(self):
        global running
        running = False
        try:
            sio.disconnect()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ─── SocketIO events ──────────────────────────────────────────────────────────

ventana: VentanaAsistencia = None

@sio.event
def connect():
    sio.emit('agent_join', {'token': TOKEN, 'session_id': SESSION})

@sio.on('agent_ready')
def on_ready():
    ventana.set_estado('amarillo', 'Esperando al técnico...')

@sio.on('agent_error')
def on_error(data):
    ventana.set_estado('rojo', f"Error: {data.get('msg', 'desconocido')}")

@sio.on('command')
def on_command(data):
    ejecutar_comando(data)


@sio.on('file_incoming')
def on_file_incoming(data):
    """Técnico envía un archivo — lo guardamos en el Desktop del usuario."""
    try:
        nombre = os.path.basename(data.get('nombre', 'archivo_recibido'))
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        os.makedirs(desktop, exist_ok=True)
        ruta_destino = os.path.join(desktop, nombre)
        contenido = base64.b64decode(data['b64'])
        with open(ruta_destino, 'wb') as f:
            f.write(contenido)
        ventana.set_archivo(f"📥 {nombre} guardado en Desktop")
    except Exception as e:
        ventana.set_archivo(f"✗ Error al recibir archivo: {e}", color="#f87171")


@sio.on('file_request')
def on_file_request(data):
    """Técnico pide un archivo — lo leemos y lo enviamos de vuelta."""
    ruta = data.get('ruta', '')
    try:
        with open(ruta, 'rb') as f:
            contenido = f.read()
        b64 = base64.b64encode(contenido).decode()
        nombre = os.path.basename(ruta)
        sio.emit('file_response', {'session_id': SESSION, 'nombre': nombre, 'b64': b64})
        ventana.set_archivo(f"📤 {nombre} enviado al técnico")
    except FileNotFoundError:
        sio.emit('file_response', {'session_id': SESSION, 'error': f'Archivo no encontrado: {ruta}'})
    except Exception as e:
        sio.emit('file_response', {'session_id': SESSION, 'error': str(e)})

@sio.event
def disconnect():
    if running:
        ventana.set_estado('gris', 'Reconectando...')


# ─── Hilo de conexión ─────────────────────────────────────────────────────────

def hilo_conexion():
    global screen_w, screen_h
    with mss.mss() as sc:
        m = sc.monitors[1]
        screen_w, screen_h = m['width'], m['height']

    while running:
        try:
            ventana.set_estado('gris', 'Conectando al servidor...')
            sio.connect(SERVER, transports=['websocket'])
            ventana.set_estado('verde', 'Conectado')
            sio.wait()
        except Exception:
            if running:
                ventana.set_estado('rojo', 'Sin conexión — reintentando...')
                time.sleep(5)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global ventana
    ventana = VentanaAsistencia()

    t1 = threading.Thread(target=hilo_conexion, daemon=True)
    t2 = threading.Thread(target=loop_frames, daemon=True)
    t1.start()
    t2.start()

    ventana.run()


if __name__ == '__main__':
    main()
