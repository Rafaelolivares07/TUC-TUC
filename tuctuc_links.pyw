import tkinter as tk
import json, urllib.request, threading, subprocess, sys, os, time, re

TUCTUC_DIR        = r"C:\Users\RAFAEL OLIVARES\Documents\TucTucV2"
TUNNEL_EXE        = r"C:\cloudflared\cloudflared.exe"
FLASK_PORT        = 5000
GITHUB_PILAR      = "https://github.com/Rafaelolivares07/TUC-TUC/releases/latest/download/PilarSetup.exe"
GITHUB_ASISTENCIA = "https://github.com/Rafaelolivares07/TUC-TUC/releases/latest/download/AsistenciaTucTuc.exe"

RUTAS_PILAR = [
    ("Admin consultas DBF", "/admin/consultas"),
]
RUTAS_REST = [
    ("Rancho Dapa — cliente",  "/r/rancho-dapa"),
    ("Jacobs Food — cliente",  "/r/jacobs-food"),
    ("Admin restaurantes",     "/admin/restaurante"),
    ("Login admin",            "/admin/login"),
]

BG     = "#1e1e2e"
BG2    = "#2a2a3e"
VERDE  = "#50fa7b"
ROJO   = "#ff5555"
AMAR   = "#f1fa8c"
GRIS   = "#6272a4"
TEXTO  = "#f8f8f2"
ACENTO = "#bd93f9"
BTN_BG = "#44475a"
BTN_ACT= "#6272a4"


_URL_RE = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')


