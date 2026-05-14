"""
agente.py — Agente local SAR / reportes multi-origen
Corre en el PC del cliente. Lee DBF locales y responde consultas del servidor.
Protocolo idéntico al admin_agent original (checkin / ping / respuesta).

Única consulta soportada: tipo="multi_tabla"
  parametros = {
    "tablas": [
      {"tabla": "PRODUCTOS", "campos": ["CODIGO","NOMBRE"], "filtros": {}},
      {"tabla": "PROD_FACT1", "campos": ["COD_PRO","FECHAHORA","CANTIDAD"],
       "filtros": {"EMPRESA": "MG", "FECHAHORA": {"desde": "2026-01-01", "hasta": "2026-05-12"}}},
      ...
    ]
  }
  respuesta = {"PRODUCTOS": [...], "PROD_FACT1": [...], ...}

El agente no sabe qué reporte se construye con los datos — eso lo hace el servidor.
"""

import os, sys, struct, time, json, threading, argparse, socket, configparser, datetime
import requests

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

POLL_INTERVALO = 5
RUTA_DBF_FILE  = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"
ENC = 'cp1252'

_en_proceso = set()
_lock = threading.Lock()


# ── Lectura de header DBF ─────────────────────────────────────────────────────

def leer_header(path):
    """Retorna (num_records, header_size, rec_size, campos).
    campos: list de {nombre, tipo, offset, longitud}
    offset calculado acumulando longitudes (byte 0 = flag borrado).
    """
    with open(path, 'rb') as f:
        hdr = f.read(32)
        num_records = struct.unpack_from('<I', hdr, 4)[0]
        header_size = struct.unpack_from('<H', hdr, 8)[0]
        rec_size    = struct.unpack_from('<H', hdr, 10)[0]
        campos = []
        offset = 1  # byte 0 es flag de borrado
        while True:
            fd = f.read(32)
            if not fd or fd[0] == 0x0D:
                break
            nombre   = fd[0:11].rstrip(b'\x00').decode('ascii', 'replace').upper()
            tipo     = chr(fd[11])
            longitud = fd[16]
            campos.append({'nombre': nombre, 'tipo': tipo, 'offset': offset, 'longitud': longitud})
            offset += longitud
    return num_records, header_size, rec_size, campos


# ── Conversiones ──────────────────────────────────────────────────────────────

def _date_to_jd(d):
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153*m + 2)//5 + 365*y + y//4 - y//100 + y//400 - 32045


def _parse_fecha(s):
    s = str(s).strip().replace('-', '')
    if len(s) == 8:
        return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


def _leer_valor(b, campo):
    """Lee el valor de un campo de un registro binario."""
    o, n, t = campo['offset'], campo['longitud'], campo['tipo']
    raw = b[o:o+n]
    if t == 'C':
        return raw.strip(b' ').decode(ENC, 'replace')
    if t == 'N':
        v = raw.strip()
        try: return float(v) if v else 0.0
        except: return 0.0
    if t == 'D':
        return raw.decode('ascii', 'replace').strip()
    if t == 'T':
        jd = struct.unpack_from('<I', raw, 0)[0]
        ms = struct.unpack_from('<I', raw, 4)[0]
        return (jd, ms)
    if t == 'L':
        return chr(raw[0]) if raw else 'F'
    return raw.strip(b' ').decode(ENC, 'replace')


# ── Construcción de máscara de filtros ────────────────────────────────────────

