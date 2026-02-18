"""
chat_bridge.py — Puente autónomo entre /admin/chat (PostgreSQL) y Claude Code

Flujo completamente autónomo:
  1. Detecta nuevo mensaje 'user' sin respuesta en chat_mensajes
  2. Lee historial reciente + archivos de memoria
  3. Llama a `claude --print` con contexto completo
  4. Guarda la respuesta en la BD directamente
  5. El frontend polling detecta la respuesta y la muestra

Uso:
  py chat_bridge.py
"""

import os
import json
import time
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

POLL_INTERVAL = 3   # segundos entre checks
MAX_HISTORIAL = 20  # mensajes de contexto a incluir
# ────────────────────────────────────────────────────────────────────────────


def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def get_mensaje_pendiente(ultimo_id_procesado):
    """Retorna el mensaje más reciente de 'user' sin respuesta posterior."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, contenido, created_at::text as ts
            FROM chat_mensajes
            WHERE rol = 'user'
              AND id > %s
              AND id > COALESCE(
                  (SELECT MAX(id) FROM chat_mensajes WHERE rol = 'assistant'),
                  0
              )
            ORDER BY id DESC
            LIMIT 1
        """, (ultimo_id_procesado,))
        row = cur.fetchone()
        return dict(row) if row else None
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
            "INSERT INTO chat_mensajes (rol, contenido) VALUES ('assistant', %s)",
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
    """Lee los archivos de memoria relevantes para dar contexto a Claude."""
    archivos = ['SESION_ACTIVA.md', 'PLAN.md']
    contenido = ""
    for nombre in archivos:
        ruta = MEMORIA_DIR / nombre
        if ruta.exists():
            try:
                texto = ruta.read_text(encoding='utf-8')
                contenido += f"\n\n--- {nombre} ---\n{texto[:3000]}"
            except Exception:
                pass
    return contenido


def llamar_claude(mensaje, historial):
    """Llama a claude --print con contexto completo y retorna la respuesta."""

    # Formatear historial
    hist_texto = ""
    for m in historial[:-1]:  # excluir el último (es el mensaje actual)
        nombre = "Rafael" if m['rol'] == 'user' else "Claude"
        hist_texto += f"\n{nombre}: {m['contenido']}"

    # Leer contexto de memoria
    memoria = leer_memoria()

    prompt = f"""Eres el asistente personal de Rafael en el chat de TUC TUC.
Rafael te escribe desde la web app /admin/chat y tú respondes aquí de forma autónoma.
Responde en español, de forma directa y útil.
{memoria}

--- HISTORIAL DEL CHAT ---
{hist_texto if hist_texto else "(sin historial previo)"}

--- NUEVO MENSAJE DE RAFAEL ---
{mensaje}

Responde directamente al mensaje anterior. Solo el contenido de tu respuesta, sin preámbulos."""

    try:
        result = subprocess.run(
            ['claude', '--print', prompt],
            capture_output=True,
            text=True,
            cwd=str(APP_DIR),
            timeout=120
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            err = result.stderr.strip() or "Sin respuesta"
            print(f"  ✗ claude --print error: {err[:200]}")
            return f"_(Error al generar respuesta: {err[:100]})_"
    except subprocess.TimeoutExpired:
        return "_(Timeout al generar respuesta)_"
    except FileNotFoundError:
        return "_(claude no encontrado en PATH — verifica instalación de Claude Code)_"
    except Exception as e:
        return f"_(Error: {e})_"


def ts():
    return datetime.now().strftime('%H:%M:%S')


def main():
    print("=" * 55)
    print("  chat_bridge.py — TUC TUC (modo autónomo)")
    print("  Claude Code responde automáticamente")
    print("=" * 55)
    print(f"  BD:      {DB_URL[:40]}...")
    print(f"  Memoria: {MEMORIA_DIR}")
    print()

    # No reprocesar mensajes anteriores al arranque
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) as max_id FROM chat_mensajes")
        row = cur.fetchone()
        ultimo_id = row['max_id'] if row else 0
    finally:
        conn.close()

    print(f"[{ts()}] Listo. Último ID: {ultimo_id}. Esperando mensajes...\n")

    while True:
        try:
            mensaje = get_mensaje_pendiente(ultimo_id)

            if mensaje:
                print(f"[{ts()}] 📨 Mensaje (ID={mensaje['id']}): {mensaje['contenido'][:80]}")
                ultimo_id = mensaje['id']

                historial = get_historial()
                print(f"[{ts()}] 🧠 Llamando a Claude Code ({len(historial)} msgs contexto)...")

                respuesta = llamar_claude(mensaje['contenido'], historial)
                print(f"[{ts()}] 💬 Respuesta: {respuesta[:80]}...")

                guardar_respuesta(respuesta)
                print(f"[{ts()}] ✅ Listo.\n")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n[{ts()}] Bridge detenido.")
            break
        except Exception as e:
            print(f"[{ts()}] ✗ Error: {e}")
            time.sleep(5)


if __name__ == '__main__':
    main()
