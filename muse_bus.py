# -*- coding: utf-8 -*-
"""muse_bus: bus dirigido multi-Muse (carta + timbre separados).

Carta = bandeja muse_inbox.json con remitente + para:.
Timbre = inyeccion ConPTY solo a los aludidos (via amarre por tag).
Sala (bridge_chat.md) = acta. Telegram = un remitente mas.

Decisiones muse2 2026-11-24 (tema 12):
a) para: = tag | lista | todos. Telegram entra con para = receptor
   configurado (bus_config.json, default muse2); ese receptor reenvia
   (carta+timbre) si el tema calza mejor en otro tag. Solo UNO responde.
b) Amarre tag->{pid, titulo, sesion, updated} en TEMP por tag
   (muse_amarre_<tag>.json); el tablero solo referencia (amarre_ref).
c) Pendientes a muertas caducan a 24h: nota en sala + vencidos (no borran).
d) Rafa-humano NO es destinatario (lee sala y Telegram).
   Destinatarios: tags muse + salida Telegram (outbox).
e) Timbres de prueba reales solo con ventana autorizada por Rafa.

Uso CLI:
  python muse_bus.py enviar --de muse2 --para muse1 --texto "..."
  python muse_bus.py pendientes --tag muse1
  python muse_bus.py consumir --tag muse1 --id <carta>
  python muse_bus.py reenviar --id <carta> --de muse2 --a muse1
  python muse_bus.py barrer
  python muse_bus.py amarrar --tag muse1 [--titulo ...] [--sesion ...]
  python muse_bus.py soltar --tag muse1
  python muse_bus.py wake --tag muse1
  python muse_bus.py receptor [--fijar muse2]
"""
import argparse
import json
import os
import re
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta

V2 = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(V2, 'muse_inbox.json')
OUTBOX = os.path.join(V2, 'muse_outbox.json')
BRIDGE = os.path.join(V2, 'bridge_chat.md')
CONV = os.path.normpath(os.path.join(V2, '..', 'docs', '_conversacion'))
TABLERO = os.path.join(CONV, 'agentes_estado.json')
BUS_CONFIG = os.path.join(CONV, 'bus_config.json')

TAG_RE = re.compile(r'^muse\d+$')
RECEPTOR_DEFAULT = 'muse2'
CADUCIDAD_HORAS = 24
COOLDOWN_SEC = 30
VERIFY_SEC = 90
TRIGGER = '__MUSE__'
ESTADOS_VIVOS = ('trabajando', 'esperando_deploy', 'desplegando')

_log = None


def _l(msg):
    if _log is not None:
        _log(msg)
    else:
        print(msg, flush=True)


def configure(logfn):
    global _log
    _log = logfn


def ahora_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ==================== DESTINATARIOS ====================

def normalizar_para(para):
    """para: tag | lista | 'todos' -> (es_broadcast, [tags]).
    Acepta 'telegram' como destino (salida outbox). Rechaza Rafa-humano."""
    if isinstance(para, str):
        items = [para.strip().lower()]
    else:
        items = [(p or '').strip().lower() for p in para]
    if not items or not items[0]:
        raise ValueError('para: vacio (usa tag, lista o todos)')
    if items == ['todos']:
        return True, []
    for p in items:
        if not TAG_RE.match(p) and p != 'telegram':
            raise ValueError("para: '%s' no es destinatario (tags muse + telegram; Rafa-humano lee sala)" % p)
    return False, sorted(set(items))


def _cargar_tablero(path=TABLERO):
    try:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def vivos(path=TABLERO):
    """Tags con estado de trabajo en el tablero."""
    tab = _cargar_tablero(path)
    return sorted(t for t, i in tab.items()
                  if TAG_RE.match(t) and isinstance(i, dict)
                  and i.get('estado') in ESTADOS_VIVOS)


def expandir(para, path=TABLERO):
    """Resuelve para: a lista concreta (todos -> vivos del tablero)."""
    bc, tags = normalizar_para(para)
    return vivos(path) if bc else tags


