"""
chat_merlin_bridge.py — Merlin como contacto en el chat de invitados TUC TUC

Flujo:
  1. Al arrancar: garantiza que existe el tercero 'Merlin' en BD
  2. Detecta mensajes nuevos (estado='pendiente') en conversaciones
     donde invitado_id = MERLIN_ID y remitente != Merlin
  3. Agrupa mensajes por conversación, genera contexto del usuario
  4. Llama a `claude --print` con ese contexto
  5. Inserta la respuesta de Merlin en mensajes (remitente_id = MERLIN_ID)
  6. Marca los mensajes del usuario como 'leido'

Diferencia con chat_bridge.py:
  - Atiende el chat de usuarios finales (tabla conversaciones + mensajes)
  - El contexto es del usuario (quién es, sus negocios, historial de conv)
  - No es un asistente de desarrollo — es Merlin como contacto TUC TUC

Uso:
  py chat_merlin_bridge.py
"""

import io
import os
import sys
import time
import uuid
import socket
import tempfile
import subprocess
import urllib.request
import psycopg2
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# UTF-8 en Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
DB_URL         = os.getenv('DATABASE_URL')
APP_DIR        = Path(r"C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos")
CLAUDE_CMD     = r"C:\Users\RAFAEL OLIVARES\.local\bin\claude.exe"
SESSIONS_DIR   = Path.home() / '.claude' / 'projects'
MEMORIA_DIR    = Path(r"C:\Users\RAFAEL OLIVARES\.claude\projects\C--Users-RAFAEL-OLIVARES-Documents-MiAppMedicamentos\memory")
SESSION_FILE   = APP_DIR / 'merlin_rafael_session_id.txt'  # sesión persistente para Rafael

POLL_INTERVAL  = 4     # segundos entre checks
MAX_HISTORIAL  = 12    # mensajes de contexto por conversación
LOCK_PORT      = 47834 # diferente al de chat_bridge (47832) y git_bridge
MERLIN_NOMBRE  = 'Merlin'
MERLIN_TIPO    = 'merlin'
RAFAEL_ID      = 16    # tercero_id de Rafael — usa sesión persistente con herramientas
# ─────────────────────────────────────────────────────────────────────────────

_lock_socket    = None
_merlin_id      = None   # cache en memoria
_rafael_session = None   # cache de session_id para Rafael


def ts():
    return datetime.now().strftime('%H:%M:%S')


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


# ── Merlin tercero ────────────────────────────────────────────────────────────

def get_or_create_merlin():
    """Garantiza que existe el tercero Merlin en BD. Devuelve su id."""
    global _merlin_id
    if _merlin_id:
        return _merlin_id
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Buscar existente
        cur.execute(
            "SELECT id FROM terceros WHERE tipo_tercero = %s LIMIT 1",
            (MERLIN_TIPO,)
        )
        row = cur.fetchone()
        if row:
            _merlin_id = row['id']
            print(f"  ✓ Merlin encontrado: terceros.id = {_merlin_id}")
            return _merlin_id
        # Crear
        cur.execute(
            """INSERT INTO terceros (nombre, tipo_tercero, foto_perfil)
               VALUES (%s, %s, %s) RETURNING id""",
            (MERLIN_NOMBRE, MERLIN_TIPO,
             'https://res.cloudinary.com/tuctuc/image/upload/v1/tuctuc_chat_avatars/merlin_avatar.png')
        )
        _merlin_id = cur.fetchone()['id']
        conn.commit()
        print(f"  🆕 Merlin creado: terceros.id = {_merlin_id}")
        return _merlin_id
    finally:
        conn.close()


# ── Mensajes pendientes ───────────────────────────────────────────────────────

def get_pendientes(merlin_id):
    """
    Retorna lista de conversaciones con mensajes pendientes para Merlin.
    Cada elemento: {conv_id, conv_token, creador_id, msgs: [{id, mensaje, tipo, fecha}]}
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT m.id, m.conversacion_id, m.remitente_id, m.mensaje, m.tipo, m.fecha::text,
                   m.url_archivo, c.token as conv_token, c.creador_id
            FROM mensajes m
            JOIN conversaciones c ON c.id = m.conversacion_id
            WHERE c.invitado_id   = %s
              AND c.activa        = TRUE
              AND m.remitente_id != %s
              AND m.estado        = 'pendiente'
              AND m.tipo          IN ('texto', 'imagen', 'audio')
            ORDER BY m.conversacion_id ASC, m.id ASC
        """, (merlin_id, merlin_id))
        rows = cur.fetchall()

        # Agrupar por conversación
        convs = {}
        for r in rows:
            cid = r['conversacion_id']
            if cid not in convs:
                convs[cid] = {
                    'conv_id':   cid,
                    'conv_token': r['conv_token'],
                    'creador_id': r['creador_id'],
                    'msgs':      [],
                }
            convs[cid]['msgs'].append({
                'id':          r['id'],
                'mensaje':     r['mensaje'],
                'tipo':        r['tipo'],
                'fecha':       r['fecha'],
                'url_archivo': r.get('url_archivo'),
            })
        return list(convs.values())
    finally:
        conn.close()


