# -*- coding: utf-8 -*-
"""muse_tg_enviar: manda texto y/o audio a Rafa por Telegram.
Uso:  muse_tg_enviar.py "texto" [--voz] [--solo-voz]
- Credenciales desde BD (muse_tg_listener.read_token), nunca en disco.
- Audio: muse_voz/habla_edge.py (Salome) + sendAudio mp3.
Imprime message_id(s). Exit 1 si falla.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import muse_tg_listener as tg


def send_text(base, cid, text):
    data = urllib.parse.urlencode({'chat_id': cid, 'text': text}).encode()
    req = urllib.request.Request(base + '/sendMessage', data=data)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def send_audio(base, cid, mp3path, title):
    b = uuid.uuid4().hex.encode()
    with open(mp3path, 'rb') as f:
        audio = f.read()
    parts = []
    for k, v in (('chat_id', cid), ('title', title)):
        parts += [b'--' + b,
                  ('Content-Disposition: form-data; name="%s"' % k).encode(),
                  b'', str(v).encode()]
    parts += [b'--' + b,
              b'Content-Disposition: form-data; name="audio"; filename="muse.mp3"',
              b'Content-Type: audio/mpeg', b'', audio,
              b'--' + b + b'--', b'']
    body = b'\r\n'.join(parts)
    req = urllib.request.Request(base + '/sendAudio', data=body,
                                 headers={'Content-Type': 'multipart/form-data; boundary=' + b.decode()})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def main(argv):
    solo_voz = '--solo-voz' in argv
    con_voz = solo_voz or '--voz' in argv
    text = ' '.join(a for a in argv[1:] if not a.startswith('--')).strip()
    if not text:
        print('uso: muse_tg_enviar.py "texto" [--voz] [--solo-voz]')
        return 1
    creds = tg.read_token()
    if creds is None:
        print('sin credenciales (tunel/BD caido)')
        return 1
    token, cid = creds
    base = 'https://api.telegram.org/bot' + token
    if not solo_voz:
        r = send_text(base, cid, text)
        print('texto_ok:', r.get('ok'), '| id:', r.get('result', {}).get('message_id'))
        if not r.get('ok'):
            return 1
    if con_voz:
        tmp = tempfile.gettempdir()
        txt = os.path.join(tmp, 'muse_tg_txt.txt')
        mp3 = os.path.join(tmp, 'muse_tg_audio.mp3')
        with open(txt, 'w', encoding='utf-8') as f:
            f.write(text)
        habla = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'muse_voz', 'habla_edge.py')
        p = subprocess.run([sys.executable, habla, txt, mp3],
                           capture_output=True, text=True, timeout=120)
        if p.returncode != 0 or not os.path.exists(mp3):
            print('tts fallo:', (p.stderr or p.stdout or '')[:200])
            return 1
        r = send_audio(base, cid, mp3, text[:60])
        print('audio_ok:', r.get('ok'), '| id:', r.get('result', {}).get('message_id'))
        for f in (txt, mp3):
            try:
                os.unlink(f)
            except OSError:
                pass
        if not r.get('ok'):
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
