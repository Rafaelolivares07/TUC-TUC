import socketio, threading, sys, base64, time, os

SERVER     = "https://remote.tuc-tuc.co"
TOKEN      = "tuctuc-remote-2026"
SESSION    = sys.argv[1] if len(sys.argv) > 1 else "283529"
CHUNK_SIZE = 512 * 1024

# (ruta_local, nombre_en_desktop)
# OBJETIVO: instalar admin_agent.py en PC Pilar + crear AdminAgent.vbs en Startup
# NO usar PilarSetup.exe — falla con MemoryError en el PC de Pilar
ARCHIVOS = [
    (r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\admin_agent.py',  'admin_agent.py'),
    (r'C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\instalar_pilar.bat', 'instalar_pilar.bat'),
]

# Después de enviar archivos, pedir a Pilar que ejecute el bat manualmente
# (exec_result no siempre retorna desde el agente compilado — ver estado_activo.md)
CMDS = [
    r'echo === Archivos recibidos. Pilar: ejecuta instalar_pilar.bat del Escritorio y reinicia el PC ===',
]

sio        = socketio.Client(reconnection=False)
done       = threading.Event()
resultados = []

@sio.event
def connect():
    print(f'Conectado. Sesión {SESSION}...')
    sio.emit('viewer_join', {'token': TOKEN, 'session_id': SESSION})

@sio.on('viewer_ok')
def on_viewer_ok(data=None):
    print('Visor OK')

@sio.on('agent_connected')
def on_agent_connected(data=None):
    print('Agente listo — enviando archivos...')
    threading.Thread(target=_enviar_todo, daemon=True).start()

@sio.on('exec_result')
def on_exec_result(data):
    out = data.get('output', '') if isinstance(data, dict) else str(data)
    print(f'>> {out.strip()}')
    resultados.append(out)
    if len(resultados) >= len(CMDS):
        done.set()

@sio.event
def disconnect():
    done.set()


def _enviar_archivo(ruta, nombre):
    with open(ruta, 'rb') as f:
        data = f.read()
    chunks = [data[i:i+CHUNK_SIZE] for i in range(0, max(len(data),1), CHUNK_SIZE)]
    total  = len(chunks)
    print(f'  Enviando {nombre} ({len(data)//1024} KB, {total} chunks)...')
    for idx, chunk in enumerate(chunks):
        sio.emit('file_chunk_in', {
            'session_id': SESSION,
            'nombre': nombre,
            'idx': idx,
            'total': total,
            'b64': base64.b64encode(chunk).decode(),
        })
        time.sleep(0.04)
    print(f'  {nombre} OK')


def _enviar_todo():
    for ruta, nombre in ARCHIVOS:
        if os.path.exists(ruta):
            _enviar_archivo(ruta, nombre)
        else:
            print(f'  OMITIDO (no encontrado): {ruta}')

    print('\nEsperando ensamblado...')
    time.sleep(4)

    print('Ejecutando comandos...')
    for cmd in CMDS:
        sio.emit('exec', {'session_id': SESSION, 'cmd': cmd})
        time.sleep(2)


if __name__ == '__main__':
    print(f'Servidor: {SERVER}  sesion={SESSION}')
    sio.connect(SERVER, transports=['websocket'])
    done.wait(timeout=180)
    try:
        sio.disconnect()
    except Exception:
        pass
    print('Fin.')
