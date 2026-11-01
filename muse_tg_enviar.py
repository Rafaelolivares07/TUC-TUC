# -*- coding: utf-8 -*-
"""muse_tg_enviar: manda texto y/o audio a Rafa por Telegram.
Uso:  muse_tg_enviar.py "texto" [--voz] [--solo-voz]
- Credenciales desde BD (muse_tg_listener.read_token), nunca en disco.
- Audio: muse_voz/habla_edge.py (Salome) + ffmpeg ogg-opus + sendVoice (nota de voz, sin playlist).
Imprime message_id(s). Exit 1 si falla.
"""
import json
import os
import shutil
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


def _mp3_a_ogg(mp3path, oggpath):
    """Convierte mp3 a ogg-opus (formato nota de voz). True si queda en disco."""
    ff = shutil.which('ffmpeg')
    if not ff:
        print('sin ffmpeg en PATH')
        return False
    p = subprocess.run([ff, '-y', '-loglevel', 'error', '-i', mp3path,
                        '-c:a', 'libopus', '-b:a', '64k', oggpath],
                       capture_output=True, text=True, timeout=120)
    if p.returncode != 0 or not os.path.exists(oggpath):
        print('ffmpeg fallo:', (p.stderr or '')[:200])
        return False
    return True


def _multipart_voice(cid, audio):
    """Cuerpo multipart para sendVoice. Retorna (body, boundary)."""
    b = uuid.uuid4().hex.encode()
    parts = [b'--' + b,
             b'Content-Disposition: form-data; name="chat_id"',
             b'', str(cid).encode(),
             b'--' + b,
             b'Content-Disposition: form-data; name="voice"; filename="muse.ogg"',
             b'Content-Type: audio/ogg', b'', audio,
             b'--' + b + b'--', b'']
    return b'\r\n'.join(parts), b.decode()


def send_voice(base, cid, oggpath):
    with open(oggpath, 'rb') as f:
        audio = f.read()
    body, boundary = _multipart_voice(cid, audio)
    req = urllib.request.Request(base + '/sendVoice', data=body,
                                 headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
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
        ogg = os.path.join(tmp, 'muse_tg_audio.ogg')
        with open(txt, 'w', encoding='utf-8') as f:
            f.write(text)
        habla = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'muse_voz', 'habla_edge.py')
        p = subprocess.run([sys.executable, habla, txt, mp3],
                           capture_output=True, text=True, timeout=120)
        if p.returncode != 0 or not os.path.exists(mp3):
            print('tts fallo:', (p.stderr or p.stdout or '')[:200])
            return 1
        if not _mp3_a_ogg(mp3, ogg):
            return 1
        r = send_voice(base, cid, ogg)
        print('audio_ok:', r.get('ok'), '| id:', r.get('result', {}).get('message_id'))
        for f in (txt, mp3, ogg):
            try:
                os.unlink(f)
            except OSError:
                pass
        if not r.get('ok'):
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