def receptor_telegram(path=BUS_CONFIG):
    """Tag que recibe lo de Telegram (config, default muse2)."""
    try:
        with open(path, encoding='utf-8') as f:
            cfg = json.load(f)
        tag = (cfg.get('receptor_telegram') or '').strip().lower()
        if TAG_RE.match(tag):
            return tag
    except (OSError, ValueError):
        pass
    return RECEPTOR_DEFAULT


def fijar_receptor(tag, path=BUS_CONFIG):
    tag = (tag or '').strip().lower()
    if not TAG_RE.match(tag):
        raise ValueError("receptor '%s' invalido (usa museN)" % tag)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'receptor_telegram': tag}, f, ensure_ascii=False)
    os.replace(tmp, path)
    return tag


# ==================== CARTAS (bandeja) ====================

def leer_cartas(path=INBOX):
    try:
        with open(path, encoding='utf-8') as f:
            cur = json.load(f)
    except (OSError, ValueError):
        return []
    items = cur if isinstance(cur, list) else [cur]
    return [m for m in items if isinstance(m, dict)]


def guardar_cartas(cartas, path=INBOX):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cartas, f, ensure_ascii=False)
    os.replace(tmp, path)


def nueva_id(remitente):
    return 'b%d-%s' % (int(time.time() * 1000), remitente)


def escribir_carta(texto, remitente, para, path=INBOX, extra=None):
    """Agrega carta dirigida. Atomica. Retorna la carta."""
    rem = (remitente or '').strip().lower()
    if not TAG_RE.match(rem) and rem != 'telegram':
        raise ValueError("remitente '%s' invalido (tags muse + telegram)" % remitente)
    dest = expandir(para)
    ahora = datetime.now()
    carta = {'id': nueva_id(rem), 'texto': texto,
             'remitente': rem, 'para': dest,
             'fecha': ahora.strftime('%Y-%m-%d %H:%M:%S'),
             'expira': (ahora + timedelta(hours=CADUCIDAD_HORAS)).strftime('%Y-%m-%d %H:%M:%S'),
             'vencido': False}
    if extra:
        carta.update(extra)
    cartas = leer_cartas(path)
    cartas.append(carta)
    guardar_cartas(cartas, path)
    return carta


def pendientes(tag, path=INBOX):
    """Cartas vigentes dirigidas a tag (sin consumir, sin vencer)."""
    tag = (tag or '').strip().lower()
    return [c for c in leer_cartas(path)
            if not c.get('vencido') and tag in (c.get('para') or [])]


def consumir(carta_id, tag, path=INBOX):
    """Saca a tag de la carta; sin destinatarios se borra. Atomico.
    Segundo consumo del mismo tag -> None (sin doble-respuesta)."""
    tag = (tag or '').strip().lower()
    cartas = leer_cartas(path)
    hallada = None
    resto = []
    for c in cartas:
        if hallada is None and str(c.get('id')) == str(carta_id):
            dest = list(c.get('para') or [])
            if tag in dest:
                dest.remove(tag)
                c['para'] = dest
                hallada = c
            else:
                hallada = False
            if dest or c.get('vencido'):
                resto.append(c)
        else:
            resto.append(c)
    if hallada:
        guardar_cartas(resto, path)
        return hallada
    return None


def reenviar(carta_id, de_tag, a_tag, path=INBOX, timbrar=True):
    """Forward por tema: de_tag suelta la carta y nace carta+timbre a a_tag.
    Solo UNO le responde a Rafa (decision a)."""
    de_tag = (de_tag or '').strip().lower()
    a_tag = (a_tag or '').strip().lower()
    if not TAG_RE.match(a_tag):
        raise ValueError("reenviar a '%s' invalido (solo tags muse)" % a_tag)
    cartas = leer_cartas(path)
    orig = next((c for c in cartas if str(c.get('id')) == str(carta_id)
                 and de_tag in (c.get('para') or [])), None)
    if orig is None:
        return None
    consumir(carta_id, de_tag, path)
    nueva = escribir_carta(orig.get('texto', ''), orig.get('remitente', de_tag),
                           a_tag, path,
                           extra={'via': de_tag, 'reenvio_de': str(carta_id)})
    if timbrar:
        wake_tag([a_tag], {a_tag: [nueva['id']]})
    return nueva


