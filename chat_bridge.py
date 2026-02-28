"""
chat_bridge.py — Puente autónomo entre /admin/chat (PostgreSQL) y Claude Code

Flujo:
  1. Detecta mensajes 'user' con estado='pendiente'
  2. Si hay varios, los compacta en un solo bloque (el más reciente puede corregir al anterior)
  3. Marca todos como 'procesando'
  4. Llama a `claude --print` con contexto completo
  5. Guarda UNA respuesta en BD y marca todos como 'respondido'
  6. El frontend polling detecta la respuesta

Uso:
  py chat_bridge.py
"""

import os
import sys
import time
import uuid
import socket
import subprocess
import psycopg2
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
DB_URL      = os.getenv('DATABASE_URL')
MEMORIA_DIR = Path(r"C:\Users\RAFAEL OLIVARES\.claude\projects\C--Users-RAFAEL-OLIVARES\memory")
APP_DIR     = Path(r"C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos")

POLL_INTERVAL      = 3    # segundos entre checks
MAX_HISTORIAL      = 10   # mensajes de contexto a incluir
LOCK_PORT          = 47832
BRIDGE_SESSION_FILE = APP_DIR / 'bridge_session_id.txt'
SESSIONS_DIR       = Path.home() / '.claude' / 'projects'
# ────────────────────────────────────────────────────────────────────────────

_bridge_session_id = None  # cache en memoria para el proceso actual

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


def recuperar_procesando():
    """Al arrancar, cualquier mensaje 'procesando' quedó atascado por crash previo → resetear."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE chat_mensajes SET estado = 'pendiente' WHERE rol = 'user' AND estado = 'procesando'"
        )
        n = cur.rowcount
        conn.commit()
        conn.close()
        if n:
            print(f"  ↩  {n} mensaje(s) atascado(s) en 'procesando' → reseteado(s) a 'pendiente'")
    except Exception as e:
        print(f"  ✗ No se pudo recuperar mensajes atascados: {e}")


def get_mensajes_pendientes():
    """Retorna TODOS los mensajes user con estado='pendiente', en orden cronológico."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, contenido, created_at::text as ts
            FROM chat_mensajes
            WHERE rol = 'user' AND estado = 'pendiente'
            ORDER BY id ASC
        """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def marcar_estado(ids, estado):
    """Marca una lista de mensajes con el estado dado."""
    if not ids:
        return
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE chat_mensajes SET estado = %s WHERE id = ANY(%s)",
            (estado, ids)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  ✗ Error marcando estado '{estado}': {e}")
    finally:
        conn.close()


def get_historial(limite=MAX_HISTORIAL):
    """Retorna los últimos N mensajes del chat para dar contexto."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT rol, contenido FROM (
                SELECT id, rol, contenido FROM chat_mensajes ORDER BY id DESC LIMIT %s
            ) sub ORDER BY id ASC
        """, (limite,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def guardar_respuesta(contenido):
    """Inserta la respuesta del asistente en la BD."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_mensajes (rol, contenido, estado) VALUES ('assistant', %s, NULL)",
            (contenido,)
        )
        conn.commit()
        print(f"  ✓ Respuesta guardada ({len(contenido)} chars)")
    except Exception as e:
        conn.rollback()
        print(f"  ✗ Error guardando: {e}")
    finally:
        conn.close()


def leer_memoria():
    """Lee archivos esenciales de memoria del proyecto."""
    archivos = [
        ('MEMORY.md',        3000),
        ('SESION_ACTIVA.md', 3000),
        ('patterns.md',      2000),
    ]
    contenido = ""
    for nombre, limite in archivos:
        ruta = MEMORIA_DIR / nombre
        if ruta.exists():
            try:
                texto = ruta.read_text(encoding='utf-8')
                contenido += f"\n\n=== {nombre} ===\n{texto[:limite]}"
            except Exception:
                pass
    return contenido


