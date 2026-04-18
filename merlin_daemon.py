"""
merlin_daemon.py — Daemon unificado TUC TUC v1.0
Fusiona captura_watcher.ps1 + chat_merlin_bridge.py en un solo proceso.

Responsabilidades:
  A) Bridge de conversaciones: atiende mensajes de usuarios en el chat
     (tabla conversaciones + mensajes, donde invitado_id = Merlin)
  B) Captura watcher: detecta mensajes de Rafael en canal='captura',
     activa la terminal de Claude Code via SendKeys
  C) Heartbeat de presencia: reporta idle real al módulo domótica
"""

import io, os, sys, time, socket, ctypes, tempfile, subprocess
import urllib.request
import threading
import urllib.parse
import psycopg2
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# UTF-8 en Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

load_dotenv()

# ── ffmpeg en PATH para Whisper ───────────────────────────────────────────────
_FFMPEG_BIN = r"C:\Users\RAFAEL OLIVARES\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
if _FFMPEG_BIN not in os.environ.get('PATH', ''):
    os.environ['PATH'] = os.environ.get('PATH', '') + os.pathsep + _FFMPEG_BIN

# ── Config ────────────────────────────────────────────────────────────────────
DB_URL         = os.getenv('DATABASE_URL')
APP_DIR        = Path(r"C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos")
CLAUDE_CMD     = r"C:\Users\RAFAEL OLIVARES\.local\bin\claude.exe"
TUCTUC_URL     = "https://tuc-tuc.onrender.com"
HB_TOKEN       = "tuctuc-hb-2026"
CLAUDE_WINDOW  = "Claude Code"

POLL_SEC       = 2     # ciclo base
DB_POLL_CADA   = 10    # check canal='captura' cada N segundos
HB_CADA        = 60    # heartbeat cada N segundos
COOLDOWN_SEC   = 45    # cooldown entre triggers a Claude
SENDKEYS_COOL  = 90    # segundos a ignorar windowsIdle tras SendKeys

LOCK_PORT      = 47835
MAX_HISTORIAL  = 12
MERLIN_NOMBRE  = 'Merlin'
MERLIN_TIPO    = 'merlin'
RAFAEL_ID      = 16

LOG_FILE       = r"C:\Users\RAFAEL OLIVARES\merlin_daemon.log"
INBOX_FILE     = APP_DIR / 'merlin_inbox.json'
OUTBOX_FILE    = APP_DIR / 'merlin_outbox.json'

# ── Estado global (compartido entre loops) ───────────────────────────────────
_lock_socket   = None
_merlin_id     = None
_last_trigger  = None      # datetime último trigger Claude
_last_sendkeys = None      # datetime último SendKeys (para calcular idle efectivo)
_last_hb       = None      # datetime último heartbeat
_last_db_check = None      # datetime último check canal='captura'
_cursor_prev   = (-1, -1)
_relay_activo  = False     # True mientras relay_via_captura espera outbox

MEDIA_PROCS = {'chrome','msedge','firefox','spotify','vlc','wmplayer',
               'groove','mpc-hc','mpc-be','itunes','winamp','potplayer','mpv','obs64','obs32'}

_log_lock = threading.Lock()


# ── Logging ───────────────────────────────────────────────────────────────────

def ts():
    return datetime.now().strftime('%H:%M:%S')

def log(msg):
    line = f"[{ts()}] {msg}"
    print(line, flush=True)
    with _log_lock:
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass


# ── Lock singleton ─────────────────────────────────────────────────────────────

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


# ── Windows APIs (ctypes) ─────────────────────────────────────────────────────

class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_idle_sec():
    lii = _LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    ms = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    return max(0, ms) // 1000

def get_cursor_pos():
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def get_foreground_hwnd():
    return ctypes.windll.user32.GetForegroundWindow()

def show_window(hwnd, cmd):
    ctypes.windll.user32.ShowWindow(hwnd, cmd)


# ── DB ─────────────────────────────────────────────────────────────────────────

def get_conn():
    conn = psycopg2.connect(
        DB_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10,
    )
    conn.cursor().execute("SET TIME ZONE 'America/Bogota'")
    conn.commit()
    return conn


# ── Merlin tercero ─────────────────────────────────────────────────────────────