def _aplicar_filtros_numpy(arr, rec_size, campos_map, filtros):
    """Retorna array booleano de máscara. Solo tipos C, N, D, T."""
    mask = arr[:, 0] != 0x2A
    for nombre_f, valor_f in filtros.items():
        c = campos_map.get(nombre_f.upper())
        if c is None:
            continue
        o, n, t = c['offset'], c['longitud'], c['tipo']
        if t == 'C':
            val_b = str(valor_f).upper().encode(ENC).ljust(n)[:n]
            mask &= np.all(arr[:, o:o+n] == np.frombuffer(val_b, dtype=np.uint8), axis=1)
        elif t == 'N':
            raw_n = arr[:, o:o+n]
            vals = np.zeros(len(arr), dtype=np.float64)
            for i in range(len(arr)):
                v = raw_n[i].tobytes().strip()
                try: vals[i] = float(v) if v else 0.0
                except: pass
            if isinstance(valor_f, dict):
                if 'min' in valor_f: mask &= vals >= valor_f['min']
                if 'max' in valor_f: mask &= vals <= valor_f['max']
            else:
                mask &= vals == float(valor_f)
        elif t == 'D':
            def _dval(s):
                s = str(s).replace('-','')
                return int(s) if len(s) == 8 else 0
            yr = (arr[:,o  ]-48)*1000 + (arr[:,o+1]-48)*100 + (arr[:,o+2]-48)*10 + (arr[:,o+3]-48)
            mn = (arr[:,o+4]-48)*10   + (arr[:,o+5]-48)
            dy = (arr[:,o+6]-48)*10   + (arr[:,o+7]-48)
            dint = yr.astype(np.int64)*10000 + mn.astype(np.int64)*100 + dy.astype(np.int64)
            if isinstance(valor_f, dict):
                if 'desde' in valor_f: mask &= dint >= _dval(valor_f['desde'])
                if 'hasta' in valor_f: mask &= dint <= _dval(valor_f['hasta'])
        elif t == 'T':
            jd = (arr[:,o  ].astype(np.int64) | (arr[:,o+1].astype(np.int64)<<8) |
                  (arr[:,o+2].astype(np.int64)<<16) | (arr[:,o+3].astype(np.int64)<<24))
            if isinstance(valor_f, dict):
                if 'desde' in valor_f:
                    d = _parse_fecha(valor_f['desde'])
                    if d: mask &= jd >= _date_to_jd(d)
                if 'hasta' in valor_f:
                    d = _parse_fecha(valor_f['hasta'])
                    if d: mask &= jd <= _date_to_jd(d)
    return mask


def _filtro_fila(b, campos_map, filtros):
    """Filtro escalar sin numpy."""
    for nombre_f, valor_f in filtros.items():
        c = campos_map.get(nombre_f.upper())
        if c is None:
            continue
        o, n, t = c['offset'], c['longitud'], c['tipo']
        raw = b[o:o+n]
        if t == 'C':
            val = raw.strip(b' ').decode(ENC, 'replace').upper()
            if val != str(valor_f).upper().strip():
                return False
        elif t == 'N':
            try: fval = float(raw.strip()) if raw.strip() else 0.0
            except: fval = 0.0
            if isinstance(valor_f, dict):
                if 'min' in valor_f and fval < valor_f['min']: return False
                if 'max' in valor_f and fval > valor_f['max']: return False
            else:
                if fval != float(valor_f): return False
        elif t == 'D':
            dstr = raw.decode('ascii','replace').strip()
            dint = int(dstr) if dstr.isdigit() else 0
            def _dval(s): s=str(s).replace('-',''); return int(s) if len(s)==8 else 0
            if isinstance(valor_f, dict):
                if 'desde' in valor_f and dint < _dval(valor_f['desde']): return False
                if 'hasta' in valor_f and dint > _dval(valor_f['hasta']): return False
        elif t == 'T':
            jd = struct.unpack_from('<I', raw, 0)[0]
            if isinstance(valor_f, dict):
                if 'desde' in valor_f:
                    d = _parse_fecha(valor_f['desde'])
                    if d and jd < _date_to_jd(d): return False
                if 'hasta' in valor_f:
                    d = _parse_fecha(valor_f['hasta'])
                    if d and jd > _date_to_jd(d): return False
    return True


# ── Serialización de valores para JSON ───────────────────────────────────────