def obtener_sesion_bridge():
    """
    Retorna (session_id, es_primera_vez) para la sesión dedicada del bridge.
    - Primera vez (sin archivo o sesión no encontrada): crea un nuevo UUID y lo guarda.
    - Siguientes veces: carga el UUID del archivo y verifica que el .jsonl existe.
    es_primera_vez=True → usar --session-id (crea la sesión con ese UUID)
    es_primera_vez=False → usar -r/--resume (carga historial de la sesión)
    """
    global _bridge_session_id
    if _bridge_session_id:
        return _bridge_session_id, False

    if BRIDGE_SESSION_FILE.exists():
        session_id = BRIDGE_SESSION_FILE.read_text(encoding='utf-8').strip()
        if session_id:
            session_files = list(SESSIONS_DIR.rglob(f'{session_id}.jsonl'))
            if session_files:
                _bridge_session_id = session_id
                return session_id, False

    # Crear nueva sesión dedicada
    session_id = str(uuid.uuid4())
    BRIDGE_SESSION_FILE.write_text(session_id, encoding='utf-8')
    _bridge_session_id = session_id
    return session_id, True


def get_contexto_git():
    """Últimos commits y archivos cambiados — ayuda a Claude a saber qué ya existe."""
    try:
        log = subprocess.run(
            ['git', 'log', '--oneline', '-8'],
            capture_output=True, text=True, cwd=str(APP_DIR), timeout=10
        )
        diff_stat = subprocess.run(
            ['git', 'diff', 'HEAD~1', '--stat', '--no-color'],
            capture_output=True, text=True, cwd=str(APP_DIR), timeout=10
        )
        resultado = ""
        if log.returncode == 0 and log.stdout.strip():
            resultado += f"Últimos commits:\n{log.stdout.strip()}"
        if diff_stat.returncode == 0 and diff_stat.stdout.strip():
            resultado += f"\n\nArchivos cambiados en último commit:\n{diff_stat.stdout.strip()[:800]}"
        return resultado
    except Exception as e:
        return f"(no se pudo obtener contexto git: {e})"


def construir_bloque(mensajes):
    """
    Construye el bloque de texto que se enviará a Claude.
    Si hay varios mensajes, los compacta en orden cronológico.
    El último mensaje puede corregir o contradecir los anteriores — Claude los lee todos.
    """
    if len(mensajes) == 1:
        return mensajes[0]['contenido']

    lineas = [f"[Rafael envió {len(mensajes)} mensajes seguidos — leerlos en orden, el último puede corregir a los anteriores]\n"]
    for i, m in enumerate(mensajes, 1):
        lineas.append(f"Mensaje {i}: {m['contenido']}")
    return "\n".join(lineas)


