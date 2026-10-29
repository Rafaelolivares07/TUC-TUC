# -*- coding: utf-8 -*-
"""muse_inbox_consume: borra del inbox solo los message_id indicados.
Uso: muse_inbox_consume.py <id1> [<id2> ...]
Si no queda nada, borra el archivo. Imprime restantes.
Nunca borra a ciegas: lo no visto se conserva para el proximo wake.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(BASE, 'muse_inbox.json')


def main(ids):
    if not os.path.exists(INBOX):
        print('sin inbox')
        return 0
    with open(INBOX, encoding='utf-8') as f:
        msgs = json.load(f)
    if isinstance(msgs, dict):
        msgs = [msgs]
    seen = set(str(i) for i in ids)
    rest = [m for m in msgs if str(m.get('message_id')) not in seen]
    if rest:
        with open(INBOX, 'w', encoding='utf-8') as f:
            json.dump(rest, f, ensure_ascii=False)
    else:
        os.remove(INBOX)
    print('restantes: %d' % len(rest))
    return 0


if __name__ == '__main__':
    main(sys.argv[1:])
