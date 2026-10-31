"""CLI Muse -> produccion TUC TUC (login propio + request API).

Uso:
  C:\\Tools\\Python313\\python.exe Documents\\TucTucV2\\muse_prod.py "/api/version"
  C:\\Tools\\Python313\\python.exe Documents\\TucTucV2\\muse_prod.py "/api/inventario/59/productos/buscar?q=pan"
  C:\\Tools\\Python313\\python.exe Documents\\TucTucV2\\muse_prod.py "/ruta" POST '{"a":1}'
Credenciales: C:\\Tools\\muse-prod-credentials
  (MUSE_PROD_USUARIO / MUSE_PROD_PASSWORD / MUSE_PROD_URL).
Solo stdlib. Una sesion por invocacion (login + 1 request).
"""
import http.cookiejar
import json
import sys
import urllib.parse
import urllib.request


def _creds(path=r'C:\Tools\muse-prod-credentials'):
    d = {}
    for ln in open(path, encoding='utf-8-sig'):
        ln = ln.strip()
        if ln and not ln.startswith('#') and '=' in ln:
            k, v = ln.split('=', 1)
            d[k.strip()] = v.strip()
    return d


def sesion():
    c = _creds()
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = urllib.parse.urlencode(
        {'usuario': c['MUSE_PROD_USUARIO'], 'password': c['MUSE_PROD_PASSWORD']}).encode()
    r = op.open(urllib.request.Request(
        c['MUSE_PROD_URL'].rstrip('/') + '/entrar', data=data), timeout=30)
    body = r.read().decode('utf-8', 'replace')
    if 'incorrectos' in body or 'todos los campos' in body:
        raise SystemExit('login prod fallo (usuario/clave)')
    return op, c['MUSE_PROD_URL'].rstrip('/')


def main():
    if len(sys.argv) < 2:
        raise SystemExit('uso: muse_prod.py <ruta-api> [METODO] [json-body]')
    op, base = sesion()
    ruta = sys.argv[1]
    metodo = (sys.argv[2] if len(sys.argv) > 2 else 'GET').upper()
    body = sys.argv[3].encode() if len(sys.argv) > 3 else None
    req = urllib.request.Request(base + ruta, data=body, method=metodo)
    if body:
        req.add_header('Content-Type', 'application/json')
    r = op.open(req, timeout=60)
    out = r.read().decode('utf-8', 'replace')
    try:
        print(json.dumps(json.loads(out), ensure_ascii=False, indent=1)[:6000])
    except Exception:
        print(out[:6000])


if __name__ == '__main__':
    main()
