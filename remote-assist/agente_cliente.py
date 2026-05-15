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
EXE_VERSION      = "2.3"
RELAY_URL_GITHUB = "https://raw.githubusercontent.com/Rafaelolivares07/TUC-TUC/main/remote_url.txt"
VER_URL_GITHUB   = "https://raw.githubusercontent.com/Rafaelolivares07/TUC-TUC/main/version.txt"
EXE_DOWNLOAD_URL = "https://github.com/Rafaelolivares07/TUC-TUC/releases/latest/download/AsistenciaTucTuc.exe"
_SERVER_FALLBACK = "https://remote.tuc-tuc.co"


def _fetch_text(url, timeout=8):
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode().strip()
    except Exception:
        return None


def _auto_update():
    """Si hay versión nueva en GitHub, muestra progreso y relanza el EXE."""
    if not getattr(sys, 'frozen', False):
        return
    ver_remota = _fetch_text(VER_URL_GITHUB)
    if not ver_remota:
        return
    try:
        if float(ver_remota) <= float(EXE_VERSION):
            return
    except ValueError:
        return

    # Ventana de progreso
    import urllib.request, tempfile, shutil
    root_upd = tk.Tk()
    root_upd.title("TUC TUC — Actualizando")
    root_upd.geometry("340x130")
    root_upd.resizable(False, False)
    root_upd.overrideredirect(True)
    root_upd.configure(bg="#1e293b")
    root_upd.update_idletasks()
    x = (root_upd.winfo_screenwidth() - 340) // 2
    y = (root_upd.winfo_screenheight() - 130) // 2
    root_upd.geometry(f"340x130+{x}+{y}")

    tk.Label(root_upd, text="TUC TUC", font=("Arial", 13, "bold"),
             fg="#2563eb", bg="#1e293b").pack(pady=(16, 2))
    lbl_ver = tk.Label(root_upd, text=f"Actualizando a V{ver_remota}...",
                       font=("Arial", 9), fg="#94a3b8", bg="#1e293b")
    lbl_ver.pack()
    bar = ttk.Progressbar(root_upd, length=280, mode='determinate')
    bar.pack(pady=10)
    lbl_pct = tk.Label(root_upd, text="0%", font=("Arial", 9),
                       fg="#64748b", bg="#1e293b")
    lbl_pct.pack()
    root_upd.update()

    import tempfile as _tmp, subprocess as _sp, shutil as _sh, socket as _sock
    exe_actual = sys.executable
    tmp_exe = os.path.join(_tmp.gettempdir(), 'AsistenciaTucTuc_update.exe')

    try:
        _sock.setdefaulttimeout(30)
        with urllib.request.urlopen(EXE_DOWNLOAD_URL) as resp:
            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            with open(tmp_exe, 'wb') as fout:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    fout.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = min(int(downloaded * 100 / total), 100)
                        bar['value'] = pct
                        lbl_pct.config(text=f"{pct}%")
                        root_upd.update()
        root_upd.destroy()
        # PyInstaller --onefile no bloquea el EXE original — se puede sobreescribir en caliente
        _sh.copy2(tmp_exe, exe_actual)
        os.remove(tmp_exe)
        time.sleep(0.3)
        _sp.Popen([exe_actual])
        time.sleep(0.5)
        sys.exit(0)
    except Exception:
        try:
            os.remove(tmp_exe)
        except Exception:
            pass
        try:
            root_upd.destroy()
        except Exception:
            pass


def _fetch_server_url():
    url = _fetch_text(RELAY_URL_GITHUB)
    if url and url.startswith("http"):
        return url
    return _SERVER_FALLBACK


