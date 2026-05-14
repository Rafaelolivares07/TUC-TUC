"""
admin_agent.py — Agente local Administrator VFP
Corre en el PC del cliente. Lee DBF locales y responde consultas desde Render.

Uso:
    python admin_agent.py --servidor https://tuc-tuc.onrender.com --cliente pilar
"""

import os, sys, time, json, argparse, threading
import datetime, struct, mmap, socket, configparser, subprocess
import requests
import dbf
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

POLL_INTERVALO = 5   # segundos entre pings
RUTA_DBF_FILE  = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"

_en_proceso = set()
_lock = threading.Lock()


def leer_config():
    cfg = configparser.ConfigParser()
    ini = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'admin_agent.ini')
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
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return ''


def leer_ruta_bd():
    t = dbf.Table(RUTA_DBF_FILE, ignore_memos=True)
    t.open(dbf.READ_ONLY)
    ruta = None
    for r in t:
        ruta = r['RUTA'].strip()
        break
    t.close()
    if not ruta:
        raise RuntimeError("ruta.dbf vacío")
    return os.path.dirname(ruta)


def _jd_to_datetime(jd, ms):
    """Convierte timestamp VFP (Julian Day + ms) a datetime."""
    if jd == 0:
        return None
    l = jd + 68569
    n = (4 * l) // 146097
    l = l - (146097 * n + 3) // 4
    i = (4000 * (l + 1)) // 1461001
    l = l - (1461 * i) // 4 + 31
    j = (80 * l) // 2447
    day = l - (2447 * j) // 80
    l = j // 11
    month = j + 2 - 12 * l
    year = 100 * (n - 49) + i + l
    try:
        ts = ms // 1000
        return datetime.datetime(year, month, day, ts // 3600, (ts % 3600) // 60, ts % 60)
    except Exception:
        return datetime.datetime(year, month, day)


def _leer_tabla_campos_binario(path, rec_size, campos_offsets, enc='cp1252'):
    """Lee solo los campos indicados usando raw binary (mucho más rápido que dbf lib).
    campos_offsets: [(nombre, offset, len), ...]
    Retorna lista de dicts con los campos pedidos."""
    with open(path, 'rb') as f:
        f.seek(4)
        num_records = struct.unpack('<I', f.read(4))[0]
        header_size = struct.unpack('<H', f.read(2))[0]
        f.seek(header_size)
        raw = f.read(num_records * rec_size)
    actual = len(raw) // rec_size
    rows = []
    for i in range(actual):
        base = i * rec_size
        if raw[base] == 0x2A:  # deleted
            continue
        row = {}
        for nombre_c, off, ln in campos_offsets:
            row[nombre_c] = raw[base+off: base+off+ln].strip(b' \x00').decode(enc, 'replace').replace('\x00', '')
        rows.append(row)
    return rows


def leer_tabla(ruta_bd, nombre):
    path = os.path.join(ruta_bd, nombre + ".DBF")
    t = dbf.Table(path, ignore_memos=True)
    t.open(dbf.READ_ONLY)
    campos = [c.upper() for c in t.field_names]
    raw_campos = list(t.field_names)
    rows = []
    for r in t:
        if not dbf.is_deleted(r):
            rows.append({c.upper(): (r[c].strip() if isinstance(r[c], str) else r[c]) for c in raw_campos})
    t.close()
    return rows, campos


def buscar_tercero_por_nit(ruta_bd, q):
    """Busca en TERCEROS por identificacion O nombre — retorna lista de {cod_ter, nombre, nit}."""
    rows = _leer_tabla_campos_binario(
        os.path.join(ruta_bd, "TERCEROS.DBF"), 739,
        [('COD_TER', 1, 10), ('NOMBRE', 11, 50), ('NIT', 61, 15)])
    q = q.strip().lower()
    resultado = []
    for r in rows:
        if q in r['NIT'].lower() or q in r['NOMBRE'].lower():
            resultado.append({'cod_ter': r['COD_TER'], 'nombre': r['NOMBRE'], 'nit': r['NIT']})
        if len(resultado) >= 30:
            break
    return resultado


def consulta_reg_ctas(ruta_bd, parametros):
    # TERCEROS: leer COD_TER+NOMBRE+IDENTIFICACION en binario
    rows_ter = _leer_tabla_campos_binario(
        os.path.join(ruta_bd, "TERCEROS.DBF"), 739,
        [('COD_TER', 1, 10), ('NOMBRE', 11, 50), ('NIT', 61, 15)])
    terceros     = {r['COD_TER']: r['NOMBRE'] for r in rows_ter}
    terceros_nit = {r['NIT'].strip(): r['COD_TER'] for r in rows_ter}

    rows_tip, _ = leer_tabla(ruta_bd, "TIPO_DOC")
    rows_cta, _ = leer_tabla(ruta_bd, "CUENTAS")
    tipo_docs = {r['CODIGO']: r['NOMBRE'] for r in rows_tip}
    cuentas   = {r['CODIGO']: r['NOMBRE'] for r in rows_cta}

    empresa = str(parametros.get('empresa', '') or '').strip()
    nit     = str(parametros.get('nit',     '') or '').strip()
    cuenta  = str(parametros.get('cuenta',  '') or '').strip()
    limite  = int(parametros.get('limite', 200))

    # tercero puede venir como COD_TER directo o como NIT a resolver
    tercero = str(parametros.get('tercero', '') or '').strip()
    if not tercero and nit:
        cod = terceros_nit.get(nit)
        if not cod:
            for k, v in terceros_nit.items():
                if nit in k:
                    cod = v
                    break
        tercero = cod or nit

    # Rango de lapso YYYYMMDD (acepta YYYY-MM-DD, YYYYMMDD o YYYYMM)
    def _parse_lapso(s):
        s = str(s or '').strip().replace('-', '')
        if len(s) >= 8:
            return int(s[:8])
        if len(s) == 6:
            return int(s) * 100 + 1  # YYYYMM → YYYYMM01
        return None

    lapso_desde = _parse_lapso(parametros.get('lapso_desde') or parametros.get('lapso'))
    lapso_hasta = _parse_lapso(parametros.get('lapso_hasta') or parametros.get('lapso'))
    # Si hasta es inicio de mes (YYYYMM01), llevar al fin del mes
    if lapso_hasta and str(lapso_hasta).endswith('01') and not (parametros.get('lapso_hasta') or '').replace('-','').endswith('01'):
        lapso_hasta = lapso_hasta - 1 + 99  # aproximar al 99 del mes = fin seguro
    # Para la estimación de inicio usamos lapso_desde
    lapso_start_year  = str(lapso_desde)[:4].encode('ascii') if lapso_desde else None
    lapso_start_month = str(lapso_desde)[4:6].encode('ascii') if lapso_desde else None

    # Offsets fijos de REG_CTAS (calculados de field_info)
    REC_SIZE   = 345
    OFF_CONSEC = 1
    OFF_CUENTA = 11
    OFF_LAPSO  = 26   # D(8)  "YYYYMMDD"
    OFF_FECHA  = 34   # T(8)  Julian Day + ms
    OFF_TERC   = 42   # N(10)
    OFF_EMP    = 52   # C(10)
    OFF_TIPO   = 62   # C(6)
    OFF_DOC    = 68   # C(20)
    OFF_DEB    = 108  # N(10)
    OFF_CRE    = 118  # N(10)
    OFF_DET    = 244  # C(100)

    ENC = 'cp1252'
    path = os.path.join(ruta_bd, "REG_CTAS.DBF")

    with open(path, 'rb') as f:
        f.seek(4)
        num_records = struct.unpack('<I', f.read(4))[0]
        header_size = struct.unpack('<H', f.read(2))[0]

        # Estimar posición de inicio por lapso_desde
        start = 0
        if lapso_start_year:
            try:
                yr = int(lapso_start_year)
                base_yr = 2018
                rango = (2029 - base_yr) * 12
                meses = (yr - base_yr) * 12 + (int(lapso_start_month) if lapso_start_month else 6) - 3
                start = int(num_records * max(0.0, min(0.92, meses / rango)))
            except Exception:
                start = 0

        count = num_records - start
        f.seek(header_size + start * REC_SIZE)
        raw = f.read(count * REC_SIZE)

    actual = len(raw) // REC_SIZE
    resultado = []

    if HAS_NUMPY and actual > 0:
        data = np.frombuffer(raw[:actual * REC_SIZE], dtype=np.uint8).reshape(actual, REC_SIZE)

        # Máscara: no borrados
        mask = data[:, 0] != 0x2A

        # Filtro LAPSO vectorizado por rango YYYYMMDD
        if lapso_desde or lapso_hasta:
            yr = data[:, OFF_LAPSO:OFF_LAPSO+4].astype(np.int32) - 48
            mn = data[:, OFF_LAPSO+4:OFF_LAPSO+6].astype(np.int32) - 48
            dy = data[:, OFF_LAPSO+6:OFF_LAPSO+8].astype(np.int32) - 48
            lapso_int = ((yr[:,0]*1000 + yr[:,1]*100 + yr[:,2]*10 + yr[:,3]) * 100 + (mn[:,0]*10 + mn[:,1])) * 100 + (dy[:,0]*10 + dy[:,1])
            if lapso_desde:
                mask &= lapso_int >= lapso_desde
            if lapso_hasta:
                mask &= lapso_int <= lapso_hasta

        indices = np.where(mask)[0]

        def _rec(idx):
            """Parse un registro desde raw bytes."""
            b = raw[idx * REC_SIZE: (idx+1) * REC_SIZE]
            def s(o, n): return b[o:o+n].strip(b' \x00').decode(ENC, 'replace').replace('\x00', '')
            def f(o, n):
                v = b[o:o+n].strip()
                try: return float(v) if v else 0.0
                except: return 0.0
            jd = struct.unpack('<I', b[OFF_FECHA:OFF_FECHA+4])[0]
            ms = struct.unpack('<I', b[OFF_FECHA+4:OFF_FECHA+8])[0]
            dt = _jd_to_datetime(jd, ms)
            lap = b[OFF_LAPSO:OFF_LAPSO+8]
            lap_s = f"{lap[:4].decode()}-{lap[4:6].decode()}-{lap[6:8].decode()}" if lap[:4] not in (b'    ', b'0000') else ''
            cr = b[OFF_CONSEC:OFF_CONSEC+10].strip()
            cod_ter = s(OFF_TERC, 10)
            cod_tip = s(OFF_TIPO, 6)
            cod_cta = s(OFF_CUENTA, 15)
            nit_ter = next((r['NIT'] for r in rows_ter if r['COD_TER'] == cod_ter), '')
            return {
                'consecutivo': int(cr) if cr.isdigit() else cr.decode(ENC, 'replace'),
                'cuenta':      cod_cta,
                'cuenta_nom':  cuentas.get(cod_cta, ''),
                'lapso':       lap_s,
                'fecha':       dt.isoformat() if dt else '',
                'tercero':     cod_ter,
                'tercero_nom': terceros.get(cod_ter, ''),
                'nit':         nit_ter,
                'tipo':        cod_tip,
                'tipo_nom':    tipo_docs.get(cod_tip, ''),
                'documento':   s(OFF_DOC, 20),
                'debito':      f(OFF_DEB, 10),
                'credito':     f(OFF_CRE, 10),
                'detalle':     s(OFF_DET, 100),
                'anulado':     None,
            }

        for idx in indices:
            b = raw[int(idx) * REC_SIZE: (int(idx)+1) * REC_SIZE]
            if empresa and b[OFF_EMP:OFF_EMP+10].rstrip(b' ').decode(ENC, 'replace') != empresa:
                continue
            if tercero and b[OFF_TERC:OFF_TERC+10].strip(b' ').decode(ENC, 'replace') != tercero:
                continue
            if cuenta and not b[OFF_CUENTA:OFF_CUENTA+15].rstrip(b' ').decode(ENC, 'replace').startswith(cuenta):
                continue
            resultado.append(_rec(int(idx)))
            if len(resultado) >= limite:
                break
    else:
        # Fallback sin numpy: mmap con filtro inline
        with open(path, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            for i in range(start, num_records):
                base_off = header_size + i * REC_SIZE
                if mm[base_off] == 0x2A:
                    continue
                lap = mm[base_off+OFF_LAPSO: base_off+OFF_LAPSO+8]
                if lapso_desde or lapso_hasta:
                    try:
                        li = int(lap[:8].decode('ascii'))
                        if lapso_desde and li < lapso_desde: continue
                        if lapso_hasta and li > lapso_hasta: break
                    except Exception:
                        continue
                if empresa and mm[base_off+OFF_EMP:base_off+OFF_EMP+10].rstrip(b' ').decode(ENC,'replace') != empresa:
                    continue
                if tercero and mm[base_off+OFF_TERC:base_off+OFF_TERC+10].strip(b' ').decode(ENC,'replace') != tercero:
                    continue
                if cuenta and not mm[base_off+OFF_CUENTA:base_off+OFF_CUENTA+15].rstrip(b' ').decode(ENC,'replace').startswith(cuenta):
                    continue
                lap_s = f"{lap[:4].decode()}-{lap[4:6].decode()}-{lap[6:8].decode()}"
                def _s(o,n): return mm[base_off+o:base_off+o+n].strip(b' ').decode(ENC,'replace')
                def _f(o,n):
                    v=mm[base_off+o:base_off+o+n].strip()
                    try: return float(v) if v else 0.0
                    except: return 0.0
                jd=struct.unpack('<I',mm[base_off+OFF_FECHA:base_off+OFF_FECHA+4])[0]
                ms=struct.unpack('<I',mm[base_off+OFF_FECHA+4:base_off+OFF_FECHA+8])[0]
                dt=_jd_to_datetime(jd,ms)
                cr=mm[base_off+OFF_CONSEC:base_off+OFF_CONSEC+10].strip()
                cod_ter=_s(OFF_TERC,10); cod_tip=_s(OFF_TIPO,6); cod_cta=_s(OFF_CUENTA,15)
                resultado.append({'consecutivo':int(cr) if cr.isdigit() else cr.decode(ENC,'replace'),
                    'cuenta':cod_cta,'cuenta_nom':cuentas.get(cod_cta,''),'lapso':lap_s,
                    'fecha':dt.isoformat() if dt else '','tercero':cod_ter,
                    'tercero_nom':terceros.get(cod_ter,''),'tipo':cod_tip,
                    'tipo_nom':tipo_docs.get(cod_tip,''),'documento':_s(OFF_DOC,20),
                    'debito':_f(OFF_DEB,10),'credito':_f(OFF_CRE,10),'detalle':_s(OFF_DET,100),'anulado':None})
                if len(resultado) >= limite: break
            mm.close()

    return resultado


def consulta_buscar_nit(ruta_bd, parametros):
    nit = str(parametros.get('nit', '') or '').strip()
    if not nit:
        return []
    return buscar_tercero_por_nit(ruta_bd, nit)


def consulta_buscar_cuenta(ruta_bd, parametros):
    """Busca en CUENTA por CODIGO o NOMBRE, solo TIPO='D'."""
    q = str(parametros.get('q', '') or '').strip().lower()
    if not q:
        return []
    rows, _ = leer_tabla(ruta_bd, "CUENTAS")
    resultado = []
    for r in rows:
        if str(r.get('TIPO', '') or '').strip().upper() != 'D':
            continue
        codigo = str(r.get('CODIGO', '') or '').strip()
        nombre = str(r.get('NOMBRE', '') or '').strip()
        if q in codigo.lower() or q in nombre.lower():
            resultado.append({'codigo': codigo, 'nombre': nombre})
        if len(resultado) >= 30:
            break
    return resultado


def consulta_buscar_empresas(ruta_bd, parametros):
    """Muestrea REG_CTAS y retorna códigos de empresa únicos (campo EMPRESA C10 @52)."""
    REC_SIZE = 345
    OFF_EMP  = 52
    EMP_LEN  = 10
    ENC = 'cp1252'
    path = os.path.join(ruta_bd, 'REG_CTAS.DBF')
    empresas = set()
    try:
        with open(path, 'rb') as f:
            f.seek(4)
            num = struct.unpack('<I', f.read(4))[0]
            hsz = struct.unpack('<H', f.read(2))[0]
            paso = max(1, num // 500)  # hasta 500 muestras distribuidas
            for i in range(0, num, paso):
                f.seek(hsz + i * REC_SIZE)
                b = f.read(REC_SIZE)
                if len(b) < REC_SIZE or b[0] == 0x2A:
                    continue
                emp = b[OFF_EMP:OFF_EMP+EMP_LEN].rstrip(b' ').decode(ENC, 'replace').strip()
                if emp:
                    empresas.add(emp)
    except Exception as e:
        print(f'buscar_empresas error: {e}')
    return sorted(empresas)


CONSULTAS = {
    'reg_ctas':          consulta_reg_ctas,
    'buscar_nit':        consulta_buscar_nit,
    'buscar_cuenta':     consulta_buscar_cuenta,
    'buscar_empresas':   consulta_buscar_empresas,
    'multi_tabla':       None,  # registrado abajo después de definir la función
}


# ── Lector genérico de DBF (para multi_tabla) ─────────────────────────────────

_ENC_GEN = 'cp1252'


def _leer_header_gen(path):
    """Retorna (num_records, header_size, rec_size, campos)."""
    with open(path, 'rb') as f:
        hdr = f.read(32)
        num_records = struct.unpack_from('<I', hdr, 4)[0]
        header_size = struct.unpack_from('<H', hdr, 8)[0]
        rec_size    = struct.unpack_from('<H', hdr, 10)[0]
        campos = []
        offset = 1
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


def _parse_fecha_gen(s):
    s = str(s).strip().replace('-', '')
    if len(s) == 8:
        try:
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except Exception:
            pass
    return None


def _date_to_jd_gen(d):
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153*m + 2)//5 + 365*y + y//4 - y//100 + y//400 - 32045


def _leer_valor_gen(b, campo):
    o, n, t = campo['offset'], campo['longitud'], campo['tipo']
    raw = b[o:o+n]
    if t == 'C':
        return raw.strip(b' \x00').decode(_ENC_GEN, 'replace').replace('\x00', '')
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
    return raw.strip(b' ').decode(_ENC_GEN, 'replace')


def _serializar_gen(val, tipo):
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


def _filtro_fila_gen(b, campos_map, filtros):
    for nombre_f, valor_f in filtros.items():
        c = campos_map.get(nombre_f.upper())
        if c is None:
            continue
        o, n, t = c['offset'], c['longitud'], c['tipo']
        raw = b[o:o+n]
        if t == 'C':
            val = raw.strip(b' ').decode(_ENC_GEN, 'replace').upper()
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
            dstr = raw.decode('ascii', 'replace').strip()
            dint = int(dstr) if dstr.isdigit() else 0
            def _dval(s): s = str(s).replace('-', ''); return int(s) if len(s) == 8 else 0
            if isinstance(valor_f, dict):
                if 'desde' in valor_f and dint < _dval(valor_f['desde']): return False
                if 'hasta' in valor_f and dint > _dval(valor_f['hasta']): return False
        elif t == 'T':
            jd = struct.unpack_from('<I', raw, 0)[0]
            if isinstance(valor_f, dict):
                if 'desde' in valor_f:
                    d = _parse_fecha_gen(valor_f['desde'])
                    if d and jd < _date_to_jd_gen(d): return False
                if 'hasta' in valor_f:
                    d = _parse_fecha_gen(valor_f['hasta'])
                    if d and jd > _date_to_jd_gen(d): return False
    return True


def _aplicar_filtros_numpy_gen(arr, rec_size, campos_map, filtros):
    mask = arr[:, 0] != 0x2A
    for nombre_f, valor_f in filtros.items():
        c = campos_map.get(nombre_f.upper())
        if c is None:
            continue
        o, n, t = c['offset'], c['longitud'], c['tipo']
        if t == 'C':
            val_b = str(valor_f).upper().encode(_ENC_GEN, 'replace').ljust(n)[:n]
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
                try: mask &= vals == float(valor_f)
                except Exception: pass
        elif t == 'D':
            def _dval(s): s = str(s).replace('-', ''); return int(s) if len(s) == 8 else 0
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
                    d = _parse_fecha_gen(valor_f['desde'])
                    if d: mask &= jd >= _date_to_jd_gen(d)
                if 'hasta' in valor_f:
                    d = _parse_fecha_gen(valor_f['hasta'])
                    if d: mask &= jd <= _date_to_jd_gen(d)
    return mask


def leer_tabla_filtrada_gen(ruta_bd, tabla, campos_pedidos, filtros):
    """Lee tabla.DBF, aplica filtros y retorna solo campos_pedidos."""
    path = os.path.join(ruta_bd, tabla.upper() + '.DBF')
    num_records, header_size, rec_size, campos = _leer_header_gen(path)
    campos_map = {c['nombre']: c for c in campos}
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
        arr = np.frombuffer(raw[:actual * rec_size], dtype=np.uint8).reshape(actual, rec_size)
        mask = _aplicar_filtros_numpy_gen(arr, rec_size, campos_map, filtros)
        for idx in np.where(mask)[0]:
            b = raw[int(idx)*rec_size:(int(idx)+1)*rec_size]
            row = {c['nombre']: _serializar_gen(_leer_valor_gen(b, c), c['tipo']) for c in campos_out}
            resultado.append(row)
    else:
        for i in range(actual):
            b = raw[i*rec_size:(i+1)*rec_size]
            if b[0] == 0x2A:
                continue
            if not _filtro_fila_gen(b, campos_map, filtros):
                continue
            row = {c['nombre']: _serializar_gen(_leer_valor_gen(b, c), c['tipo']) for c in campos_out}
            resultado.append(row)
    return resultado


def consulta_multi_tabla(ruta_bd, parametros):
    """Handler para tipo='multi_tabla': lee varias tablas DBF en un solo request."""
    if isinstance(parametros, str):
        try:
            parametros = json.loads(parametros)
        except Exception:
            parametros = {}
    tablas = parametros.get('tablas', [])
    resultado = {}
    for t in tablas:
        nombre  = t.get('tabla', '').upper()
        campos  = t.get('campos', [])
        filtros = t.get('filtros', {})
        try:
            resultado[nombre] = leer_tabla_filtrada_gen(ruta_bd, nombre, campos, filtros)
        except Exception as e:
            resultado[nombre] = {'error': str(e)}
    return resultado


CONSULTAS['multi_tabla'] = consulta_multi_tabla


# ── ejecutar_reporte: calcula el reporte completo localmente ──────────────────

def consulta_ejecutar_reporte(ruta_bd, parametros):
    """Importa el módulo de reporte de sar-reportes, ejecuta tablas_requeridas +
    leer + calcular localmente, y devuelve solo las filas finales."""
    reporte_id = str(parametros.get('reporte_id', '')).strip()
    filtros    = parametros.get('filtros', {})
    if not reporte_id:
        return {'error': 'reporte_id requerido'}

    sar_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sar-reportes')
    if sar_path not in sys.path:
        sys.path.insert(0, sar_path)

    try:
        from reportes import CATALOGO
    except ImportError as e:
        return {'error': f'No se pudo importar reportes: {e}'}

    if reporte_id not in CATALOGO:
        return {'error': f'Reporte desconocido: {reporte_id}'}

    modulo = CATALOGO[reporte_id]
    t0 = time.time()
    try:
        tablas_req = modulo.tablas_requeridas(filtros)
        datos = {}
        for t in tablas_req:
            nombre   = t['tabla'].upper()
            campos   = t.get('campos', [])
            filtros_t = t.get('filtros', {})
            datos[nombre] = leer_tabla_filtrada_gen(ruta_bd, nombre, campos, filtros_t)
        rows    = modulo.calcular(datos, filtros)
        elapsed = round(time.time() - t0, 1)
        return {'rows': rows, 'total': len(rows), 'elapsed': elapsed}
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()[-1000:]}


# ── consulta_estado: snapshot del estado de la máquina ───────────────────────

def consulta_estado(ruta_bd, parametros):
    """Devuelve estado de la máquina: startup items, procesos, BD, Alegra daemon."""
    items = parametros.get('items', ['todo'])
    todo  = 'todo' in items
    res   = {}

    # ── Startup items ─────────────────────────────────────────────────────────
    if todo or 'startup' in items:
        startup_path = os.path.expandvars(
            r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup')
        try:
            archivos = sorted(os.listdir(startup_path))
            res['startup'] = {'ruta': startup_path, 'archivos': archivos}
        except Exception as e:
            res['startup'] = {'error': str(e)}

    # ── Procesos conocidos ────────────────────────────────────────────────────
    if todo or 'procesos' in items:
        CONOCIDOS = [
            'admin_agent',
            'administrator.exe',
            'administrator_web',
            'AlegraDaemon',
            'alegra_daemon',
            'server.py',
            'merlin_daemon',
            'deploy_watcher',
        ]
        try:
            out = subprocess.run(
                ['tasklist', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            ).stdout.lower()
            activos = {nombre: nombre.lower() in out for nombre in CONOCIDOS}
            # También leer líneas de wmic para ver commandlines completas
            wmic = subprocess.run(
                ['wmic', 'process', 'get', 'processid,commandline'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            ).stdout
            res['procesos'] = {'activos': activos, 'detalle': wmic[:3000]}
        except Exception as e:
            res['procesos'] = {'error': str(e)}

    # ── Base de datos ─────────────────────────────────────────────────────────
    if todo or 'bd' in items:
        try:
            accesible = os.path.isdir(ruta_bd)
            muestra   = sorted([f for f in os.listdir(ruta_bd) if f.upper().endswith('.DBF')])[:8] if accesible else []
            res['bd'] = {'ruta': ruta_bd, 'accesible': accesible, 'muestra_dbf': muestra}
        except Exception as e:
            res['bd'] = {'error': str(e)}

    # ── Alegra daemon ─────────────────────────────────────────────────────────
    if todo or 'alegra_daemon' in items:
        PID_FILE   = r'C:\S.A.R\alegra_daemon.pid'
        PAUSA_FILE = r'C:\S.A.R\alegra_daemon_pausa.txt'
        LOG_FILE   = r'C:\S.A.R\alegra_vfp.log'
        info = {}
        try:
            info['en_pausa'] = os.path.exists(PAUSA_FILE)
            if os.path.exists(PID_FILE):
                pid = int(open(PID_FILE).read().strip())
                chk = subprocess.run(
                    ['wmic', 'process', 'where', f'processid={pid}', 'get', 'processid'],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                ).stdout
                info['activo'] = str(pid) in chk
                info['pid']    = pid
            else:
                info['activo'] = False
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
                    lineas = f.readlines()
                info['ultimas_lineas'] = ''.join(lineas[-30:])
                info['total_lineas']   = len(lineas)
        except Exception as e:
            info['error'] = str(e)
        res['alegra_daemon'] = info

    return res


# ── subir_archivo: lee un archivo local y lo retorna ─────────────────────────

def consulta_subir_archivo(ruta_bd, parametros):
    """Lee un archivo de la máquina cliente y lo devuelve en la respuesta.
    Parámetros:
      ruta          — ruta absoluta del archivo
      ultimas_lineas — si > 0, retorna solo las últimas N líneas (texto)
      max_bytes     — límite en bytes para binario (default 5MB)
    """
    ruta          = parametros.get('ruta', '')
    ultimas_lineas = int(parametros.get('ultimas_lineas', 0))
    max_bytes     = int(parametros.get('max_bytes', 5 * 1024 * 1024))

    if not ruta:
        return {'error': 'ruta requerida'}
    if not os.path.isfile(ruta):
        return {'error': f'Archivo no encontrado: {ruta}'}

    try:
        stat  = os.stat(ruta)
        nombre = os.path.basename(ruta)
        size  = stat.st_size

        if ultimas_lineas > 0:
            with open(ruta, 'r', encoding='utf-8', errors='replace') as f:
                lineas = f.readlines()
            contenido = ''.join(lineas[-ultimas_lineas:])
            return {'nombre': nombre, 'bytes': size,
                    'total_lineas': len(lineas), 'contenido': contenido}
        else:
            import base64
            with open(ruta, 'rb') as f:
                data = f.read(max_bytes)
            truncado = size > max_bytes
            return {'nombre': nombre, 'bytes': size, 'truncado': truncado,
                    'contenido_b64': base64.b64encode(data).decode('ascii')}
    except Exception as e:
        return {'error': str(e)}


CONSULTAS['ejecutar_reporte'] = consulta_ejecutar_reporte
CONSULTAS['consulta_estado']  = consulta_estado
CONSULTAS['subir_archivo']    = consulta_subir_archivo


def _procesar_consulta(base, token, ruta_bd, consulta):
    """Corre en thread separado para no bloquear el ping loop."""
    cid   = consulta['id']
    tipo  = consulta['tipo']
    params = consulta.get('parametros') or {}
    print(f"Consulta #{cid}: {tipo}")

    try:
        if tipo not in CONSULTAS:
            raise ValueError(f'Tipo desconocido: {tipo}')
        resultado = CONSULTAS[tipo](ruta_bd, params)
        r = requests.post(f"{base}/api/admin-agent/respuesta",
            json={'token': token, 'consulta_id': cid, 'respuesta': resultado},
            timeout=60)
        if not r.ok:
            print(f"  -> respuesta HTTP {r.status_code}: {r.text[:500]}")
        r.raise_for_status()
        n = len(resultado) if hasattr(resultado, '__len__') else '?'
        print(f"  -> OK #{cid} ({n})")
    except Exception as e:
        try:
            requests.post(f"{base}/api/admin-agent/respuesta",
                json={'token': token, 'consulta_id': cid, 'error': str(e)},
                timeout=10)
        except Exception:
            pass
        print(f"  -> ERROR #{cid}: {e}")
    finally:
        with _lock:
            _en_proceso.discard(cid)


def _pid_es_admin_agent(pid: int) -> bool:
    """True solo si el PID existe Y su línea de comando contiene admin_agent."""
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where', f'processid={pid}', 'get', 'commandline'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return 'admin_agent' in result.stdout
    except Exception:
        return False


def _adquirir_lock(cliente_id: str) -> bool:
    """Crea un lock file con el PID actual. Retorna False si ya hay otra instancia."""
    lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             f"admin_agent_{cliente_id}.lock")
    if os.path.exists(lock_path):
        try:
            old_pid = int(open(lock_path).read().strip())
            if _pid_es_admin_agent(old_pid):
                return False  # ya corre
        except Exception:
            pass  # lock stale — sobrescribir
    open(lock_path, 'w').write(str(os.getpid()))
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--servidor', default='https://admin.tuc-tuc.co')
    parser.add_argument('--cliente',  required=True)
    args = parser.parse_args()

    base = args.servidor.rstrip('/')
    cliente_id = args.cliente

    if not _adquirir_lock(cliente_id):
        print(f"Ya hay una instancia de admin_agent corriendo para '{cliente_id}'. Saliendo.")
        sys.exit(0)

    nombre   = leer_config() or cliente_id
    ip_local = get_ip_local()

    print(f"=== Admin Agent - cliente: {cliente_id} | nombre: {nombre} | ip: {ip_local} ===")
    print(f"Servidor: {base}")

    try:
        ruta_bd = leer_ruta_bd()
        print(f"BD: {ruta_bd}")
    except Exception as e:
        print(f"ERROR leyendo ruta BD: {e}")
        sys.exit(1)

    token = None
    while not token:
        try:
            r = requests.post(f"{base}/api/admin-agent/checkin",
                              json={'cliente_id': cliente_id, 'nombre': nombre,
                                    'ip_local': ip_local, 'ruta_bd': ruta_bd}, timeout=15)
            data = r.json()
            if data.get('ok'):
                token = data['token']
                print(f"Conectado. Token: {token[:12]}...")
            else:
                print(f"ERROR checkin: {data.get('error')} - reintentando en 15s...")
                time.sleep(15)
        except Exception as e:
            print(f"ERROR conectando: {e} - reintentando en 15s...")
            time.sleep(15)

    print("Esperando consultas... (Ctrl+C para salir)\n")

    try:
        while True:
            # ping loop — sale con break para reconectar
            while True:
                try:
                    r = requests.post(f"{base}/api/admin-agent/ping",
                                      json={'token': token, 'ruta_bd': ruta_bd}, timeout=15)
                    data = r.json()
                    if not data.get('ok'):
                        print(f"Sesion perdida ({data.get('error','?')}) - reconectando en 5s...")
                        break

                    consulta = data.get('consulta')
                    if consulta:
                        cid = consulta['id']
                        with _lock:
                            ya    = cid in _en_proceso
                            puede = not ya and not _en_proceso  # serializar: 1 sola consulta a la vez
                            if puede:
                                _en_proceso.add(cid)
                        if puede:
                            t = threading.Thread(
                                target=_procesar_consulta,
                                args=(base, token, ruta_bd, consulta),
                                daemon=True
                            )
                            t.start()

                except (requests.RequestException, ValueError):
                    pass  # red inestable — reintenta en el próximo ciclo

                time.sleep(POLL_INTERVALO)

            # reconexión
            time.sleep(5)
            try:
                r = requests.post(f"{base}/api/admin-agent/checkin",
                                  json={'cliente_id': cliente_id, 'nombre': nombre,
                                        'ip_local': ip_local, 'ruta_bd': ruta_bd}, timeout=15)
                data = r.json()
                if data.get('ok'):
                    token = data['token']
                    print(f"Reconectado. Token: {token[:12]}...")
                else:
                    print(f"ERROR checkin: {data.get('error')} - reintentando en 30s...")
                    time.sleep(30)
            except Exception as e:
                print(f"ERROR reconectando: {e} - reintentando en 30s...")
                time.sleep(30)

    except KeyboardInterrupt:
        print("\nDesconectando...")
        try:
            requests.post(f"{base}/api/admin-agent/checkout",
                          json={'token': token}, timeout=10)
        except Exception:
            pass
        print("Agente detenido.")


if __name__ == '__main__':
    main()
