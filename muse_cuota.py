# -*- coding: utf-8 -*-
"""Muestra cuota Muse Code al arranque. Best-effort: nunca bloquea (exit 0)."""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BOG = ZoneInfo('America/Bogota')


def main():
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
        rw = datetime.fromtimestamp(w.get('resets_at', 0), timezone.utc).astimezone(BOG).strftime('%H:%M')
        print('  Cuota Muse [%s]: 5h %s%% usado, reset %s - semanal %s%%' % (
            tier, w.get('used_percent', '?'), rw, s.get('used_percent', '?')))
    except Exception as e:
        print('  Cuota Muse: no disponible [%s]' % type(e).__name__)
    return 0


if __name__ == '__main__':
    sys.exit(main())