def flask_ya_corre():
    try:
        urllib.request.urlopen(f"http://localhost:{FLASK_PORT}/api/version", timeout=2)
        return True
    except Exception:
        return False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TUC TUC")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._tunnel_url = None
        self._proc_flask = None
        self._proc_tunnel = None
        self._rows_din  = []
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        threading.Thread(target=self._arrancar_sistema, daemon=True).start()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build(self):
        # Header estado
        hdr = tk.Frame(self, bg=BG2, pady=12)
        hdr.pack(fill="x")

        self._dot = tk.Label(hdr, text="●", bg=BG2, fg=AMAR, font=("Segoe UI", 14))
        self._dot.pack(side="left", padx=(18, 4))
        self._estado_lbl = tk.Label(hdr, text="Arrancando sistema...",
                                    bg=BG2, fg=AMAR, font=("Segoe UI", 10, "bold"))
        self._estado_lbl.pack(side="left")

        self._btn_stop = tk.Button(hdr, text="⏹ Detener", bg="#ff5555", fg=TEXTO,
                                   relief="flat", cursor="hand2", font=("Segoe UI", 9),
                                   activebackground="#ff7777", activeforeground=TEXTO,
                                   state="disabled", command=self._detener)
        self._btn_stop.pack(side="right", padx=18)

        self._url_lbl = tk.Label(self, text="", bg=BG, fg=GRIS, font=("Segoe UI", 8))
        self._url_lbl.pack(anchor="w", padx=18, pady=(4, 0))

        # Sección Pilar
        self._seccion("Para Pilar")
        self._fila_fija("Instalador (PilarSetup.exe)",  GITHUB_PILAR)
        self._fila_fija("Asistencia Remota (EXE)",      GITHUB_ASISTENCIA)
        for et, ruta in RUTAS_PILAR:
            self._fila_din(et, ruta)

        # Sección Restaurantes
        self._seccion("Restaurantes")
        for et, ruta in RUTAS_REST:
            self._fila_din(et, ruta)

        # Sección Tracking
        self._seccion("Tracking GPS")
        f_inp = tk.Frame(self, bg=BG)
        f_inp.pack(fill="x", padx=18, pady=(4, 6))
        tk.Label(f_inp, text="Nombre corredor:", bg=BG, fg=TEXTO,
                 font=("Segoe UI", 9)).pack(side="left")
        self._entry_nombre = tk.Entry(f_inp, bg=BG2, fg=VERDE, insertbackground=VERDE,
                                      font=("Segoe UI", 10), relief="flat", width=14)
        self._entry_nombre.insert(0, "david")
        self._entry_nombre.pack(side="left", padx=(8, 6))
        tk.Button(f_inp, text="Generar", bg=BTN_BG, fg=TEXTO, relief="flat",
                  cursor="hand2", font=("Segoe UI", 8),
                  activebackground=BTN_ACT, activeforeground=TEXTO,
                  command=self._actualizar_tracking).pack(side="left")

        self._lbl_track_corredor = tk.Label(self, text="—", bg=BG, fg=GRIS,
                                            font=("Segoe UI", 8), anchor="w")
        self._lbl_track_corredor.pack(fill="x", padx=18)
        self._btn_track_corredor = tk.Button(self, text="Copiar link corredor",
                                             bg=BTN_BG, fg=GRIS, relief="flat",
                                             cursor="hand2", font=("Segoe UI", 8),
                                             activebackground=BTN_ACT,
                                             activeforeground=TEXTO, state="disabled")
        self._btn_track_corredor.pack(anchor="e", padx=18, pady=(0, 4))

        self._lbl_track_mapa = tk.Label(self, text="—", bg=BG, fg=GRIS,
                                        font=("Segoe UI", 8), anchor="w")
        self._lbl_track_mapa.pack(fill="x", padx=18)
        self._btn_track_mapa = tk.Button(self, text="Copiar link mapa",
                                         bg=BTN_BG, fg=GRIS, relief="flat",
                                         cursor="hand2", font=("Segoe UI", 8),
                                         activebackground=BTN_ACT,
                                         activeforeground=TEXTO, state="disabled")
        self._btn_track_mapa.pack(anchor="e", padx=18, pady=(0, 4))

        tk.Label(self, text="Copiar → portapapeles listo para WhatsApp",
                 bg=BG, fg=GRIS, font=("Segoe UI", 8)).pack(pady=(6, 12))

    def _seccion(self, titulo):
        f = tk.Frame(self, bg=BG)
        f.pack(fill="x", padx=18, pady=(14, 2))
        tk.Label(f, text=titulo, bg=BG, fg=ACENTO,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Frame(f, bg=GRIS, height=1).pack(side="left", fill="x", expand=True,
                                             padx=(8, 0), pady=6)

    def _fila_fija(self, etiqueta, url):
        f = tk.Frame(self, bg=BG)
        f.pack(fill="x", padx=18, pady=2)
        tk.Label(f, text=etiqueta, bg=BG, fg=TEXTO, font=("Segoe UI", 9),
                 width=28, anchor="w").pack(side="left")
        tk.Label(f, text=self._cortar(url), bg=BG, fg=VERDE,
                 font=("Segoe UI", 8), anchor="w").pack(side="left", expand=True, fill="x")
        tk.Button(f, text="Copiar", bg=BTN_BG, fg=TEXTO, relief="flat", cursor="hand2",
                  font=("Segoe UI", 8), activebackground=BTN_ACT, activeforeground=TEXTO,
                  command=lambda u=url: self._copiar(u)).pack(side="right", padx=(6, 0))

    def _fila_din(self, etiqueta, ruta):
        f = tk.Frame(self, bg=BG)
        f.pack(fill="x", padx=18, pady=2)
        tk.Label(f, text=etiqueta, bg=BG, fg=TEXTO, font=("Segoe UI", 9),
                 width=28, anchor="w").pack(side="left")
        lbl = tk.Label(f, text="—", bg=BG, fg=GRIS, font=("Segoe UI", 8), anchor="w")
        lbl.pack(side="left", expand=True, fill="x")
        btn = tk.Button(f, text="Copiar", bg=BTN_BG, fg=GRIS, relief="flat",
                        cursor="hand2", font=("Segoe UI", 8),
                        activebackground=BTN_ACT, activeforeground=TEXTO, state="disabled")
        btn.pack(side="right", padx=(6, 0))
        self._rows_din.append((ruta, lbl, btn))

    # ── Lógica arranque ───────────────────────────────────────────────────

    def _arrancar_sistema(self):
        # 1. Flask
        if flask_ya_corre():
            self.after(0, lambda: self._set_estado("Flask ya estaba corriendo", AMAR))
        else:
            self.after(0, lambda: self._set_estado("Arrancando Flask...", AMAR))
            self._proc_flask = subprocess.Popen(
                [sys.executable, "main.py"],
                cwd=TUCTUC_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for _ in range(20):
                time.sleep(1)
                if flask_ya_corre():
                    break
            else:
                self.after(0, lambda: self._set_estado("Flask no respondió — revisar main.py", ROJO))
                return

        # 2. Tunnel (cloudflared — URL viene por stderr)
        self.after(0, lambda: self._set_estado("Arrancando tunnel...", AMAR))
        self._proc_tunnel = subprocess.Popen(
            [TUNNEL_EXE, "tunnel", "--url", f"http://localhost:{FLASK_PORT}"],
            stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        url = None
        deadline = time.time() + 30
        while time.time() < deadline:
            line = self._proc_tunnel.stderr.readline().decode("utf-8", errors="replace")
            m = _URL_RE.search(line)
            if m:
                url = m.group(0).rstrip("/")
                break
        if not url:
            self.after(0, lambda: self._set_estado("Tunnel no respondio", ROJO))
            return
        threading.Thread(target=lambda: [self._proc_tunnel.stderr.readline() for _ in iter(int, 1)],
                         daemon=True).start()

        # 3. Activar UI
        self.after(0, lambda: self._on_listo(url))

    def _on_listo(self, url):
        self._tunnel_url = url
        self._set_estado("Sistema activo ●", VERDE)
        self._url_lbl.config(text=url or "", fg=VERDE)
        self._btn_stop.config(state="normal")
        for ruta, lbl, btn in self._rows_din:
            full = (url or "") + ruta
            lbl.config(text=self._cortar(full), fg=VERDE)
            btn.config(state="normal", fg=TEXTO,
                       command=lambda u=full: self._copiar(u))
        self._actualizar_tracking()
        threading.Thread(target=self._publicar_url, args=(url,), daemon=True).start()

    def _actualizar_tracking(self):
        base = self._tunnel_url or ""
        nombre = self._entry_nombre.get().strip() or "corredor"
        u_send = f"{base}/t/{nombre}"
        u_mapa = f"{base}/t/{nombre}/seguir"
        col = VERDE if base else GRIS
        st  = "normal" if base else "disabled"
        self._lbl_track_corredor.config(text=u_send, fg=col)
        self._btn_track_corredor.config(state=st, fg=TEXTO if base else GRIS,
                                        command=lambda: self._copiar(u_send))
        self._lbl_track_mapa.config(text=u_mapa, fg=col)
        self._btn_track_mapa.config(state=st, fg=TEXTO if base else GRIS,
                                    command=lambda: self._copiar(u_mapa))

    def _publicar_url(self, url):
        try:
            relay_file = os.path.join(TUCTUC_DIR, "..", "MiAppMedicamentos", "relay_url.txt")
            relay_file = os.path.normpath(relay_file)
            # Escribir en MiAppMedicamentos (branch main)
            repo_dir = os.path.normpath(os.path.join(TUCTUC_DIR, "..","MiAppMedicamentos"))
            dest = os.path.join(repo_dir, "relay_url.txt")
            with open(dest, "w", encoding="utf-8") as f:
                f.write(url)
            subprocess.run(["git", "add", "relay_url.txt"], cwd=repo_dir,
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            subprocess.run(["git", "commit", "-m", f"relay: actualizar URL"],
                           cwd=repo_dir, capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            subprocess.run(["git", "push"], cwd=repo_dir, capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass

    def _set_estado(self, texto, color):
        self._dot.config(fg=color)
        self._estado_lbl.config(text=texto, fg=color)

    # ── Acciones ──────────────────────────────────────────────────────────

    def _detener(self):
        if self._proc_tunnel:
            self._proc_tunnel.terminate()
        if self._proc_flask:
            self._proc_flask.terminate()
        self._tunnel_url = None
        self._set_estado("Sistema detenido", GRIS)
        self._url_lbl.config(text="")
        self._btn_stop.config(state="disabled")
        for _, lbl, btn in self._rows_din:
            lbl.config(text="—", fg=GRIS)
            btn.config(state="disabled", fg=GRIS, command=None)
        self._lbl_track_corredor.config(text="—", fg=GRIS)
        self._btn_track_corredor.config(state="disabled", fg=GRIS)
        self._lbl_track_mapa.config(text="—", fg=GRIS)
        self._btn_track_mapa.config(state="disabled", fg=GRIS)

    def _cerrar(self):
        self._detener()
        self.after(300, self.destroy)

    def _copiar(self, texto):
        self.clipboard_clear()
        self.clipboard_append(texto)

    @staticmethod
    def _cortar(url, max=52):
        return url if len(url) <= max else url[:max] + "…"


if __name__ == "__main__":
    App().mainloop()