def marcar_leidos(msg_ids):
    if not msg_ids:
        return
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE mensajes SET estado = 'leido' WHERE id = ANY(%s)",
            (msg_ids,)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  ✗ Error marcando leídos: {e}")
    finally:
        conn.close()


def guardar_respuesta(conv_id, merlin_id, creador_id, texto):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO mensajes
              (remitente_id, destinatario_id, mensaje, tipo, conversacion_id, estado, fecha)
            VALUES (%s, %s, %s, 'texto', %s, 'pendiente', CURRENT_TIMESTAMP)
            RETURNING id
        """, (merlin_id, creador_id, texto, conv_id))
        mid = cur.fetchone()['id']
        conn.commit()
        print(f"  ✓ Respuesta insertada (msg_id={mid}, {len(texto)} chars)")
    except Exception as e:
        conn.rollback()
        print(f"  ✗ Error guardando respuesta: {e}")
    finally:
        conn.close()


# ── Contexto del usuario ──────────────────────────────────────────────────────

def get_contexto_usuario(creador_id, conv_id, merlin_id):
    """Recupera nombre, negocios e historial del usuario para armar el prompt."""
    conn = get_conn()
    try:
        cur = conn.cursor()

        # Quién es el usuario
        cur.execute(
            "SELECT nombre, telefono FROM terceros WHERE id = %s",
            (creador_id,)
        )
        user = cur.fetchone() or {}
        nombre_usuario = user.get('nombre') or f'Usuario #{creador_id}'
        telefono       = user.get('telefono') or ''

        # Sus negocios (restaurantes)
        cur.execute("""
            SELECT nombre, slug, 'restaurante' as tipo
            FROM restaurantes WHERE admin_id = %s AND activo = TRUE
            UNION ALL
            SELECT nombre, slug, 'tienda' as tipo
            FROM tiendas WHERE admin_id = %s AND activo = TRUE
        """, (creador_id, creador_id))
        negocios = cur.fetchall()

        # Historial de la conversación
        cur.execute("""
            SELECT m.mensaje, m.tipo,
                   CASE WHEN m.remitente_id = %s THEN 'Merlin' ELSE %s END as quien
            FROM mensajes m
            WHERE m.conversacion_id = %s
            ORDER BY m.fecha DESC
            LIMIT %s
        """, (merlin_id, nombre_usuario, conv_id, MAX_HISTORIAL))
        historial = list(reversed(cur.fetchall()))

        return {
            'nombre':   nombre_usuario,
            'telefono': telefono,
            'negocios': [dict(n) for n in negocios],
            'historial': [dict(h) for h in historial],
        }
    finally:
        conn.close()


# ── Transcripción de audio ────────────────────────────────────────────────────

_whisper_model = None

def transcribir_audio(url):
    """Descarga el WebM de Cloudinary y transcribe con openai-whisper local."""
    global _whisper_model
    if not url:
        return None
    try:
        import whisper
        if _whisper_model is None:
            print('  🔊 Cargando modelo Whisper (base)...')
            _whisper_model = whisper.load_model('base')
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
            urllib.request.urlretrieve(url, tmp.name)
            result = _whisper_model.transcribe(tmp.name, language='es')
            texto = result.get('text', '').strip()
            os.unlink(tmp.name)
            return texto if texto else None
    except ImportError:
        return None  # whisper no instalado — silencioso
    except Exception as e:
        print(f'  ✗ Error transcribiendo audio: {e}')
        return None


def _contenido_msg(m):
    """Convierte un mensaje a texto para el prompt."""
    tipo = m.get('tipo', 'texto')
    if tipo == 'audio':
        transcripcion = transcribir_audio(m.get('url_archivo'))
        if transcripcion:
            return f'[Audio]: {transcripcion}'
        return '[Audio — sin transcripción. Instala openai-whisper para habilitar: pip install openai-whisper]'
    if tipo == 'imagen':
        return f'[Imagen enviada]'
    return m.get('mensaje') or f'[{tipo}]'


# ── Llamada a Claude ──────────────────────────────────────────────────────────

def construir_prompt(ctx, msgs_nuevos):
    nombre   = ctx['nombre']
    negocios = ctx['negocios']
    historial = ctx['historial']

    # Texto de negocios
    if negocios:
        neg_texto = '\n'.join(
            f"  - {n['tipo'].capitalize()}: {n['nombre']} (/{n['tipo'][0]}/{n['slug']})"
            for n in negocios
        )
    else:
        neg_texto = '  (sin negocios registrados aún)'

    # Historial formateado
    hist_texto = ''
    for h in historial:
        contenido = h['mensaje'] or f'[{h["tipo"]}]'
        hist_texto += f"\n{h['quien']}: {contenido}"

    # Mensajes nuevos
    if len(msgs_nuevos) == 1:
        nuevo_texto = _contenido_msg(msgs_nuevos[0])
    else:
        lineas = [f"[{nombre} envió {len(msgs_nuevos)} mensajes seguidos]\n"]
        for i, m in enumerate(msgs_nuevos, 1):
            lineas.append(f"Mensaje {i}: {_contenido_msg(m)}")
        nuevo_texto = '\n'.join(lineas)

    return f"""Eres Merlin, el asistente inteligente de TUC TUC.