def barrer(path=INBOX, bridge=BRIDGE):
    """Caduca pendientes de +24h: nota en sala + vencidos (no borra)."""
    cartas = leer_cartas(path)
    ahora = datetime.now()
    vencidas = 0
    for c in cartas:
        if c.get('vencido') or not c.get('para'):
            continue
        try:
            exp = datetime.strptime(c.get('expira', ''), '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            continue
        if ahora > exp:
            c['vencido'] = True
            vencidas += 1
            acta('Carta %s de %s para %s VENCIDA sin consumir (24h). Texto: %s'
                 % (c.get('id'), c.get('remitente'), ','.join(c.get('para') or []),
                    (c.get('texto') or '')[:200]), bridge)
    if vencidas:
        guardar_cartas(cartas, path)
    return vencidas


def acta(texto, bridge=BRIDGE):
    entry = '\n---\n\n### [%s] Bus multi-muse:\n\n[bus] %s\n' % (ahora_str(), texto)
    with open(bridge, 'a', encoding='utf-8', newline='') as f:
        f.write(entry)


# ==================== AMARRE (TEMP por tag) ====================

def amarre_path(tag):
    return os.path.join(tempfile.gettempdir(), 'muse_amarre_%s.json' % tag)


def escribir_amarre(tag, pid, titulo=None, sesion=None):
    tag = (tag or '').strip().lower()
    if not TAG_RE.match(tag):
        raise ValueError("amarre a '%s' invalido (usa museN)" % tag)
    data = {'tag': tag, 'pid': pid, 'titulo': titulo, 'sesion': sesion,
            'updated': ahora_str()}
    with open(amarre_path(tag), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def leer_amarre(tag):
    try:
        with open(amarre_path(tag), encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def soltar_amarre(tag):
    try:
        os.unlink(amarre_path(tag))
        return True
    except OSError:
        return False


def _wake():
    sys.path.insert(0, V2)
    import muse_wake
    return muse_wake


def mi_pid_cli(procs=None):
    """Pid de mi CLI: primer ancestro muse subiendo desde este proceso."""
    w = _wake()
    procs = procs if procs is not None else w._snapshot()
    p, seen = os.getpid(), set()
    while p and p not in seen:
        seen.add(p)
        ppid, exe = procs.get(p, (0, ''))
        if _wake()._is_muse(exe):
            return p
        p = ppid
    return None


def validar_amarre(tag, procs=None):
    """Pid amarrado si vivo + es-muse. Muerto/ambiguo -> None (aborto seguro)."""
    a = leer_amarre(tag)
    if not a:
        return None
    try:
        pid = int(a.get('pid'))
    except (TypeError, ValueError):
        return None
    w = _wake()
    procs = procs if procs is not None else w._snapshot()
    if pid in procs and w._is_muse(procs[pid][1]):
        return pid
    return None


def titulo_tag(tag):
    """Titulo de la pestana: archivo por-tag, fallback legado unico."""
    for p in (os.path.join(tempfile.gettempdir(), 'muse_tab_title_%s.txt' % tag),
              os.path.join(tempfile.gettempdir(), 'muse_tab_title.txt')):
        try:
            t = open(p, encoding='utf-8').read().strip()
            if t:
                return t
        except OSError:
            pass
    return None


def amarrar(tag, titulo=None, sesion=None, procs=None):
    """Graba mi amarre (pid CLI propio validado). Lo corre cada sesion."""
    tag = (tag or '').strip().lower()
    pid = mi_pid_cli(procs)
    if not pid:
        raise RuntimeError('sin CLI muse ancestro (corre dentro de tu sesion Muse)')
    return escribir_amarre(tag, pid, titulo or titulo_tag(tag),
                           sesion or os.environ.get('MUSE_SESSION_ID', ''))


# ==================== TIMBRE DIRIGIDO ====================

def _cooldown_path(tag):
    return os.path.join(tempfile.gettempdir(), 'muse_bus_cool_%s.txt' % tag)


def en_cooldown(tag, path=None):
    try:
        ts = float(open(path or _cooldown_path(tag), encoding='utf-8').read().strip())
        return (time.time() - ts) < COOLDOWN_SEC
    except (OSError, ValueError):
        return False


def _marcar_cooldown(tag, path=None):
    try:
        with open(path or _cooldown_path(tag), 'w', encoding='utf-8') as f:
            f.write(str(time.time()))
    except OSError:
        pass


def wake_tag(tags, ids_por_tag=None, verify=True):
    """Timbra solo a tags amarrados y validados. Sin pid claro: aborto
    seguro (carta queda, sin inyectar). Retorna {tag: bool}."""
    w = _wake()
    out = {}
    for tag in tags or []:
        tag = (tag or '').strip().lower()
        if tag == 'telegram' or not TAG_RE.match(tag):
            continue
        if en_cooldown(tag):
            _l('bus: cooldown %s, solo carta' % tag)
            out[tag] = False
            continue
        pid = validar_amarre(tag)
        if not pid:
            _l('bus: %s sin amarre valido, aborto seguro (carta queda)' % tag)
            out[tag] = False
            continue
        try:
            ok = w._conpty_inject(pid, TRIGGER + '\r\n')
        except Exception as e:
            _l('bus: inyeccion %s fallo %s' % (tag, type(e).__name__))
            ok = False
        out[tag] = bool(ok)
        if ok:
            _l('bus: timbre a %s pid=%d' % (tag, pid))
            _marcar_cooldown(tag)
            if verify and ids_por_tag and ids_por_tag.get(tag):
                ids = list(ids_por_tag[tag])
                threading.Thread(target=_verify_tag, args=(tag, ids), daemon=True).start()
    return out


def _sigue_pendiente(tag, ids, path=INBOX):
    have = set()
    for c in leer_cartas(path):
        if tag in (c.get('para') or []) and not c.get('vencido'):
            have.add(str(c.get('id')))
    return [i for i in ids if str(i) in have]


def _verify_tag(tag, ids):
    """Entrega verificada por tag: sin consumo, re-timbra una vez."""
    time.sleep(VERIFY_SEC)
    if not _sigue_pendiente(tag, ids):
        _l('bus: entrega a %s confirmada' % tag)
        return
    _l('bus: %s sin confirmacion, reintento' % tag)
    try:
        os.unlink(_cooldown_path(tag))
    except OSError:
        pass
    wake_tag([tag], verify=False)
    time.sleep(VERIFY_SEC)
    pend = _sigue_pendiente(tag, ids)
    if pend:
        _l('bus: %s SIN CONFIRMACION ids=%s (revisar manual)' % (tag, pend))
        acta('Timbre a %s SIN CONFIRMACION (ids=%s): carta en bandeja, despertar manual.' % (tag, pend))
    else:
        _l('bus: entrega a %s confirmada (2do intento)' % tag)


# ==================== SALIDA TELEGRAM ====================

def entregar_telegram(texto, voz=False, path=OUTBOX):
    """Salida Telegram: escribe outbox (el listener lo envia: voz+texto)."""
    contenido, v = '', False
    try:
        with open(path, encoding='utf-8') as f:
            ob = json.load(f)
        contenido, v = (ob.get('contenido') or ''), bool(ob.get('voz'))
    except (OSError, ValueError):
        pass
    if contenido:
        contenido += '\n---\n'
    contenido += texto
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'contenido': contenido, 'voz': bool(v or voz)}, f, ensure_ascii=False)
    os.replace(tmp, path)


# ==================== ENVIO COMPLETO ====================

def notify_dirigido(texto, remitente, para, chat_id=None, message_id=None, timbrar=True):
    """Carta + timbre a destinatarios. 'telegram' en para: -> outbox."""
    bc, _ = normalizar_para(para)
    dest = expandir(para)
    extra = {}
    if chat_id is not None:
        extra['chat_id'] = str(chat_id)
    if message_id is not None:
        extra['message_id'] = message_id
    carta = escribir_carta(texto, remitente, dest or para, extra=extra)
    if 'telegram' in dest:
        entregar_telegram('[%s] %s' % (remitente, texto))
        consumir(carta['id'], 'telegram')
    muses = [t for t in dest if t != 'telegram']
    res = wake_tag(muses, {t: [carta['id']] for t in muses}) if timbrar else {}
    if bc and not muses:
        acta('Broadcast sin vivos: carta %s de %s queda en bandeja.' % (carta['id'], remitente))
    return carta, res


def main(argv=None):
    p = argparse.ArgumentParser(description='Bus dirigido multi-Muse')
    sub = p.add_subparsers(dest='cmd')
    e = sub.add_parser('enviar')
    e.add_argument('--de', required=True)
    e.add_argument('--para', required=True, nargs='+')
    e.add_argument('--texto', required=True)
    e.add_argument('--sin-timbre', action='store_true')
    pe = sub.add_parser('pendientes')
    pe.add_argument('--tag', required=True)
    c = sub.add_parser('consumir')
    c.add_argument('--tag', required=True)
    c.add_argument('--id', required=True)
    r = sub.add_parser('reenviar')
    r.add_argument('--id', required=True)
    r.add_argument('--de', required=True)
    r.add_argument('--a', required=True)
    sub.add_parser('barrer')
    a = sub.add_parser('amarrar')
    a.add_argument('--tag', required=True)
    a.add_argument('--titulo', default=None)
    a.add_argument('--sesion', default=None)
    s = sub.add_parser('soltar')
    s.add_argument('--tag', required=True)
    wk = sub.add_parser('wake')
    wk.add_argument('--tag', required=True)
    rc = sub.add_parser('receptor')
    rc.add_argument('--fijar', default=None)
    args = p.parse_args(argv)
    if args.cmd == 'enviar':
        para = args.para[0] if len(args.para) == 1 else args.para
        carta, res = notify_dirigido(args.texto, args.de, para, timbrar=not args.sin_timbre)
        print('[OK] carta %s para %s timbre=%s' % (carta['id'], ','.join(carta['para']) or '(telegram)', res))
    elif args.cmd == 'pendientes':
        for c in pendientes(args.tag):
            print('%s | %s -> %s | %s' % (c.get('id'), c.get('remitente'), ','.join(c.get('para') or []), (c.get('texto') or '')[:100]))
    elif args.cmd == 'consumir':
        c = consumir(args.id, args.tag)
        print('[OK] consumida' if c else '[INFO] nada que consumir (ya consumida o ajena)')
    elif args.cmd == 'reenviar':
        n = reenviar(args.id, args.de, args.a)
        print('[OK] reenviada %s' % n['id'] if n else '[INFO] carta no pendiente para %s' % args.de)
    elif args.cmd == 'barrer':
        print('[OK] vencidas: %d' % barrer())
    elif args.cmd == 'amarrar':
        d = amarrar(args.tag, args.titulo, args.sesion)
        print('[OK] %s pid=%s titulo=%s' % (d['tag'], d['pid'], d['titulo']))
    elif args.cmd == 'soltar':
        print('[OK] amarre suelto' if soltar_amarre(args.tag) else '[INFO] sin amarre')
    elif args.cmd == 'wake':
        print(wake_tag([args.tag]))
    elif args.cmd == 'receptor':
        if args.fijar:
            print('[OK] receptor_telegram=%s' % fijar_receptor(args.fijar))
        else:
            print(receptor_telegram())
    else:
        p.print_help()
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