def get_or_create_merlin():
    global _merlin_id
    if _merlin_id:
        return _merlin_id
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM terceros WHERE tipo_tercero = %s LIMIT 1", (MERLIN_TIPO,))
        row = cur.fetchone()
        if row:
            _merlin_id = row['id']
            log(f"✓ Merlin encontrado: id={_merlin_id}")
            return _merlin_id
        cur.execute(
            "INSERT INTO terceros (nombre, tipo_tercero, foto_perfil) VALUES (%s,%s,%s) RETURNING id",
            (MERLIN_NOMBRE, MERLIN_TIPO,
             'https://res.cloudinary.com/tuctuc/image/upload/v1/tuctuc_chat_avatars/merlin_avatar.png')
        )
        _merlin_id = cur.fetchone()['id']
        conn.commit()
        log(f"✓ Merlin creado: id={_merlin_id}")
        return _merlin_id
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
#  A) BRIDGE — conversaciones de usuarios
# ══════════════════════════════════════════════════════════════

def get_pendientes(merlin_id):
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
        convs = {}
        for r in rows:
            cid = r['conversacion_id']
            if cid not in convs:
                convs[cid] = {
                    'conv_id':    cid,
                    'conv_token': r['conv_token'],
                    'creador_id': r['creador_id'],
                    'msgs':       [],
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
        cur.execute("UPDATE mensajes SET estado = 'leido' WHERE id = ANY(%s)", (msg_ids,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        log(f"✗ Error marcando leídos: {e}")
    finally:
        conn.close()


def guardar_respuesta(conv_id, merlin_id, creador_id, texto):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO mensajes
              (remitente_id, destinatario_id, mensaje, tipo, conversacion_id, estado, fecha)
            VALUES (%s,%s,%s,'texto',%s,'pendiente',CURRENT_TIMESTAMP)
            RETURNING id
        """, (merlin_id, creador_id, texto, conv_id))
        mid = cur.fetchone()['id']
        conn.commit()
        log(f"  ✓ Respuesta insertada (msg_id={mid}, {len(texto)} chars)")
    except Exception as e:
        conn.rollback()
        log(f"  ✗ Error guardando respuesta: {e}")
    finally:
        conn.close()


def get_contexto_usuario(creador_id, conv_id, merlin_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nombre, telefono FROM terceros WHERE id = %s", (creador_id,))
        user = cur.fetchone() or {}
        nombre_usuario = user.get('nombre') or f'Usuario #{creador_id}'
        telefono       = user.get('telefono') or ''

        cur.execute("""
            SELECT nombre, slug, 'restaurante' as tipo
            FROM restaurantes WHERE admin_id = %s AND activo = TRUE
            UNION ALL
            SELECT nombre, slug, 'tienda' as tipo
            FROM tiendas WHERE admin_id = %s AND activo = TRUE
        """, (creador_id, creador_id))
        negocios = cur.fetchall()

        cur.execute("""
            SELECT m.mensaje, m.tipo,
                   CASE WHEN m.remitente_id = %s THEN 'Merlin' ELSE %s END as quien
            FROM mensajes m
            WHERE m.conversacion_id = %s
            ORDER BY m.fecha DESC LIMIT %s
        """, (merlin_id, nombre_usuario, conv_id, MAX_HISTORIAL))
        historial = list(reversed(cur.fetchall()))
        return {
            'nombre':    nombre_usuario,
            'telefono':  telefono,
            'negocios':  [dict(n) for n in negocios],
            'historial': [dict(h) for h in historial],
        }
    finally:
        conn.close()


_whisper_model = None
WHISPER_MODEL  = 'tiny'

def _precargar_whisper():
    global _whisper_model
    try:
        import whisper
        log(f'Precargando Whisper ({WHISPER_MODEL})...')
        _whisper_model = whisper.load_model(WHISPER_MODEL)
        log('✓ Whisper listo')
    except Exception as e:
        log(f'⚠ Whisper no disponible: {e}')

def transcribir_audio(url):
    global _whisper_model
    if not url:
        return None
    try:
        import whisper
        if _whisper_model is None:
            _whisper_model = whisper.load_model(WHISPER_MODEL)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmppath = tmp.name
        urllib.request.urlretrieve(url, tmppath)
        try:
            result = _whisper_model.transcribe(tmppath, language='es')
            texto = result.get('text', '').strip()
        finally:
            try: os.unlink(tmppath)
            except: pass
        return texto if texto else None
    except ImportError:
        return None
    except Exception as e:
        log(f'  ✗ Error transcribiendo audio: {e}')
        return None

def _contenido_msg(m):
    tipo = m.get('tipo', 'texto')
    if tipo == 'audio':
        t = transcribir_audio(m.get('url_archivo'))
        return f'[Audio]: {t}' if t else '[Audio — sin transcripción]'
    if tipo == 'imagen':
        return '[Imagen enviada]'
    return m.get('mensaje') or f'[{tipo}]'

def construir_prompt(ctx, msgs_nuevos):
    nombre   = ctx['nombre']
    negocios = ctx['negocios']
    historial = ctx['historial']
    neg_texto = '\n'.join(
        f"  - {n['tipo'].capitalize()}: {n['nombre']} (/{n['tipo'][0]}/{n['slug']})"
        for n in negocios
    ) if negocios else '  (sin negocios registrados aún)'
    hist_texto = '\n'.join(
        "{}: {}".format(h['quien'], h['mensaje'] or '[{}]'.format(h['tipo']))
        for h in historial
    )
    if len(msgs_nuevos) == 1:
        nuevo_texto = _contenido_msg(msgs_nuevos[0])
    else:
        lineas = [f"[{nombre} envió {len(msgs_nuevos)} mensajes seguidos]"]
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

━━━ HISTORIAL ━━━
{hist_texto or '(inicio de conversación)'}

━━━ MENSAJE NUEVO DE {nombre.upper()} ━━━
{nuevo_texto}

Responde en español. Sé directo, útil y amigable. Máximo 3 párrafos cortos.
Si el usuario pregunta algo técnico que no puedes resolver desde aquí, dile que le avise a Rafael."""

def _cmd_claude(extra_flags, prompt, timeout=45):
    env = os.environ.copy()
    for var in ['CLAUDECODE','CLAUDE_CODE_ENTRYPOINT','CLAUDE_CODE_SESSION_ID',
                'CLAUDE_CODE_API_KEY_HELPER','ANTHROPIC_API_KEY']:
        env.pop(var, None)
    return subprocess.run(
        [CLAUDE_CMD] + extra_flags + ['-p', '--dangerously-skip-permissions'],
        input=prompt, capture_output=True, text=True,
        encoding='utf-8', errors='replace',
        cwd=str(APP_DIR), timeout=timeout, env=env,
    )

def llamar_claude(prompt):
    try:
        result = _cmd_claude([], prompt, timeout=45)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        err = result.stderr.strip() or result.stdout.strip() or 'Sin respuesta'
        log(f"  ✗ Claude error: {err[:200]}")
        return '_(No pude generar una respuesta en este momento. Intenta de nuevo.)_'
    except subprocess.TimeoutExpired:
        return '⚠️ Me tomó más tiempo del esperado. Escríbeme de nuevo en un momento.'
    except FileNotFoundError:
        return '_(claude no encontrado — verifica instalación)_'
    except Exception as e:
        return f'_(Error: {e})_'


# ══════════════════════════════════════════════════════════════
#  B) CAPTURA WATCHER — mensajes de Rafael → Claude Code
# ══════════════════════════════════════════════════════════════

def _escribir_inbox(contenido):
    import json
    INBOX_FILE.write_text(
        json.dumps({'contenido': contenido}, ensure_ascii=False),
        encoding='utf-8'
    )

def check_outbox():
    """Si merlin_outbox.json existe, inserta respuesta en chat_mensajes y borra el archivo."""
    if not OUTBOX_FILE.exists():
        return False
    try:
        import json
        data = json.loads(OUTBOX_FILE.read_text(encoding='utf-8'))
        respuesta = data.get('contenido', '').strip()
        OUTBOX_FILE.unlink()
        if not respuesta:
            return False
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chat_mensajes (rol, contenido, canal) VALUES ('assistant',%s,'captura')",
                (respuesta,)
            )
            conn.commit()
            log(f"✓ Outbox → BD ({len(respuesta)} chars)")
        finally:
            conn.close()
        return True
    except Exception as e:
        log(f"✗ Error procesando outbox: {e}")
        return False

def get_captura_pendiente():
    """Retorna True si hay mensaje pendiente; escribe merlin_inbox.json con el contenido."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, contenido FROM chat_mensajes
            WHERE archivado = FALSE
              AND rol = 'user'
              AND canal = 'captura'
              AND created_at > NOW() - INTERVAL '10 minutes'
              AND id > COALESCE(
                    (SELECT MAX(id) FROM chat_mensajes
                     WHERE archivado = FALSE AND rol = 'assistant'), 0)
            ORDER BY id DESC LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            _escribir_inbox(row['contenido'])
            return True
        return False
    finally:
        conn.close()


def activar_claude():
    """Activa la terminal de Claude Code y envía __MERLIN__ via SendKeys."""
    global _last_trigger, _last_sendkeys
    try:
        import win32com.client
        import win32gui
        import win32con

        prev_hwnd = get_foreground_hwnd()
        wshell = win32com.client.Dispatch("WScript.Shell")
        sent = False

        if wshell.AppActivate(CLAUDE_WINDOW):
            time.sleep(0.4)
            wshell.SendKeys("__MERLIN__")
            wshell.SendKeys("{ENTER}")
            sent = True
        else:
            # Fallback: buscar por WindowsTerminal
            import win32process
            def _enum(hwnd, result):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if 'WindowsTerminal' in title or 'claude' in title.lower():
                        result.append(hwnd)
            hwnds = []
            win32gui.EnumWindows(_enum, hwnds)
            for hwnd in hwnds:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if wshell.AppActivate(pid):
                        time.sleep(0.4)
                        wshell.SendKeys("__MERLIN__")
                        wshell.SendKeys("{ENTER}")
                        sent = True
                        break
                except Exception:
                    pass

        if sent:
            now = datetime.now()
            _last_trigger  = now
            _last_sendkeys = now
            time.sleep(0.15)
            # Minimizar terminal (SW_MINIMIZE=6) y devolver foco al navegador
            term_hwnd = get_foreground_hwnd()
            if term_hwnd and term_hwnd != prev_hwnd:
                show_window(term_hwnd, 6)
            time.sleep(0.1)
            if prev_hwnd:
                try:
                    wshell.AppActivate(int(ctypes.windll.user32.GetWindowThreadProcessId(prev_hwnd, None)))
                except Exception:
                    pass
            log("Terminal activada OK")
        else:
            log(f"Ventana '{CLAUDE_WINDOW}' no encontrada")
        return sent
    except Exception as e:
        log(f"Error activando Claude: {e}")
        return False


def relay_via_captura(conv_id, merlin_id, creador_id, msgs_nuevos):
    """
    Para Rafael: escribe inbox, activa Claude y espera el outbox (sin polling a BD).
    """
    global _relay_activo
    if len(msgs_nuevos) == 1:
        nuevo_texto = _contenido_msg(msgs_nuevos[0])
    else:
        lineas = [f'[Rafael envió {len(msgs_nuevos)} mensajes seguidos]']
        for i, m in enumerate(msgs_nuevos, 1):
            lineas.append(f'Mensaje {i}: {_contenido_msg(m)}')
        nuevo_texto = '\n'.join(lineas)

    # Insertar en chat_mensajes para que el bridge lo archive correctamente
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_mensajes (rol, contenido, canal) VALUES ('user',%s,'captura') RETURNING id",
            (nuevo_texto,)
        )
        chat_id = cur.fetchone()['id']
        conn.commit()
        log(f'  Relay captura id={chat_id}. Activando Claude...')
    finally:
        conn.close()

    _escribir_inbox(nuevo_texto)
    _relay_activo = True
    activar_claude()

    # Esperar outbox hasta 3 minutos — sin tocar la BD
    respuesta = None
    for _ in range(90):
        time.sleep(2)
        if OUTBOX_FILE.exists():
            try:
                import json
                data = json.loads(OUTBOX_FILE.read_text(encoding='utf-8'))
                respuesta = data.get('contenido', '').strip()
                OUTBOX_FILE.unlink()
            except Exception as e:
                log(f'  ✗ Error leyendo outbox: {e}')
            break

    _relay_activo = False

    # Archivar el mensaje de captura
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE chat_mensajes SET archivado=TRUE WHERE id=%s", (chat_id,))
        conn.commit()
    finally:
        conn.close()

    return respuesta or '⚠️ Sin respuesta. Escríbeme de nuevo en un momento.'


# ══════════════════════════════════════════════════════════════
#  C) HEARTBEAT — presencia domótica
# ══════════════════════════════════════════════════════════════

def get_active_window_title():
    buf = ctypes.create_unicode_buffer(128)
    ctypes.windll.user32.GetWindowTextW(get_foreground_hwnd(), buf, 128)
    return buf.value

def send_heartbeat(idle_sec):
    global _cursor_prev
    cx, cy = get_cursor_pos()
    prev_cx, prev_cy = _cursor_prev
    mouse = 1 if (prev_cx == -1 or cx != prev_cx or cy != prev_cy) else 0
    _cursor_prev = (cx, cy)

    audio = 0
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'cpu_times']):
            if proc.info['name'] and proc.info['name'].lower().rstrip('.exe') in MEDIA_PROCS:
                audio = 1
                break
    except Exception:
        pass

    ventana = get_active_window_title()[:60]
    ventana_enc = urllib.parse.quote(ventana)

    try:
        uri = f"{TUCTUC_URL}/api/domotica/heartbeat?token={HB_TOKEN}&idle={idle_sec}&mouse={mouse}&audio={audio}&ventana={ventana_enc}"
        req = urllib.request.Request(uri, headers={'User-Agent': 'merlin-daemon/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            import json
            data = json.loads(resp.read())
        log(f"Heartbeat: idle={idle_sec}s mouse={mouse} audio={audio} ventana='{ventana}' activo={data.get('activo')}")
        if data.get('comando') == 'shutdown':
            log("Comando shutdown recibido — apagando en 15 seg...")
            subprocess.Popen(['shutdown.exe', '/s', '/f', '/t', '15'])
    except Exception as e:
        log(f"Heartbeat error: {e}")


# ══════════════════════════════════════════════════════════════
#  LOOP PRINCIPAL
# ══════════════════════════════════════════════════════════════

def main():
    global _last_hb, _last_db_check, _last_trigger, _last_sendkeys

    if not adquirir_lock():
        print('⚠️  Merlin daemon ya está corriendo. Saliendo.')
        sys.exit(0)

    print('=' * 55)
    print('  TUC TUC — Merlin Daemon v1.0')
    print('  Bridge + Watcher + Heartbeat unificados')
    print('=' * 55)
    print(f'  BD: {(DB_URL or "")[:40]}...')
    print()

    _precargar_whisper()
    merlin_id = get_or_create_merlin()
    log(f'Merlin listo (id={merlin_id}). Iniciando loops...')

    error_wait = 5

    while True:
        try:
            now = datetime.now()

            # ── Idle efectivo (corrige contaminación por SendKeys) ─────────────
            windows_idle = get_idle_sec()
            if _last_sendkeys:
                sk_sec = (now - _last_sendkeys).total_seconds()
                effective_idle = 0 if sk_sec < SENDKEYS_COOL else windows_idle
            else:
                effective_idle = windows_idle

            # ── C) Heartbeat ──────────────────────────────────────────────────
            hb_elapsed = (now - _last_hb).total_seconds() if _last_hb else 9999
            if hb_elapsed >= HB_CADA:
                send_heartbeat(effective_idle)
                _last_hb = now

            # ── B) Outbox (respuesta de Claude lista en archivo) ─────────────
            if not _relay_activo:
                check_outbox()

            # ── B) Check canal='captura' (throttled) ──────────────────────────
            db_elapsed = (now - _last_db_check).total_seconds() if _last_db_check else 9999
            if db_elapsed >= DB_POLL_CADA and not _relay_activo:
                _last_db_check = now
                trigger_elapsed = (now - _last_trigger).total_seconds() if _last_trigger else 9999
                if get_captura_pendiente() and trigger_elapsed > COOLDOWN_SEC:
                    log("Mensaje pendiente en captura — activando Claude...")
                    activar_claude()

            # ── A) Bridge conversaciones usuarios ────────────────────────────
            grupos = get_pendientes(merlin_id)
            for g in grupos:
                conv_id    = g['conv_id']
                creador_id = g['creador_id']
                msgs       = g['msgs']
                msg_ids    = [m['id'] for m in msgs]
                n          = len(msgs)
                log(f"📨 Conv {conv_id}: {n} msg(s) de usuario {creador_id}")
                marcar_leidos(msg_ids)
                ctx = get_contexto_usuario(creador_id, conv_id, merlin_id)
                if creador_id == RAFAEL_ID:
                    log(f"  Rafael → relay captura...")
                    respuesta = relay_via_captura(conv_id, merlin_id, creador_id, msgs)
                else:
                    prompt = construir_prompt(ctx, msgs)
                    log(f"  Llamando Claude ({len(ctx['historial'])} msgs contexto)...")
                    respuesta = llamar_claude(prompt)
                log(f"  💬 {respuesta[:80]}...")
                guardar_respuesta(conv_id, merlin_id, creador_id, respuesta)
                log("  ✅ Listo.")

            error_wait = 5
            time.sleep(POLL_SEC)

        except KeyboardInterrupt:
            log('Daemon detenido.')
            break
        except psycopg2.OperationalError as e:
            log(f'✗ BD perdida: {e}')
            time.sleep(error_wait)
            error_wait = min(error_wait * 2, 60)
        except Exception as e:
            log(f'✗ Error: {e}')
            time.sleep(error_wait)
            error_wait = min(error_wait * 2, 60)


if __name__ == '__main__':
    main()