def _serializar(val, tipo):
    if tipo == 'T':
        jd, ms = val
        if jd == 0:
            return None
        try:
            l = jd + 68569
            nn = (4 * l) // 146097
            l = l - (146097 * nn + 3) // 4
            ii = (4000 * (l + 1)) // 1461001
            l = l - (1461 * ii) // 4 + 31
            j = (80 * l) // 2447
            day = l - (2447 * j) // 80
            l = j // 11
            month = j + 2 - 12 * l
            year = 100 * (nn - 49) + ii + l
            ts = ms // 1000
            return datetime.datetime(year, month, day, ts//3600, (ts%3600)//60, ts%60).isoformat()
        except Exception:
            return None
    return val


# ── Lector principal ──────────────────────────────────────────────────────────

def leer_tabla_filtrada(ruta_bd, tabla, campos_pedidos, filtros):
    """Lee tabla.DBF, aplica filtros y retorna solo campos_pedidos como lista de dicts."""
    path = os.path.join(ruta_bd, tabla.upper() + '.DBF')
    num_records, header_size, rec_size, campos = leer_header(path)
    campos_map = {c['nombre']: c for c in campos}

    # Si campos_pedidos vacío → todos
    if not campos_pedidos:
        campos_pedidos = [c['nombre'] for c in campos]
    campos_pedidos = [c.upper() for c in campos_pedidos]
    campos_out = [campos_map[n] for n in campos_pedidos if n in campos_map]

    with open(path, 'rb') as f:
        f.seek(header_size)
        raw = f.read(num_records * rec_size)

    actual = len(raw) // rec_size
    resultado = []

    if HAS_NUMPY and actual > 0:
        arr = (np.frombuffer(raw[:actual * rec_size], dtype=np.uint8)
               .reshape(actual, rec_size))
        mask = _aplicar_filtros_numpy(arr, rec_size, campos_map, filtros)
        indices = np.where(mask)[0]
        for idx in indices:
            b = raw[int(idx)*rec_size:(int(idx)+1)*rec_size]
            row = {}
            for c in campos_out:
                v = _leer_valor(b, c)
                row[c['nombre']] = _serializar(v, c['tipo'])
            resultado.append(row)
    else:
        for i in range(actual):
            b = raw[i*rec_size:(i+1)*rec_size]
            if b[0] == 0x2A:
                continue
            if not _filtro_fila(b, campos_map, filtros):
                continue
            row = {}
            for c in campos_out:
                v = _leer_valor(b, c)
                row[c['nombre']] = _serializar(v, c['tipo'])
            resultado.append(row)

    return resultado


# ── Procesador de consultas ───────────────────────────────────────────────────

def procesar_multi_tabla(ruta_bd, parametros):
    tablas = parametros.get('tablas', [])
    resultado = {}
    for t in tablas:
        nombre  = t.get('tabla', '').upper()
        campos  = t.get('campos', [])
        filtros = t.get('filtros', {})
        try:
            resultado[nombre] = leer_tabla_filtrada(ruta_bd, nombre, campos, filtros)
        except Exception as e:
            resultado[nombre] = {'error': str(e)}
    return resultado


CONSULTAS = {
    'multi_tabla': procesar_multi_tabla,
}


# ── Red ───────────────────────────────────────────────────────────────────────

def leer_config():
    cfg = configparser.ConfigParser()
    ini = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agente.ini')
    cfg.read(ini, encoding='utf-8')
    return cfg.get('agent', 'nombre', fallback='').strip()


def get_ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ''


def leer_ruta_bd():
    import dbf
    t = dbf.Table(RUTA_DBF_FILE, ignore_memos=True)
    t.open(dbf.READ_ONLY)
    ruta = None
    for r in t:
        ruta = r['RUTA'].strip()
        break
    t.close()
    if not ruta:
        raise RuntimeError('ruta.dbf vacío')
    return os.path.dirname(ruta)


def _procesar_consulta(base, token, ruta_bd, consulta):
    cid   = consulta['id']
    tipo  = consulta['tipo']
    params = consulta.get('parametros') or {}
    print(f'Consulta #{cid}: {tipo}')
    try:
        if tipo not in CONSULTAS:
            raise ValueError(f'Tipo desconocido: {tipo}')
        resultado = CONSULTAS[tipo](ruta_bd, params)
        requests.post(f'{base}/api/admin-agent/respuesta',
            json={'token': token, 'consulta_id': cid, 'respuesta': resultado},
            timeout=60)
        n = sum(len(v) for v in resultado.values()) if isinstance(resultado, dict) else len(resultado)
        print(f'  → {n} registros enviados')
    except Exception as e:
        try:
            requests.post(f'{base}/api/admin-agent/respuesta',
                json={'token': token, 'consulta_id': cid, 'error': str(e)},
                timeout=10)
        except Exception:
            pass
        print(f'  → ERROR: {e}')
    finally:
        with _lock:
            _en_proceso.discard(cid)


def _pid_existe(pid):
    import ctypes
    h = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid)
    if not h: return False
    ctypes.windll.kernel32.CloseHandle(h)
    return True


