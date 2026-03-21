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


def get_db():
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DB_URL, connect_timeout=5)
    return conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def get_historial():
    try:
        conn, cur = get_db()
        try:
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


def get_requerimientos():
    try:
        conn, cur = get_db()
        try:
            cur.execute("""
                SELECT id, descripcion, modulo, prioridad, estado, fecha_creacion
                FROM requerimientos
                WHERE estado NOT IN ('Completado', 'Descartado')
                ORDER BY id DESC
                LIMIT 30
            """)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception:
        return []


def set_window_title():
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


def main():
    # Leer payload (no lo necesitamos, pero hay que consumir stdin)
    try:
        sys.stdin.read()
    except Exception:
        pass

    set_window_title()
    historial = get_historial()
    requerimientos = get_requerimientos()

    salida = []

    if historial:
        salida.append("━━━ HISTORIAL RECIENTE DEL CHAT (BD PostgreSQL) ━━━")
        for m in historial:
            nombre   = "Rafael" if m['rol'] == 'user' else "Claude"
            contenido = m['contenido']
            if len(contenido) > MAX_CHARS:
                contenido = contenido[:MAX_CHARS] + "…"
            salida.append(f"{nombre}: {contenido}")
        salida.append("━━━ FIN HISTORIAL ━━━")

    if requerimientos:
        salida.append("━━━ IDEAS / REQUERIMIENTOS PENDIENTES ━━━")
        for r in requerimientos:
            fecha = str(r['fecha_creacion'])[:10] if r['fecha_creacion'] else '?'
            modulo = f" [{r['modulo']}]" if r.get('modulo') else ''
            salida.append(f"#{r['id']} [{r['estado']}][{r['prioridad']}]{modulo} {fecha}: {r['descripcion']}")
        salida.append("━━━ FIN IDEAS ━━━")

    if not salida:
        sys.exit(0)

    print('\n'.join(salida))
    sys.exit(0)


if __name__ == '__main__':
    main()
