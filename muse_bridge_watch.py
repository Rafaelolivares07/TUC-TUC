# -*- coding: utf-8 -*-
"""muse_bridge_watch: vigila bridge_chat.md N minutos e imprime lo nuevo.
Uso:  python muse_bridge_watch.py [minutos=10]
Para sesiones en vivo: el agente ve mensajes de Telegram en ~15 s.
"""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

V2 = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(V2, 'bridge_chat.md')


def main(argv):
    mins = int(argv[1]) if len(argv) > 1 else 10
    size = os.path.getsize(BRIDGE)
    end = time.time() + mins * 60
    print('WATCH inicio', flush=True)
    while time.time() < end:
        time.sleep(15)
        try:
            ns = os.path.getsize(BRIDGE)
        except OSError:
            continue
        if ns > size:
            with open(BRIDGE, encoding='utf-8', errors='replace') as f:
                f.seek(size)
                new = f.read()
            size = ns
            print('NUEVO-EN-SALA:', flush=True)
            print(new[-600:], flush=True)
    print('WATCH fin', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