def llamar_claude(bloque, historial):
    """Llama a claude -p con contexto completo del proyecto TUC TUC."""

    # Formatear historial
    hist_texto = ""
    for m in historial:
        nombre = "Rafael" if m['rol'] == 'user' else "Claude"
        hist_texto += f"\n{nombre}: {m['contenido']}"

    memoria = leer_memoria()
    git_ctx = get_contexto_git()

    prompt = f"""Eres Claude Code — el mismo asistente que Rafael usa en su terminal para desarrollar TUC TUC.
Rafael te escribe desde /admin/chat (puede estar en su celular o en otro dispositivo).
Tienes acceso completo a las herramientas: puedes leer archivos, editar código, ejecutar bash, etc.
Actúa exactamente como lo harías en una sesión interactiva de Claude Code.
Responde en español. Sé directo y concreto.

El proyecto está en: C:\\Users\\RAFAEL OLIVARES\\Documents\\MiAppMedicamentos
El backend principal es: 1_medicamentos.py

⚠️ REGLA CRÍTICA ANTI-DUPLICADOS: Antes de agregar cualquier función o endpoint a 1_medicamentos.py,
SIEMPRE hacer primero un grep para verificar que no existe ya:
  grep -n "def NOMBRE_FUNCION" 1_medicamentos.py
  grep -n "app.route('/api/RUTA'" 1_medicamentos.py
Si ya existe → editar el existente. NUNCA agregar uno nuevo al final sin verificar.

━━━ CONTEXTO DEL PROYECTO ━━━
{memoria}

━━━ GIT — estado reciente ━━━
{git_ctx}

━━━ HISTORIAL DEL CHAT ━━━
{hist_texto if hist_texto else "(inicio de conversación)"}

━━━ MENSAJE DE RAFAEL ━━━
{bloque}"""

    try:
        claude_cmd = r"C:\Users\RAFAEL OLIVARES\AppData\Roaming\npm\claude.cmd"
        env = os.environ.copy()
        for var in ['CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SESSION_ID',
                    'CLAUDE_CODE_API_KEY_HELPER', 'ANTHROPIC_API_KEY']:
            env.pop(var, None)

        session_id, es_primera_vez = obtener_sesion_bridge()
        if es_primera_vez:
            session_flags = ['--session-id', session_id]
            print(f"  🆕 Nueva sesión bridge: {session_id}")
        else:
            session_flags = ['-r', session_id]
            print(f"  ↩  Reanudando sesión bridge: {session_id[:8]}...")

        result = subprocess.run(
            ['cmd', '/c', claude_cmd] + session_flags + ['-p', '--dangerously-skip-permissions'],
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=str(APP_DIR),
            timeout=60,
            env=env
        )
        print(f"  returncode: {result.returncode}")
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            err = result.stderr.strip() or result.stdout.strip() or "Sin respuesta"
            print(f"  ✗ error: {err[:200]}")
            return f"_(Error al generar respuesta: {err[:100]})_"
    except subprocess.TimeoutExpired:
        return "⚠️ No pude procesar tu mensaje a tiempo. Escríbeme de nuevo en un momento."
    except FileNotFoundError:
        return "_(claude no encontrado en PATH — verifica instalación de Claude Code)_"
    except Exception as e:
        return f"_(Error: {e})_"


def ts():
    return datetime.now().strftime('%H:%M:%S')


def main():
    if not adquirir_lock():
        print("⚠️  Bridge ya está corriendo. Saliendo.")
        sys.exit(0)

    print("=" * 55)
    print("  chat_bridge.py — TUC TUC (modo autónomo)")
    print("  Claude Code responde automáticamente")
    print("=" * 55)
    print(f"  BD:      {DB_URL[:40]}...")
    print(f"  Memoria: {MEMORIA_DIR}")
    print()
    recuperar_procesando()
    print(f"[{ts()}] Listo. Esperando mensajes...\n")

    error_wait = 5  # backoff: empieza en 5s, sube hasta 60s

    while True:
        try:
            mensajes = get_mensajes_pendientes()

            if mensajes:
                ids = [m['id'] for m in mensajes]
                n   = len(mensajes)
                print(f"[{ts()}] 📨 {n} mensaje(s) pendiente(s): {[m['id'] for m in mensajes]}")

                # Marcar como procesando antes de llamar a Claude
                marcar_estado(ids, 'procesando')

                bloque = construir_bloque(mensajes)
                print(f"[{ts()}] 📦 Bloque: {bloque[:120]}{'...' if len(bloque) > 120 else ''}")

                historial = get_historial()
                print(f"[{ts()}] 🧠 Llamando a Claude Code ({len(historial)} msgs contexto)...")

                respuesta = llamar_claude(bloque, historial)
                print(f"[{ts()}] 💬 Respuesta: {respuesta[:80]}...")

                guardar_respuesta(respuesta)
                marcar_estado(ids, 'respondido')
                print(f"[{ts()}] ✅ Listo.\n")

            error_wait = 5  # reset backoff en ciclo exitoso
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n[{ts()}] Bridge detenido.")
            break
        except psycopg2.OperationalError as e:
            print(f"[{ts()}] ✗ Conexión BD perdida: {e}")
            print(f"[{ts()}] ⏳ Reintentando en {error_wait}s...")
            time.sleep(error_wait)
            error_wait = min(error_wait * 2, 60)  # backoff exponencial, máx 60s
        except Exception as e:
            print(f"[{ts()}] ✗ Error: {e}")
            time.sleep(error_wait)
            error_wait = min(error_wait * 2, 60)


if __name__ == '__main__':
    main()
