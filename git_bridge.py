"""
git_bridge.py — Puente autónomo entre tareas_git (PostgreSQL) y git local

Flujo:
  1. Detecta tareas con estado='pendiente' en la tabla tareas_git
  2. Marca como 'procesando'
  3. Ejecuta el comando git localmente (status o commit-push)
  4. Guarda el resultado en JSON y marca como 'listo' o 'error'
  5. Render hace polling a /api/admin/git/tarea/<id> y muestra el resultado

Uso:
  py git_bridge.py
"""

import os
import sys
import json
import time
import socket
import subprocess
import re
import psycopg2
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Forzar UTF-8 en stdout para evitar UnicodeEncodeError en Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
DB_URL    = os.getenv('DATABASE_URL')
APP_DIR   = Path(r"C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos")
LOCK_PORT = 47833   # distinto al de chat_bridge.py (47832)
POLL_INTERVAL = 2   # segundos entre checks
# ────────────────────────────────────────────────────────────────────────────

_lock_socket = None


def adquirir_lock():
    global _lock_socket
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', LOCK_PORT))
        _lock_socket.listen(1)
        return True
    except OSError:
        if _lock_socket:
            _lock_socket.close()
        return False


def get_conn():
    return psycopg2.connect(
        DB_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10,
    )


def ts():
    return datetime.now().strftime('%H:%M:%S')