def _adquirir_lock(cliente_id):
    lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             f'agente_{cliente_id}.lock')
    if os.path.exists(lock_path):
        try:
            old_pid = int(open(lock_path).read().strip())
            if _pid_existe(old_pid):
                return False
        except Exception:
            pass
    open(lock_path, 'w').write(str(os.getpid()))
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--servidor', default='https://admin.tuc-tuc.co')
    parser.add_argument('--cliente',  required=True)
    args = parser.parse_args()

    base       = args.servidor.rstrip('/')
    cliente_id = args.cliente

    if not _adquirir_lock(cliente_id):
        print(f'Ya hay una instancia corriendo para {cliente_id!r}. Saliendo.')
        sys.exit(0)

    nombre   = leer_config() or cliente_id
    ip_local = get_ip_local()
    print(f'=== Agente SAR — cliente: {cliente_id} | ip: {ip_local} ===')

    try:
        ruta_bd = leer_ruta_bd()
        print(f'BD: {ruta_bd}')
    except Exception as e:
        print(f'ERROR leyendo ruta BD: {e}')
        sys.exit(1)

    token = None
    while not token:
        try:
            r = requests.post(f'{base}/api/admin-agent/checkin',
                              json={'cliente_id': cliente_id, 'nombre': nombre,
                                    'ip_local': ip_local, 'ruta_bd': ruta_bd}, timeout=15)
            data = r.json()
            if data.get('ok'):
                token = data['token']
                print(f'Conectado. Token: {token[:12]}...')
            else:
                print(f'ERROR checkin: {data.get("error")} - reintentando en 15s...')
                time.sleep(15)
        except Exception as e:
            print(f'ERROR conectando: {e} - reintentando en 15s...')
            time.sleep(15)

    print('Esperando consultas... (Ctrl+C para salir)\n')
    try:
        while True:
            while True:
                try:
                    r = requests.post(f'{base}/api/admin-agent/ping',
                                      json={'token': token, 'ruta_bd': ruta_bd}, timeout=15)
                    data = r.json()
                    if not data.get('ok'):
                        print(f'Sesión perdida — reconectando...')
                        break
                    consulta = data.get('consulta')
                    if consulta:
                        cid = consulta['id']
                        with _lock:
                            puede = cid not in _en_proceso and not _en_proceso
                            if puede:
                                _en_proceso.add(cid)
                        if puede:
                            threading.Thread(target=_procesar_consulta,
                                             args=(base, token, ruta_bd, consulta),
                                             daemon=True).start()
                except (requests.RequestException, ValueError):
                    pass
                time.sleep(POLL_INTERVALO)
            time.sleep(5)
            try:
                r = requests.post(f'{base}/api/admin-agent/checkin',
                                  json={'cliente_id': cliente_id, 'nombre': nombre,
                                        'ip_local': ip_local, 'ruta_bd': ruta_bd}, timeout=15)
                data = r.json()
                if data.get('ok'):
                    token = data['token']
                    print(f'Reconectado.')
                else:
                    time.sleep(30)
            except Exception:
                time.sleep(30)
    except KeyboardInterrupt:
        print('\nDesconectando...')
        try:
            requests.post(f'{base}/api/admin-agent/checkout',
                          json={'token': token}, timeout=10)
        except Exception:
            pass


if __name__ == '__main__':
    main()