TUC TUC es una plataforma de servicios locales en Colombia: restaurantes, tiendas, transporte, domótica.
Tu rol es ayudar a los usuarios con su negocio en TUC TUC y con cualquier pregunta general.

Sobre el usuario con quien hablas:
- Nombre: {nombre}
- Teléfono: {ctx['telefono'] or 'no registrado'}
- Sus negocios en TUC TUC:
{neg_texto}

━━━ HISTORIAL DE ESTA CONVERSACIÓN ━━━
{hist_texto if hist_texto else '(inicio de conversación)'}

━━━ MENSAJE NUEVO DE {nombre.upper()} ━━━
{nuevo_texto}

Responde en español. Sé directo, útil y amigable. Máximo 3 párrafos cortos.
Si el usuario pregunta algo técnico sobre su negocio en TUC TUC que no puedes resolver
desde aquí, dile que le avise a Rafael directamente."""


def _cmd_claude(extra_flags, prompt, timeout=45):
    """Ejecuta claude.exe directamente (sin cmd /c — evita problemas de quoting con espacios en el path)."""
    env = os.environ.copy()
    for var in ['CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SESSION_ID',
                'CLAUDE_CODE_API_KEY_HELPER', 'ANTHROPIC_API_KEY']:
        env.pop(var, None)
    return subprocess.run(
        [CLAUDE_CMD] + extra_flags + ['-p', '--dangerously-skip-permissions'],
        input=prompt,
        capture_output=True, text=True,
        encoding='utf-8', errors='replace',
        cwd=str(APP_DIR), timeout=timeout, env=env,
    )


def llamar_claude(prompt):
    try:
        result = _cmd_claude([], prompt, timeout=45)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        err = result.stderr.strip() or result.stdout.strip() or 'Sin respuesta'
        print(f"  ✗ Claude error: {err[:200]}")
        return '_(No pude generar una respuesta en este momento. Intenta de nuevo.)_'
    except subprocess.TimeoutExpired:
        return '⚠️ Me tomó más tiempo del esperado. Escríbeme de nuevo en un momento.'
    except FileNotFoundError:
        return '_(claude no encontrado — verifica instalación de Claude Code)_'
    except Exception as e:
        return f'_(Error: {e})_'


# ── Sesión persistente Rafael ─────────────────────────────────────────────────

def leer_memoria():
    """Lee todos los archivos .md del directorio de memoria."""
    if not MEMORIA_DIR.exists():
        return '(sin memoria disponible)'
    contenido = ''
    for f in sorted(MEMORIA_DIR.glob('*.md')):
        if f.name == 'MEMORY.md':
            continue
        try:
            contenido += f'\n\n--- {f.stem} ---\n' + f.read_text(encoding='utf-8')
        except Exception:
            pass
    return contenido.strip() or '(sin memoria disponible)'


def relay_via_captura(conv_id, merlin_id, creador_id, msgs_nuevos):
    """
    Para Rafael: en vez de spawnar claude --print, inserta el mensaje en
    chat_mensajes (canal='captura') para que el captura_watcher active esta
    terminal y yo (Claude Code) responda directamente.
    Luego espera la respuesta y la copia a mensajes.
    """
    # Armar texto del mensaje
    if len(msgs_nuevos) == 1:
        nuevo_texto = _contenido_msg(msgs_nuevos[0])
    else:
        lineas = [f'[Rafael envió {len(msgs_nuevos)} mensajes seguidos]']
        for i, m in enumerate(msgs_nuevos, 1):
            lineas.append(f'Mensaje {i}: {_contenido_msg(m)}')
        nuevo_texto = '\n'.join(lineas)

    conn = get_conn()
    try:
        cur = conn.cursor()
        # Max id assistant actual — para detectar respuesta nueva
        cur.execute(
            "SELECT COALESCE(MAX(id), 0) FROM chat_mensajes WHERE rol = 'assistant' AND archivado = FALSE"
        )
        max_asst_antes = cur.fetchone()[0]

        # Insertar en chat_mensajes con canal='captura', sin estado='pendiente'
        # (para que chat_bridge.py no lo tome — él busca estado='pendiente')
        cur.execute(
            "INSERT INTO chat_mensajes (rol, contenido, canal) VALUES ('user', %s, 'captura') RETURNING id",
            (nuevo_texto,)
        )
        chat_id = cur.fetchone()[0]
        conn.commit()
        print(f'  📤 Relay captura id={chat_id}, max_asst={max_asst_antes}. Esperando respuesta...')
    finally:
        conn.close()

    # Esperar hasta 3 minutos a que aparezca la respuesta del assistant
    for _ in range(90):
        time.sleep(2)
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT contenido FROM chat_mensajes WHERE rol = 'assistant' AND archivado = FALSE AND id > %s ORDER BY id DESC LIMIT 1",
                (max_asst_antes,)
            )
            row = cur.fetchone()
            if row:
                # Archivar el mensaje captura para que el watcher no lo reprocese
                cur.execute("UPDATE chat_mensajes SET archivado = TRUE WHERE id = %s", (chat_id,))
                conn.commit()
                return row[0]
        finally:
            conn.close()

    # Timeout — archivar de todas formas
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE chat_mensajes SET archivado = TRUE WHERE id = %s", (chat_id,))
        conn.commit()
    finally:
        conn.close()
    return '⚠️ Sin respuesta. Escríbeme de nuevo en un momento.'


# ── Loop principal ────────────────────────────────────────────────────────────

def main():
    if not adquirir_lock():
        print('⚠️  Merlin bridge ya está corriendo. Saliendo.')
        sys.exit(0)

    print('=' * 55)
    print('  chat_merlin_bridge.py — TUC TUC')
    print('  Merlin como contacto en el chat de invitados')
    print('=' * 55)
    print(f'  BD: {(DB_URL or "")[:40]}...')
    print()

    merlin_id = get_or_create_merlin()
    print(f'[{ts()}] Merlin listo (id={merlin_id}). Esperando mensajes...\n')

    error_wait = 5

    while True:
        try:
            grupos = get_pendientes(merlin_id)

            for g in grupos:
                conv_id    = g['conv_id']
                creador_id = g['creador_id']
                msgs       = g['msgs']
                msg_ids    = [m['id'] for m in msgs]
                n          = len(msgs)

                print(f"[{ts()}] 📨 Conv {conv_id}: {n} mensaje(s) de usuario {creador_id}")

                # Marcar leídos antes de responder (evita que el bridge lo tome dos veces)
                marcar_leidos(msg_ids)

                ctx = get_contexto_usuario(creador_id, conv_id, merlin_id)

                if creador_id == RAFAEL_ID:
                    print(f"[{ts()}] 🔀 Rafael → relay via captura_watcher...")
                    respuesta = relay_via_captura(conv_id, merlin_id, creador_id, msgs)
                else:
                    prompt = construir_prompt(ctx, msgs)
                    print(f"[{ts()}] 🧠 Llamando a Claude ({len(ctx['historial'])} msgs contexto)...")
                    respuesta = llamar_claude(prompt)
                print(f"[{ts()}] 💬 {respuesta[:80]}...")

                guardar_respuesta(conv_id, merlin_id, creador_id, respuesta)
                print(f"[{ts()}] ✅ Listo.\n")

            error_wait = 5
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(f'\n[{ts()}] Bridge detenido.')
            break
        except psycopg2.OperationalError as e:
            print(f'[{ts()}] ✗ BD perdida: {e}')
            print(f'[{ts()}] ⏳ Reintentando en {error_wait}s...')
            time.sleep(error_wait)
            error_wait = min(error_wait * 2, 60)
        except Exception as e:
            print(f'[{ts()}] ✗ Error: {e}')
            time.sleep(error_wait)
            error_wait = min(error_wait * 2, 60)


if __name__ == '__main__':
    main()
