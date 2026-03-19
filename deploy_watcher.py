"""
deploy_watcher.py — Monitor local de deploy en Render.

Uso (lo llama Claude automáticamente después de cada git push):
    python deploy_watcher.py <commit_hash>

Flujo:
1. Escribe deploy_estado.json con commit, estado=pendiente, fecha
2. Cada 20s consulta https://tuc-tuc.onrender.com/api/version
3. Cuando el commit coincide:
   - Notificación Windows (balloon en bandeja)
   - Notificación Telegram (via servidor — el servidor tiene el token en BD)
   - Estado pasa a 'live', el script termina
4. Timeout a los 30 minutos → notificación de alerta
"""
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'], check=True)
    import requests

APP_URL    = 'https://tuc-tuc.onrender.com'
ESTADO_FILE = Path(__file__).parent / 'deploy_estado.json'
INTERVALO  = 20   # segundos entre checks
MAX_MIN    = 30   # minutos máximo de espera


def notificar_windows(titulo, texto):
    """MessageBox persistente — el usuario debe cerrarla manualmente."""
    ps = (
        f'Add-Type -AssemblyName System.Windows.Forms;'
        f'[System.Windows.Forms.MessageBox]::Show("{texto}", "{titulo}", '
        f'[System.Windows.Forms.MessageBoxButtons]::OK, '
        f'[System.Windows.Forms.MessageBoxIcon]::Information)'
    )
    subprocess.Popen(
        ['powershell', '-WindowStyle', 'Hidden', '-NonInteractive', '-Command', ps],
        creationflags=0x08000000  # CREATE_NO_WINDOW
    )


def notificar_telegram(commit, mensaje_commit):
    """Llama al endpoint del servidor para que mande el Telegram (token está en la BD)."""
    try:
        requests.post(
            f'{APP_URL}/api/webhook/render-deploy',
            json={'commit': {'id': commit, 'message': mensaje_commit}, 'status': 'live'},
            timeout=10
        )
    except Exception as e:
        print(f'[watcher] Error Telegram: {e}')


def main():
    if len(sys.argv) < 2:
        print('[watcher] Uso: python deploy_watcher.py <commit_hash>')
        sys.exit(1)

    commit = sys.argv[1].strip()
    ahora  = datetime.now().isoformat()

    # Obtener el asunto del commit para incluirlo en las notificaciones
    try:
        mensaje_commit = subprocess.check_output(
            ['git', 'log', '--format=%s', '-1', commit],
            cwd=Path(__file__).parent,
            encoding='utf-8'
        ).strip()
    except Exception:
        mensaje_commit = ''

    # Escribir estado inicial
    estado = {'commit': commit, 'estado': 'pendiente', 'iniciado': ahora, 'mensaje': mensaje_commit}
    ESTADO_FILE.write_text(json.dumps(estado, indent=2), encoding='utf-8')
    print(f'[watcher] Deploy pendiente — commit {commit} | {ahora}')

    max_intentos = (MAX_MIN * 60) // INTERVALO
    intento = 0

    while intento < max_intentos:
        time.sleep(INTERVALO)
        intento += 1
        try:
            r = requests.get(f'{APP_URL}/api/version', timeout=10)
            if r.status_code == 200:
                commit_live = r.json().get('commit', '').strip()
                print(f'[watcher] #{intento} live={commit_live} esperado={commit}')
                # Comparar: ambos son short hash (7 chars), puede haber diferencia de longitud
                if commit_live and (commit_live == commit or
                                    commit.startswith(commit_live) or
                                    commit_live.startswith(commit)):
                    # ¡Deploy confirmado!
                    estado['estado']  = 'live'
                    estado['live_at'] = datetime.now().isoformat()
                    ESTADO_FILE.write_text(json.dumps(estado, indent=2), encoding='utf-8')

                    detalle = f'\n{mensaje_commit}' if mensaje_commit else ''
                    notificar_windows(
                        'TUC TUC — Deploy Listo',
                        f'Commit {commit[:7]} en produccion.{detalle}'
                    )
                    notificar_telegram(commit, mensaje_commit)
                    print(f'[watcher] Deploy confirmado en intento #{intento}. Terminando.')
                    return
            else:
                print(f'[watcher] #{intento} HTTP {r.status_code}')
        except Exception as e:
            print(f'[watcher] #{intento} Error: {e}')

    # Timeout
    estado['estado'] = 'timeout'
    ESTADO_FILE.write_text(json.dumps(estado, indent=2), encoding='utf-8')
    notificar_windows(
        'TUC TUC — Deploy Timeout ⚠️',
        f'El commit {commit[:7]} no apareció en {MAX_MIN} min. Revisar Render.'
    )
    print(f'[watcher] Timeout tras {MAX_MIN} minutos.')


if __name__ == '__main__':
    main()
