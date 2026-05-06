"""
agente_cliente.py — Versión para el cliente final
- Ventana simple con estado (sin consola negra)
- Doble clic → conecta automáticamente → técnico puede ver y controlar
- Botón "Cerrar sesión" para terminar
"""

import base64
import io
import os
import zipfile
import subprocess
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

# ─── Config ───────────────────────────────────────────────────────────────────
SERVER   = "https://remote.tuc-tuc.co"
TOKEN    = "tuctuc-remote-2026"
SESSION  = __import__('random').randint(100000, 999999).__str__()
VERSION  = "V1.5"
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
        elif tipo == 'calibrate_show':
            ventana.root.after(0, _crear_overlay_calibracion)
        elif tipo == 'calibrate_hide':
            ventana.root.after(0, _ocultar_overlay_calibracion)
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
        tk.Label(self.root, text=VERSION,
                 font=("Arial", 8), fg="#aaa").pack()

        # Código de sesión
        codigo = SESSION[:3] + "-" + SESSION[3:]
        tk.Label(self.root, text="Tu código de sesión:",
                 font=("Arial", 9), fg="#888").pack(pady=(10, 0))
        tk.Label(self.root, text=codigo,
                 font=("Courier New", 26, "bold"), fg="#16a34a").pack()

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
_calib_win   = None

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


CHUNK_SIZE = 512 * 1024  # 512 KB por chunk
_chunks_entrantes = {}   # nombre -> {total, chunks: {idx: bytes}}


@sio.on('file_chunk_in')
def on_file_chunk_in(data):
    """Técnico envía archivo en chunks — ensamblar y guardar en Desktop."""
    nombre = os.path.basename(data.get('nombre', 'archivo_recibido'))
    idx    = data['idx']
    total  = data['total']

    if nombre not in _chunks_entrantes:
        _chunks_entrantes[nombre] = {'total': total, 'chunks': {}}

    _chunks_entrantes[nombre]['chunks'][idx] = base64.b64decode(data['b64'])
    recibidos = len(_chunks_entrantes[nombre]['chunks'])
    ventana.set_archivo(f"📥 {nombre} — {recibidos}/{total}")

    if recibidos == total:
        try:
            contenido = b''.join(_chunks_entrantes[nombre]['chunks'][i] for i in range(total))
            import subprocess as _sp
            _r = _sp.run(['powershell','-Command','[Environment]::GetFolderPath("Desktop")'],
                         capture_output=True, text=True)
            destino = _r.stdout.strip() if _r.stdout.strip() else os.path.join(os.path.expanduser('~'), 'Desktop')
            os.makedirs(destino, exist_ok=True)
            with open(os.path.join(destino, nombre), 'wb') as f:
                f.write(contenido)
            del _chunks_entrantes[nombre]
            ventana.set_archivo(f"📥 {nombre} guardado en {destino}")
        except Exception as e:
            ventana.set_archivo(f"✗ Error al guardar: {e}", color="#f87171")


@sio.on('file_request')
def on_file_request(data):
    """Técnico pide archivo o carpeta — comprimir si es carpeta, enviar en chunks."""
    ruta = data.get('ruta', '').strip()

    def _enviar():
        try:
            buf = io.BytesIO()
            if os.path.isdir(ruta):
                nombre = os.path.basename(ruta.rstrip('/\\')) + '.zip'
                ventana.set_archivo(f"📦 Comprimiendo {nombre}...")
                with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, files in os.walk(ruta):
                        for fname in files:
                            fp = os.path.join(root, fname)
                            zf.write(fp, os.path.relpath(fp, os.path.dirname(ruta)))
            elif os.path.isfile(ruta):
                nombre = os.path.basename(ruta)
                with open(ruta, 'rb') as f:
                    buf.write(f.read())
            else:
                sio.emit('file_chunk', {'session_id': SESSION, 'error': f'No encontrado: {ruta}', 'idx': 0, 'total': 0})
                return

            contenido = buf.getvalue()
            total = (len(contenido) + CHUNK_SIZE - 1) // CHUNK_SIZE
            for i in range(total):
                chunk = contenido[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]
                sio.emit('file_chunk', {
                    'session_id': SESSION,
                    'nombre': nombre,
                    'idx': i,
                    'total': total,
                    'b64': base64.b64encode(chunk).decode()
                })
                ventana.set_archivo(f"📤 {nombre} — {i + 1}/{total}")
            ventana.set_archivo(f"📤 {nombre} enviado ({len(contenido) // 1024} KB)")
        except Exception as e:
            sio.emit('file_chunk', {'session_id': SESSION, 'error': str(e), 'idx': 0, 'total': 0})
            ventana.set_archivo(f"✗ Error: {e}", color="#f87171")

    threading.Thread(target=_enviar, daemon=True).start()

@sio.on('exec')
def on_exec(data):
    """Técnico envía un comando — ejecutar y devolver output."""
    cmd = data.get('cmd', '').strip()
    if not cmd:
        return

    def _run():
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=60, encoding='utf-8', errors='replace'
            )
            output = result.stdout + result.stderr
            if not output:
                output = f'[Comando ejecutado — código de salida: {result.returncode}]'
        except subprocess.TimeoutExpired:
            output = '[Timeout: el comando tardó más de 60 segundos]'
        except Exception as e:
            output = f'[Error: {e}]'
        sio.emit('exec_result', {'session_id': SESSION, 'output': output})
        ventana.set_archivo(f"⌨️ cmd ejecutado: {cmd[:40]}")

    threading.Thread(target=_run, daemon=True).start()


@sio.event
def disconnect():
    if running:
        ventana.set_estado('gris', 'Reconectando...')


# ─── Calibración overlay ─────────────────────────────────────────────────────

def _crear_overlay_calibracion():
    global _calib_win
    if _calib_win:
        try: _calib_win.destroy()
        except Exception: pass
    _calib_win = tk.Toplevel(ventana.root)
    _calib_win.attributes('-fullscreen', True)
    _calib_win.attributes('-topmost', True)
    _calib_win.overrideredirect(True)
    _calib_win.configure(bg='#0f172a')
    canvas = tk.Canvas(_calib_win, bg='#0f172a', highlightthickness=0)
    canvas.pack(fill='both', expand=True)
    _calib_win.update()
    w = _calib_win.winfo_screenwidth()
    h = _calib_win.winfo_screenheight()
    canvas.create_text(w//2, 55, text='CALIBRACIÓN DE PUNTERO',
                       fill='white', font=('Arial', 20, 'bold'))
    canvas.create_text(w//2, 92,
                       text='El técnico está calibrando el cursor — por favor espere',
                       fill='#94a3b8', font=('Arial', 13))
    targets = [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]
    colors  = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444']
    r = 28
    for i, (rx, ry) in enumerate(targets):
        x, y = int(rx * w), int(ry * h)
        col = colors[i]
        canvas.create_oval(x-r, y-r, x+r, y+r, outline=col, width=3, fill='#0f172a')
        canvas.create_line(x-r-20, y, x-5, y, fill=col, width=2)
        canvas.create_line(x+5, y, x+r+20, y, fill=col, width=2)
        canvas.create_line(x, y-r-20, x, y-5, fill=col, width=2)
        canvas.create_line(x, y+5, x, y+r+20, fill=col, width=2)
        canvas.create_text(x, y, text=str(i+1), fill=col, font=('Arial', 16, 'bold'))


def _ocultar_overlay_calibracion():
    global _calib_win
    if _calib_win:
        try: _calib_win.destroy()
        except Exception: pass
        _calib_win = None


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