_auto_update()
SERVER   = _fetch_server_url()
TOKEN    = "tuctuc-remote-2026"
SESSION  = __import__('random').randint(100000, 999999).__str__()
FPS      = 8
QUALITY  = 85
SCALE    = 1.0
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
                'Space': 'space', 'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4',
                'F5': 'f5', 'F6': 'f6', 'F7': 'f7', 'F8': 'f8', 'F9': 'f9',
                'F10': 'f10', 'F11': 'f11', 'F12': 'f12',
            }
            if '+' in key:
                # Combo: win+r, alt+F4, ctrl+c, etc.
                parts = [p.strip().lower() for p in key.split('+')]
                mod_map = {'win': 'winleft', 'ctrl': 'ctrl', 'alt': 'alt', 'shift': 'shift'}
                mapped_parts = []
                for p in parts:
                    mapped_parts.append(mod_map.get(p, key_map.get(p, p if len(p) == 1 else p.lower())))
                pyautogui.hotkey(*mapped_parts)
            else:
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
        self.root.geometry("340x220")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar)

        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 340) // 2
        y = (self.root.winfo_screenheight() - 220) // 2
        self.root.geometry(f"340x220+{x}+{y}")

        self._tecnico_conectado = False
        self._tiempo_inicio     = None
        self._pulso_on          = True

        tk.Label(self.root, text="TUC TUC", font=("Arial", 18, "bold"),
                 fg="#2563eb").pack(pady=(16, 2))
        tk.Label(self.root, text=f"Asistencia Técnica Remota  V{EXE_VERSION}",
                 font=("Arial", 10), fg="#555").pack()

        codigo = SESSION[:3] + "-" + SESSION[3:]
        tk.Label(self.root, text="Tu código de sesión:",
                 font=("Arial", 9), fg="#888").pack(pady=(8, 0))
        tk.Label(self.root, text=codigo,
                 font=("Courier New", 26, "bold"), fg="#16a34a").pack()

        # Estado + contador
        self.frame_estado = tk.Frame(self.root)
        self.frame_estado.pack(pady=(8, 0))
        self.dot = tk.Label(self.frame_estado, text="●", font=("Arial", 14), fg="#999")
        self.dot.pack(side="left", padx=(0, 6))
        self.lbl_estado = tk.Label(self.frame_estado, text="Conectando...",
                                   font=("Arial", 11))
        self.lbl_estado.pack(side="left")
        self.lbl_timer = tk.Label(self.frame_estado, text="",
                                  font=("Arial", 9), fg="#64748b")
        self.lbl_timer.pack(side="left", padx=(6, 0))

        # Aviso "no cierre"
        self.lbl_aviso = tk.Label(self.root,
                                  text="No cierre esta ventana mientras el tecnico trabaja.",
                                  font=("Arial", 8), fg="#dc2626")
        # no se empaqueta aún — aparece solo con técnico conectado

        self.btn = tk.Button(self.root, text="Cerrar sesión", command=self.cerrar,
                             bg="#ef4444", fg="white", font=("Arial", 10),
                             relief="flat", padx=16, pady=6, cursor="hand2")
        self.btn.pack(pady=6)

        self.lbl_archivo = tk.Label(self.root, text="", font=("Arial", 8), fg="#22c55e")
        self.lbl_archivo.pack(pady=(0, 2))

        self._tick()

    def _tick(self):
        if self._tecnico_conectado:
            # Pulso: alternar entre verde claro y verde oscuro
            self.dot.config(fg="#22c55e" if self._pulso_on else "#86efac")
            self._pulso_on = not self._pulso_on
            # Contador
            if self._tiempo_inicio:
                secs = int(time.time() - self._tiempo_inicio)
                m, s = divmod(secs, 60)
                self.lbl_timer.config(text=f"· {m}m {s:02d}s")
        self.root.after(600, self._tick)

    def set_estado(self, color, texto):
        self.root.after(0, lambda: self._actualizar(color, texto))

    def set_archivo(self, texto, color="#22c55e"):
        self.root.after(0, lambda: self.lbl_archivo.config(text=texto, fg=color))

    def _actualizar(self, color, texto):
        colores = {'verde': '#22c55e', 'amarillo': '#eab308', 'rojo': '#ef4444', 'gris': '#999'}
        self.dot.config(fg=colores.get(color, '#999'))
        self.lbl_estado.config(text=texto)
        if color == 'verde':
            self._tecnico_conectado = True
            self._tiempo_inicio = time.time()
            self.lbl_aviso.pack(before=self.btn)
        else:
            self._tecnico_conectado = False
            self._tiempo_inicio = None
            self.lbl_timer.config(text="")
            self.lbl_aviso.pack_forget()

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
    ventana.set_estado('amarillo', 'Esperando al tecnico...')

@sio.on('viewer_joined')
def on_viewer_joined():
    ventana.set_estado('verde', 'Tecnico conectado')

@sio.on('viewer_left')
def on_viewer_left():
    ventana.set_estado('amarillo', 'Esperando al tecnico...')

@sio.on('agent_error')
def on_error(data):
    ventana.set_estado('rojo', f"Error: {data.get('msg', 'desconocido')}")

@sio.on('set_quality')
def on_set_quality(data):
    global QUALITY, SCALE
    QUALITY = int(data.get('quality', QUALITY))
    SCALE   = float(data.get('scale', SCALE))
    try:
        img_b64 = capturar_frame()
        sio.emit('frame', {'session_id': SESSION, 'img': img_b64})
    except Exception:
        pass

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
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders') as _k:
                    desktop = winreg.QueryValueEx(_k, 'Desktop')[0]
            except Exception:
                desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
            os.makedirs(desktop, exist_ok=True)
            with open(os.path.join(desktop, nombre), 'wb') as f:
                f.write(contenido)
            del _chunks_entrantes[nombre]
            ventana.set_archivo(f"📥 {nombre} guardado en Desktop")
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
    try:
        ventana = VentanaAsistencia()

        t1 = threading.Thread(target=hilo_conexion, daemon=True)
        t2 = threading.Thread(target=loop_frames, daemon=True)
        t1.start()
        t2.start()

        ventana.run()
    except Exception:
        import traceback as _tb, tkinter.messagebox as _mb
        _mb.showerror("TUC TUC — Error de inicio", _tb.format_exc())


if __name__ == '__main__':
    main()
