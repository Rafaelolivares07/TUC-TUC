"""
chat_context_hook.py — Hook UserPromptSubmit de Claude Code
Inyecta el historial reciente de chat_mensajes como contexto antes de cada respuesta.
Así Claude ve la conversación de la BD igual que ve los archivos de memoria.
"""
import sys
import io
import os
from pathlib import Path

# Forzar UTF-8 en stdout (Windows usa cp1252 por defecto)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Cargar .env manualmente
_ENV_PATH = Path(r"C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\.env")
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _, _v = _line.partition('=')
            os.environ.setdefault(_k.strip(), _v.strip())

DB_URL   = os.getenv('DATABASE_URL', '')
MAX_MSGS = 20   # últimos mensajes a inyectar
MAX_CHARS = 600  # máximo de chars por mensaje (para no saturar el contexto)


def get_historial():
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DB_URL, connect_timeout=5)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT rol, contenido FROM (
                    SELECT id, rol, contenido
                    FROM chat_mensajes
                    WHERE archivado = FALSE
                    ORDER BY id DESC
                    LIMIT %s
                ) sub ORDER BY id ASC
            """, (MAX_MSGS,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception:
        return []


def main():
    # Leer payload (no lo necesitamos, pero hay que consumir stdin)
    try:
        sys.stdin.read()
    except Exception:
        pass

    historial = get_historial()
    if not historial:
        sys.exit(0)

    lineas = ["━━━ HISTORIAL RECIENTE DEL CHAT (BD PostgreSQL) ━━━"]
    for m in historial:
        nombre   = "Rafael" if m['rol'] == 'user' else "Claude"
        contenido = m['contenido']
        if len(contenido) > MAX_CHARS:
            contenido = contenido[:MAX_CHARS] + "…"
        lineas.append(f"{nombre}: {contenido}")
    lineas.append("━━━ FIN HISTORIAL ━━━")

    print('\n'.join(lineas))
    sys.exit(0)


if __name__ == '__main__':
    main()
