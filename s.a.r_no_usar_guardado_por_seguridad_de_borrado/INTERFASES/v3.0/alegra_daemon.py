"""
alegra_daemon.py  v3.0
Servicio en segundo plano — corre allegra_sync + interfaz_allegra cada N minutos.
v3.0: EXE autónomo sin Python en el cliente. Usa --run para sub-ejecuciones internas.

Modos de ejecución:
  AlegraDaemon.exe                     -> inicia daemon en background
  AlegraDaemon.exe --run allegra_sync  -> corre allegra_sync.main() y sale
  AlegraDaemon.exe --run interfaz_allegra -> corre interfaz_allegra.main() y sale
  AlegraDaemon.exe --run ciclo         -> corre correr_sync() y sale (para ConfigurarAlegra)
"""

import time
import subprocess
import sys
import os
import shutil
import json
import dbf
from datetime import datetime

DAEMON_VERSION = "3.0"

_FROZEN = getattr(sys, 'frozen', False)

def _python_exe():
    for nombre in ('pythonw', 'pythonw3', 'python', 'python3', 'py'):
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    return 'pythonw'

PYTHON_EXE    = None if _FROZEN else _python_exe()
RUTA_DBF      = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"
LOG_FILE      = r"C:\S.A.R\alegra_daemon.log"
PID_FILE      = r"C:\S.A.R\alegra_daemon.pid"
BD_ESPERADA_TXT = r"C:\S.A.R\bd_esperada.txt"
PAUSA_FILE      = r"C:\S.A.R\alegra_daemon_pausa.txt"
SYNC_PY         = r"C:\S.A.R\allegra_sync.py"
INTERFAZ_PY     = r"C:\S.A.R\interfaz_allegra.py"
ESPERA_MIN    = 5

