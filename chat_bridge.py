"""
chat_bridge.py — Puente entre /admin/chat (PostgreSQL) y Claude Code (archivos JSON)

Flujo:
  1. Detecta nuevo mensaje 'user' sin respuesta en chat_mensajes
  2. Escribe chat_pendiente.json en la carpeta de memoria de Claude
  3. Espera que Claude Code escriba chat_respuesta.json
  4. Guarda la respuesta en la BD via /api/admin/chat/responder
  5. Borra chat_respuesta.json y vuelve a esperar

Uso:
  py chat_bridge.py
"""

import os
import json
import time
import requests
import psycopg2
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
DB_URL      = os.getenv('DATABASE_URL')
APP_URL     = os.getenv('APP_URL', 'https://tuc-tuc.onrender.com')
MEMORIA_DIR = Path(r"C:\Users\RAFAEL OLIVARES\.claude\projects\C--Users-RAFAEL-OLIVARES\memory")

PENDIENTE_FILE = MEMORIA_DIR / "chat_pendiente.json"
RESPUESTA_FILE = MEMORIA_DIR / "chat_respuesta.json"

POLL_INTERVAL  = 2   # segundos entre checks de la BD
# ────────────────────────────────────────────────────────────────────────────


def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def get_mensaje_pendiente(ultimo_id_procesado):
    """Retorna el mensaje más reciente de 'user' que no tiene respuesta posterior."""
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


def guardar_respuesta_en_bd(contenido):
    """Inserta la respuesta del asistente directamente en la BD."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_mensajes (rol, contenido) VALUES ('assistant', %s)",
            (contenido,)
        )
        conn.commit()
        print(f"  ✓ Respuesta guardada en BD ({len(contenido)} chars)")
    except Exception as e:
        conn.rollback()
        print(f"  ✗ Error guardando respuesta: {e}")
    finally:
        conn.close()


def ts():
    return datetime.now().strftime('%H:%M:%S')


def main():
    print("=" * 55)
    print("  chat_bridge.py — TUC TUC")
    print("  Conectando Claude Code ↔ /admin/chat")
    print("=" * 55)
    print(f"  BD:       {DB_URL[:40]}...")
    print(f"  Memoria:  {MEMORIA_DIR}")
    print()

    # Limpiar archivos residuales
    if PENDIENTE_FILE.exists(): PENDIENTE_FILE.unlink()
    if RESPUESTA_FILE.exists(): RESPUESTA_FILE.unlink()

    # No reprocesar mensajes anteriores al arranque
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) as max_id FROM chat_mensajes")
        row = cur.fetchone()
        ultimo_id = row['max_id'] if row else 0
    finally:
        conn.close()

    print(f"[{ts()}] Listo. Último ID en BD: {ultimo_id}. Esperando mensajes...\n")

    while True:
        try:
            mensaje = get_mensaje_pendiente(ultimo_id)

            if mensaje:
                print(f"[{ts()}] 📨 Nuevo mensaje (ID={mensaje['id']})")
                print(f"         → {mensaje['contenido'][:120]}")

                # Escribir archivo para Claude Code
                with open(PENDIENTE_FILE, 'w', encoding='utf-8') as f:
                    json.dump({
                        'id':        mensaje['id'],
                        'contenido': mensaje['contenido'],
                        'ts':        mensaje['ts']
                    }, f, ensure_ascii=False, indent=2)

                print(f"[{ts()}] 📝 Escrito en chat_pendiente.json")
                print(f"[{ts()}] ⏳ Esperando respuesta en chat_respuesta.json...")

                ultimo_id = mensaje['id']

                # Esperar respuesta de Claude Code
                while not RESPUESTA_FILE.exists():
                    time.sleep(1)

                # Leer respuesta
                with open(RESPUESTA_FILE, 'r', encoding='utf-8') as f:
                    respuesta = json.load(f)

                RESPUESTA_FILE.unlink()
                print(f"[{ts()}] 💬 Respuesta recibida ({len(respuesta['contenido'])} chars)")

                guardar_respuesta_en_bd(respuesta['contenido'])
                print(f"[{ts()}] ✅ Listo. Esperando siguiente mensaje...\n")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n[{ts()}] Bridge detenido.")
            break
        except Exception as e:
            print(f"[{ts()}] ✗ Error: {e}")
            time.sleep(5)


if __name__ == '__main__':
    main()
