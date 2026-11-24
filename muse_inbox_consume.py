# -*- coding: utf-8 -*-
"""muse_inbox_consume: borra del inbox solo los message_id indicados.
Uso: muse_inbox_consume.py <id1> [<id2> ...]
     muse_inbox_consume.py --para <tag> <carta_id...>  (bus: consumo por destinatario)
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


def main_para(tag, ids):
    """Bus dirigido: saca a tag de cada carta (sin doble-respuesta)."""
    sys.path.insert(0, BASE)
    import muse_bus
    n = 0
    for i in ids:
        if muse_bus.consumir(i, tag):
            n += 1
    rest = len(muse_bus.leer_cartas())
    print('consumidas: %d, restantes: %d' % (n, rest))
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == '--para':
        main_para(args[1], args[2:])
    else:
        main(args)