SAR_DIR = r"C:\S.A.R"
if not _FROZEN and SAR_DIR not in sys.path:
    sys.path.insert(0, SAR_DIR)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ts}] {msg}"
    print(linea, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        pass


def _escribir_pid():
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n{DAEMON_VERSION}")
    except Exception:
        pass


def _eliminar_pid():
    try:
        if os.path.exists(PID_FILE):
            os.unlink(PID_FILE)
    except Exception:
        pass


def get_bd_path():
    try:
        t = dbf.Table(RUTA_DBF)
        t.open(dbf.READ_ONLY)
        ruta_dbc = t[0].ruta.strip()
        t.close()
        sep = ruta_dbc.rfind('\\')
        return ruta_dbc[:sep+1] if sep >= 0 else ruta_dbc + '\\'
    except Exception as e:
        log(f"ERROR leyendo ruta.dbf: {e}")
        return None


def leer_intervalo():
    carpeta = get_bd_path()
    if not carpeta:
        return ESPERA_MIN
    cfg_path = carpeta + "allegra_config.dbf"
    if not os.path.exists(cfg_path):
        return ESPERA_MIN
    try:
        t = dbf.Table(cfg_path, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        intervalo = 0
        for r in t:
            intervalo = int(r.intervalo or 0)
            break
        t.close()
        return intervalo  # 0 = no correr automáticamente
    except Exception as e:
        log(f"ERROR leyendo intervalo: {e}")
        return ESPERA_MIN


def _leer_config_empresas() -> dict:
    """Retorna dict con config por empresa para incluir en el log."""
    carpeta = get_bd_path()
    if not carpeta:
        return {}
    cfg_path = carpeta + "allegra_config.dbf"
    if not os.path.exists(cfg_path):
        return {}
    try:
        t = dbf.Table(cfg_path, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        datos = {}
        for r in t:
            emp = str(r.empresa).strip()
            datos[emp] = {
                'num_inicio': str(r.num_inicio).strip(),
                'max_fact':   int(r.max_fact or 0),
                'intervalo':  int(r.intervalo or 0),
                'total_proc': int(r.total_proc or 0),
            }
        t.close()
        return datos
    except Exception:
        return {}


def _guardar_ultimo_log(texto: str):
    """Guarda el log del ciclo en allegra_config.dbf (campo ultimo_log)."""
    carpeta = get_bd_path()
    if not carpeta:
        return
    cfg_path = carpeta + "allegra_config.dbf"
    if not os.path.exists(cfg_path):
        return
    # DBF VFP usa cp1252 — reemplazar chars fuera de rango
    texto_safe = texto.encode('cp1252', errors='replace').decode('cp1252')
    try:
        t = dbf.Table(cfg_path, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        for r in t:
            with r:
                r.ultimo_log = texto_safe[:8000]
        t.close()
    except Exception as e:
        log(f"ERROR guardando ultimo_log: {e}")
    _actualizar_estado_json()


def _actualizar_estado_json():
    """Actualiza C:\\S.A.R\\estado_proceso.json con estado runtime del daemon."""
    json_path = r"C:\S.A.R\estado_proceso.json"
    try:
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

        # Estado daemon
        pid = None
        try:
            pid = int(open(PID_FILE, encoding="utf-8").readline().strip())
        except Exception:
            pass

        pausado = os.path.exists(PAUSA_FILE)
        corriendo = False
        if pid:
            try:
                import ctypes
                h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                if h:
                    code = ctypes.c_ulong(0)
                    ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
                    ctypes.windll.kernel32.CloseHandle(h)
                    corriendo = (code.value == 259)
            except Exception:
                pass

        data["daemon"] = {
            "estado": "pausado" if pausado else ("corriendo" if corriendo else "detenido"),
            "pid": pid,
            "archivo_pausa": PAUSA_FILE,
            "fallback_intervalo_min": ESPERA_MIN
        }

        # Config por empresa
        carpeta = get_bd_path()
        if carpeta:
            cfg_path = carpeta + "allegra_config.dbf"
            if os.path.exists(cfg_path):
                try:
                    t = dbf.Table(cfg_path, codepage="cp1252")
                    t.open(dbf.READ_ONLY)
                    empresas = []
                    for r in t:
                        if dbf.is_deleted(r):
                            continue
                        empresas.append({
                            "empresa":       str(r.empresa).strip(),
                            "max_fact":      int(r.max_fact or 0),
                            "intervalo_min": int(r.intervalo or 0),
                            "num_inicio":    str(r.num_inicio).strip(),
                            "total_proc":    int(r.total_proc or 0),
                            "ultima_sync":   str(r.ultima_sin).strip() if hasattr(r, 'ultima_sin') else "",
                        })
                    t.close()
                    data["allegra_config"] = empresas
                except Exception:
                    pass

        # Fases activas — leer desde interfaz_allegra (bundleado en EXE o .py en disco)
        try:
            if _FROZEN:
                import interfaz_allegra
                data["fases_activas"] = interfaz_allegra.FASES_ACTIVAS
            else:
                import importlib.util
                spec = importlib.util.spec_from_file_location("interfaz_allegra", r"C:\S.A.R\interfaz_allegra.py")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                data["fases_activas"] = mod.FASES_ACTIVAS
        except Exception:
            pass  # si falla, no tocar el valor existente

        data["_actualizado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _verificar_bd() -> bool:
    """
    Compara la BD activa (ruta.dbf) contra la BD esperada (bd_esperada.txt).
    Si no coinciden o bd_esperada.txt no existe, aborta y escribe en ultimo_log.
    """
    try:
        t = dbf.Table(RUTA_DBF)
        t.open(dbf.READ_ONLY)
        bd_actual = t[0].ruta.strip()
        t.close()
    except Exception as e:
        log(f"ERROR leyendo ruta.dbf: {e}")
        return False

    if not os.path.exists(BD_ESPERADA_TXT):
        msg = "ABORTADO: bd_esperada.txt no definido. Abra configurar_allegra.py y defina la BD esperada."
        log(msg)
        _guardar_ultimo_log(msg)
        return False

    bd_esperada = open(BD_ESPERADA_TXT, encoding="utf-8").read().strip()

    if bd_actual.lower() != bd_esperada.lower():
        msg = (
            f"ABORTADO: BD activa no coincide con la esperada para Interfaz Alegra.\n"
            f"  Activa:   {bd_actual}\n"
            f"  Esperada: {bd_esperada}\n"
            f"Verifique que Administrator este apuntando a la BD correcta."
        )
        log(msg)
        _guardar_ultimo_log(msg)
        return False

    return True


def correr_sync():
    if os.path.exists(PAUSA_FILE):
        msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] DAEMON PAUSADO — ciclo omitido.\nElimina alegra_daemon_pausa.txt o usa el formulario para reanudar."
        log("PAUSADO — ciclo omitido")
        _guardar_ultimo_log(msg)
        return

    ahora   = datetime.now()
    ts      = ahora.strftime("%Y-%m-%d %H:%M:%S")
    intervalo = leer_intervalo()
    proximo = ahora.replace(microsecond=0)
    from datetime import timedelta
    proximo_ts = (ahora + timedelta(seconds=intervalo)).strftime("%H:%M:%S")

    # Leer BD activa y esperada para el header
    try:
        t = dbf.Table(RUTA_DBF)
        t.open(dbf.READ_ONLY)
        bd_activa = t[0].ruta.strip()
        t.close()
    except Exception:
        bd_activa = "(no se pudo leer)"

    bd_esperada_txt = "(sin definir)"
    if os.path.exists(BD_ESPERADA_TXT):
        try:
            bd_esperada_txt = open(BD_ESPERADA_TXT, encoding="utf-8").read().strip()
        except Exception:
            pass

    bd_ok = bd_activa.lower() == bd_esperada_txt.lower()
    estado_bd = "OK" if bd_ok else "NO COINCIDE"

    cfg = _leer_config_empresas()
    lineas = [
        f"=== CICLO {ts} (daemon v{DAEMON_VERSION}) ===",
        f"BD activa:   {bd_activa}",
        f"BD esperada: {bd_esperada_txt}",
        f"Estado BD:   {estado_bd}",
        f"Intervalo:   {intervalo} seg  |  Proximo aprox: {proximo_ts}",
    ]
    for emp, d in sorted(cfg.items()):
        lineas.append(
            f"Config {emp}:   num_inicio={d['num_inicio'] or '(vacio)'}  "
            f"max_fact={d['max_fact']}  total_proc={d['total_proc']}"
        )
    lineas.append("")

    log(f"Iniciando ciclo (intervalo={intervalo} seg)...")

    if not _verificar_bd():
        lineas.append("ABORTADO: BD no verificada (ver detalle arriba)")
        _guardar_ultimo_log("\n".join(lineas))
        return

    # Timeout: intervalo_configurado × 60s (el ciclo nunca debería durar más que su propio intervalo).
    # Mínimo 1800s (30 min) para absorber ciclos lentos sin importar la configuración.
    intervalo_cfg = leer_intervalo()
    timeout_ciclo = max(1800, intervalo_cfg)
    log(f"Timeout ciclo: {timeout_ciclo}s (intervalo={intervalo_cfg} seg)")

    PROCESADOR_EXE = r"C:\S.A.R\PROCESADOR_STAGING.EXE"

    for nombre, script in [("allegra_sync", SYNC_PY), ("interfaz_allegra", INTERFAZ_PY)]:
        if _FROZEN:
            cmd = [sys.executable, '--run', nombre]
        else:
            if not os.path.exists(script):
                lineas.append(f"=== {nombre} ===\nNO ENCONTRADO: {script}")
                continue
            cmd = [PYTHON_EXE, script]
        try:
            r = subprocess.run(
                cmd,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout_ciclo,
            )
            salida = (r.stdout + r.stderr).strip()
            lineas.append(f"=== {nombre} ===\n{salida}")
            if r.returncode != 0:
                log(f"{nombre} ERROR (returncode={r.returncode})")
            else:
                log(f"{nombre} OK")
        except subprocess.TimeoutExpired:
            lineas.append(f"=== {nombre} ===\nTIMEOUT (>5 min)")
            log(f"{nombre}: TIMEOUT")
        except Exception as e:
            lineas.append(f"=== {nombre} ===\nEXCEPCION: {e}")
            log(f"{nombre}: EXCEPCION — {e}")

    # Llamar al PROCESADOR_STAGING.EXE si existe (fallback: interfaz_allegra ya lo llama internamente)
    if os.path.exists(PROCESADOR_EXE):
        try:
            r_proc = subprocess.run([PROCESADOR_EXE], timeout=300, capture_output=True)
            if r_proc.returncode == 0:
                lineas.append("=== procesador_staging ===\nOK")
                log("procesador_staging OK")
            else:
                lineas.append(f"=== procesador_staging ===\nERROR returncode={r_proc.returncode}")
                log(f"procesador_staging ERROR ({r_proc.returncode})")
        except Exception as e_proc:
            lineas.append(f"=== procesador_staging ===\nEXCEPCION: {e_proc}")
            log(f"procesador_staging: EXCEPCION — {e_proc}")

    lineas.append(f"\n=== FIN CICLO {datetime.now().strftime('%H:%M:%S')} ===")
    salida_total = "\n".join(lineas)
    log("Ciclo completado.")
    _guardar_ultimo_log(salida_total)


def main():
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--run', default=None,
                        choices=['allegra_sync', 'interfaz_allegra', 'ciclo'])
    args, _ = parser.parse_known_args()

    if args.run == 'allegra_sync':
        import allegra_sync
        allegra_sync.main()
        return
    elif args.run == 'interfaz_allegra':
        import interfaz_allegra
        interfaz_allegra.main()
        return
    elif args.run == 'ciclo':
        correr_sync()
        return

    import ctypes
    import atexit

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateMutexW(None, True, "Global\\AlegraDaemonMutex30")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return

    _escribir_pid()
    atexit.register(_eliminar_pid)

    log(f"=== AlegraDaemon v{DAEMON_VERSION} iniciado (PID {os.getpid()}) ===")
    while True:
        intervalo = leer_intervalo()
        if intervalo > 0:
            correr_sync()
            log(f"Proximo sync en {intervalo} segundo(s)...")
            time.sleep(intervalo)
        else:
            log("Intervalo=0 — modo manual, esperando...")
            time.sleep(ESPERA_MIN * 60)


if __name__ == "__main__":
    main()
