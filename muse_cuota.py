# -*- coding: utf-8 -*-
"""Cuota Muse Code para el launcher. Imprime linea completa y deja tag corto
en %TEMP%/muse_cuota_tag.txt para concatenar al titulo WT. Best-effort exit 0."""
import json
import os
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BOG = ZoneInfo('America/Bogota')
DIAS = ['lun', 'mar', 'mie', 'jue', 'vie', 'sab', 'dom']
TAG = os.path.join(tempfile.gettempdir(), 'muse_cuota_tag.txt')


def main():
    try:
        os.unlink(TAG)
    except OSError:
        pass
    try:
        a = json.load(open(r'C:\Users\RAFAEL OLIVARES\.config\muse\auth.json'))
        tok = a['providers']['meta']['access_token']
    except Exception:
        print('  Cuota Muse: sin login [muse login]')
        return 0
    try:
        req = urllib.request.Request(
            'https://api.meta.ai/muse-code/key', data=json.dumps({}).encode(),
            headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'},
            method='POST')
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        u = d.get('subs_usage') or {}
        w = u.get('window') or {}
        s = u.get('weekly') or {}
        tier = d.get('subs_tier_name') or '?'
        uw = int(w.get('used_percent', 0) or 0)
        us = int(s.get('used_percent', 0) or 0)
        rw = datetime.fromtimestamp(w.get('resets_at', 0), timezone.utc).astimezone(BOG)
        rs = datetime.fromtimestamp(s.get('resets_at', 0), timezone.utc).astimezone(BOG)
        corte = '%s %s' % (DIAS[rs.weekday()], rs.strftime('%d/%m'))
        print('  Cuota Muse [%s]: 5h %d%% usado / %d%% libre, reset %s - semanal %d%% usado / %d%% libre, corte %s' % (
            tier, uw, 100 - uw, rw.strftime('%H:%M'), us, 100 - us, corte))
        open(TAG, 'w').write('%d%% %s' % (uw, rw.strftime('%H:%M')))
    except Exception as e:
        print('  Cuota Muse: no disponible [%s]' % type(e).__name__)
    return 0


if __name__ == '__main__':
    sys.exit(main())