def recuperar_procesando():
    """Al arrancar, tareas en 'procesando' por crash previo → resetear."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tareas_git SET estado = 'pendiente' WHERE estado = 'procesando'"
        )
        n = cur.rowcount
        conn.commit()
        conn.close()
        if n:
            print(f"  ↩  {n} tarea(s) atascada(s) → reseteada(s) a 'pendiente'")
    except Exception as e:
        print(f"  ✗ No se pudo recuperar tareas atascadas: {e}")


def get_tareas_pendientes():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, tipo, mensaje FROM tareas_git
            WHERE estado = 'pendiente'
            ORDER BY id ASC
        """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def marcar_procesando(tarea_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tareas_git SET estado = 'procesando', updated_at = NOW() WHERE id = %s",
            (tarea_id,)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  ✗ Error marcando procesando: {e}")
    finally:
        conn.close()


def guardar_resultado(tarea_id, estado, resultado_dict):
    """Guarda el resultado JSON y marca la tarea como 'listo' o 'error'."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tareas_git SET estado = %s, resultado = %s, updated_at = NOW() WHERE id = %s",
            (estado, json.dumps(resultado_dict, ensure_ascii=False), tarea_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  ✗ Error guardando resultado: {e}")
    finally:
        conn.close()


def ejecutar_status():
    """Ejecuta git status --short y retorna dict resultado."""
    try:
        result = subprocess.run(
            ['git', 'status', '--short'],
            cwd=str(APP_DIR), capture_output=True, text=True, timeout=15,
            encoding='utf-8', errors='replace'
        )
        if result.returncode != 0:
            return False, {'error': result.stderr or 'git status falló', 'rc': result.returncode}
        lineas = [l for l in result.stdout.split('\n') if l.strip()] if result.stdout.strip() else []
        return True, {'lineas': lineas, 'total': len(lineas)}
    except subprocess.TimeoutExpired:
        return False, {'error': 'Timeout en git status'}
    except Exception as e:
        return False, {'error': str(e)}


_ARCH_SENSIBLES = ['.env', 'serviceaccountkey', 'firebase-adminsdk',
                   'credentials.json', 'secrets.', 'private_key.json']
_PATRONES_CLAVE = [
    (r'\bAIzaSy[A-Za-z0-9_\-]{33}\b', 'Google/Firebase API key'),
    (r'-----BEGIN (RSA |EC )?PRIVATE KEY-----', 'Private key'),
    (r'"private_key"\s*:\s*"-----BEGIN', 'Firebase private key en JSON'),
    (r'AAAA[A-Za-z0-9_\-]{40,}', 'Token tipo FCM/JWT largo'),
]


def ejecutar_commit_push(mensaje):
    """Ejecuta git add -A, commit y push. Retorna (ok, resultado_dict)."""
    pasos = []
    try:
        # git add -A
        r = subprocess.run(['git', 'add', '-A'], cwd=str(APP_DIR),
                           capture_output=True, text=True, timeout=15,
                           encoding='utf-8', errors='replace')
        pasos.append({'cmd': 'git add -A', 'ok': r.returncode == 0, 'out': r.stdout + r.stderr})
        if r.returncode != 0:
            return False, {'pasos': pasos, 'error': 'git add falló'}

        # Chequeo archivos sensibles
        r_names = subprocess.run(['git', 'diff', '--staged', '--name-only'],
                                  cwd=str(APP_DIR), capture_output=True, text=True, timeout=10,
                                  encoding='utf-8', errors='replace')
        for arch in (r_names.stdout or '').strip().split('\n'):
            for pat in _ARCH_SENSIBLES:
                if pat in arch.lower():
                    subprocess.run(['git', 'reset', 'HEAD'], cwd=str(APP_DIR), capture_output=True)
                    return False, {'pasos': pasos,
                                   'error': f'⚠️ Archivo sensible detectado: {arch} — commit cancelado'}

        # Chequeo patrones de claves en diff
        r_diff = subprocess.run(['git', 'diff', '--staged'],
                                 cwd=str(APP_DIR), capture_output=True, text=True, timeout=15,
                                 encoding='utf-8', errors='replace')
        for pat, nombre in _PATRONES_CLAVE:
            if re.search(pat, r_diff.stdout or ''):
                subprocess.run(['git', 'reset', 'HEAD'], cwd=str(APP_DIR), capture_output=True)
                return False, {'pasos': pasos,
                               'error': f'⚠️ {nombre} detectada en el diff — commit cancelado'}

        # git commit
        r = subprocess.run(['git', 'commit', '-m', mensaje], cwd=str(APP_DIR),
                           capture_output=True, text=True, timeout=15,
                           encoding='utf-8', errors='replace')
        pasos.append({'cmd': 'git commit', 'ok': r.returncode == 0, 'out': r.stdout + r.stderr})
        if r.returncode != 0:
            return False, {'pasos': pasos, 'error': 'git commit falló (¿sin cambios?)'}

        # git push
        r = subprocess.run(['git', 'push'], cwd=str(APP_DIR),
                           capture_output=True, text=True, timeout=60,
                           encoding='utf-8', errors='replace')
        pasos.append({'cmd': 'git push', 'ok': r.returncode == 0, 'out': r.stdout + r.stderr})
        if r.returncode != 0:
            return False, {'pasos': pasos, 'error': 'git push falló'}

        return True, {'pasos': pasos}

    except subprocess.TimeoutExpired:
        return False, {'pasos': pasos, 'error': 'Timeout en operación git'}
    except Exception as e:
        return False, {'pasos': pasos, 'error': str(e)}


def procesar_tarea(tarea):
    tarea_id = tarea['id']
    tipo     = tarea['tipo']
    mensaje  = tarea['mensaje']
    print(f"[{ts()}] ⚙  Tarea #{tarea_id} tipo='{tipo}' {'msg=' + repr(mensaje[:40]) if mensaje else ''}")

    marcar_procesando(tarea_id)

    if tipo == 'status':
        ok, resultado = ejecutar_status()
    elif tipo == 'commit-push':
        if not mensaje:
            ok, resultado = False, {'error': 'Mensaje de commit vacío'}
        elif (APP_DIR / '.claude_working').exists():
            ok, resultado = False, {'error': '⚠️ Claude está trabajando ahora mismo — espera a que termine antes de commitear'}
        else:
            ok, resultado = ejecutar_commit_push(mensaje)
    else:
        ok, resultado = False, {'error': f'Tipo de tarea desconocido: {tipo}'}

    estado_final = 'listo' if ok else 'error'
    guardar_resultado(tarea_id, estado_final, resultado)
    simbolo = '✅' if ok else '✗'
    print(f"[{ts()}] {simbolo} Tarea #{tarea_id} → {estado_final}")


def main():
    if not DB_URL:
        print("✗ DATABASE_URL no configurado. Verifica el .env")
        sys.exit(1)

    if not adquirir_lock():
        print("⚠️  git_bridge ya está corriendo. Saliendo.")
        sys.exit(0)

    print("=" * 55)
    print("  git_bridge.py — TUC TUC")
    print("  Ejecuta tareas git desde Render en PC local")
    print("=" * 55)
    print(f"  BD:      {DB_URL[:40]}...")
    print(f"  Repo:    {APP_DIR}")
    print()
    recuperar_procesando()
    print(f"[{ts()}] Listo. Esperando tareas...\n")

    error_wait = 5

    while True:
        try:
            tareas = get_tareas_pendientes()
            for tarea in tareas:
                procesar_tarea(tarea)

            error_wait = 5
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n[{ts()}] git_bridge detenido.")
            break
        except psycopg2.OperationalError as e:
            print(f"[{ts()}] ✗ Conexión BD perdida: {e}")
            print(f"[{ts()}] ⏳ Reintentando en {error_wait}s...")
            time.sleep(error_wait)
            error_wait = min(error_wait * 2, 60)
        except Exception as e:
            print(f"[{ts()}] ✗ Error: {e}")
            time.sleep(error_wait)
            error_wait = min(error_wait * 2, 60)


if __name__ == '__main__':
    main()
