"""
chat_terminal_hook.py — Hook Stop de Claude Code
Guarda la conversación de la sesión terminal en chat_mensajes (PostgreSQL).
Se ejecuta automáticamente cada vez que Claude Code termina de responder.

Formato real del transcript: JSONL (una línea = un evento)
  type='user'      → message.content es str o lista de blocks
  type='assistant' → message.content es lista (puede incluir thinking, text, tool_use)

Flujo:
  1. Hook Stop llama este script vía stdin (JSON con session_id y transcript_path)
  2. Lee el JSONL del transcript
  3. Extrae mensajes nuevos (user texto + assistant texto, ignorando tool calls/thinking)
  4. Los inserta en chat_mensajes para que aparezcan en /admin/chat
  5. Guarda el uuid del último evento procesado (evita duplicados)
"""
import sys
import json
import os
from pathlib import Path

# Cargar .env manualmente
_ENV_PATH = Path(r"C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\.env")
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _, _v = _line.partition('=')
            os.environ.setdefault(_k.strip(), _v.strip())

DB_URL     = os.getenv('DATABASE_URL', '')
STATE_FILE = Path(r"C:\Users\RAFAEL OLIVARES\.claude\chat_hook_state.json")


def log(msg):
    print(f"[chat_hook] {msg}", file=sys.stderr)


def extraer_texto_assistant(content):
    """
    Extrae solo los bloques type='text' del assistant.
    Ignora: thinking, tool_use, tool_result.
    content es una lista de blocks.
    """
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ''
    partes = []
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'text':
            t = block.get('text', '').strip()
            if t:
                partes.append(t)
    return '\n'.join(partes).strip()


def extraer_texto_user(content):
    """
    Extrae texto del mensaje user.
    content puede ser str o lista de blocks.
    Retorna '' si es un tool_result (mensajes del sistema, no del usuario).
    """
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ''
    if not content:
        return ''
    primer = content[0] if isinstance(content[0], dict) else {}
    # Si el primer bloque es tool_result → no es texto del usuario
    if primer.get('type') == 'tool_result':
        return ''
    partes = []
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'text':
            t = block.get('text', '').strip()
            if t:
                partes.append(t)
    return '\n'.join(partes).strip()


def leer_estado(session_id):
    """Retorna el uuid del último evento guardado para esta sesión."""
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
            if data.get('session_id') == session_id:
                return data.get('last_uuid', None)
    except Exception:
        pass
    return None


def guardar_estado(session_id, last_uuid):
    try:
        STATE_FILE.write_text(
            json.dumps({'session_id': session_id, 'last_uuid': last_uuid}),
            encoding='utf-8'
        )
    except Exception as e:
        log(f"Error guardando estado: {e}")


def set_window_title():
    """Guarda el PID de Windows Terminal para que el watcher pueda activarlo."""
    try:
        import subprocess
        r = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-Process WindowsTerminal -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Id'],
            capture_output=True, text=True, timeout=5
        )
        pid_str = r.stdout.strip()
        if pid_str.isdigit():
            Path(r"C:\Users\RAFAEL OLIVARES\claude_pid.txt").write_text(pid_str)
    except Exception:
        pass


def hay_mensaje_voz_reciente(cur):
    """True si hay un mensaje de canal='voz' en los últimos 5 minutos."""
    try:
        cur.execute("""
            SELECT 1 FROM chat_mensajes
            WHERE canal = 'voz' AND rol = 'user'
              AND created_at >= NOW() - INTERVAL '30 minutes'
            LIMIT 1
        """)
        return cur.fetchone() is not None
    except Exception:
        return False


def insertar_en_bd(mensajes):
    """mensajes = lista de (rol, contenido). Inserta en chat_mensajes."""
    if not mensajes or not DB_URL:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL, connect_timeout=10)
        try:
            cur = conn.cursor()
            es_voz = hay_mensaje_voz_reciente(cur)
            canal = 'voz' if es_voz else 'terminal'
            for rol, contenido in mensajes:
                cur.execute(
                    f"INSERT INTO chat_mensajes (rol, contenido, estado, canal) VALUES (%s, %s, NULL, '{canal}')",
                    (rol, contenido)
                )
            conn.commit()
            log(f"{len(mensajes)} mensaje(s) guardado(s) en BD")
        except Exception as e:
            conn.rollback()
            log(f"Error INSERT: {e}")
        finally:
            conn.close()
    except Exception as e:
        log(f"Error conexión BD: {e}")


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        payload = json.loads(raw)
    except Exception as e:
        log(f"Error leyendo payload: {e}")
        sys.exit(0)

    session_id      = payload.get('session_id', '')
    transcript_path = payload.get('transcript_path', '')

    if not transcript_path:
        sys.exit(0)

    tp = Path(transcript_path)
    if not tp.exists():
        log(f"Transcript no encontrado: {transcript_path}")
        sys.exit(0)

    # Leer el JSONL evento por evento
    eventos = []
    try:
        with open(tp, encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    eventos.append(json.loads(line))
                except Exception:
                    pass
    except Exception as e:
        log(f"Error leyendo transcript: {e}")
        sys.exit(0)

    last_uuid = leer_estado(session_id)
    nuevos    = []
    nuevo_last_uuid = last_uuid
    encontrado_last = (last_uuid is None)  # si no hay estado, procesar todo

    for evento in eventos:
        uuid = evento.get('uuid', '')
        tipo = evento.get('type', '')

        # Avanzar hasta pasar el último evento ya procesado
        if not encontrado_last:
            if uuid == last_uuid:
                encontrado_last = True
            continue

        if tipo == 'user':
            msg     = evento.get('message', {})
            content = msg.get('content', '')
            texto   = extraer_texto_user(content)
            if texto:
                nuevos.append(('user', texto))
                nuevo_last_uuid = uuid

        elif tipo == 'assistant':
            msg     = evento.get('message', {})
            content = msg.get('content', [])
            texto   = extraer_texto_assistant(content)
            if texto:
                nuevos.append(('assistant', texto))
                nuevo_last_uuid = uuid

    if nuevos:
        insertar_en_bd(nuevos)
        if nuevo_last_uuid:
            guardar_estado(session_id, nuevo_last_uuid)

    set_window_title()
    sys.exit(0)


if __name__ == '__main__':
    main()
