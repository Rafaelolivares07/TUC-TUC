"""
admin_agent.py — Agente local Administrator VFP
Corre en el PC del cliente. Lee DBF locales y responde consultas desde Render.

Uso:
    python admin_agent.py --servidor https://tuc-tuc.onrender.com --cliente pilar
"""

import os, sys, time, json, argparse, threading
import datetime, struct, mmap
import requests
import dbf
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

POLL_INTERVALO = 5   # segundos entre pings
RUTA_DBF_FILE  = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"

# Consultas en proceso (cid -> True) para no procesar dos veces la misma
_en_proceso = set()
_lock = threading.Lock()


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
            row[nombre_c] = raw[base+off: base+off+ln].strip(b' ').decode(enc, 'replace')
        rows.append(row)
    return rows


def leer_tabla(ruta_bd, nombre):
    path = os.path.join(ruta_bd, nombre + ".DBF")
    t = dbf.Table(path, ignore_memos=True)
    t.open(dbf.READ_ONLY)
    campos = list(t.field_names)
    rows = []
    for r in t:
        if not dbf.is_deleted(r):
            rows.append({c: (r[c].strip() if isinstance(r[c], str) else r[c]) for c in campos})
    t.close()
    return rows, campos


def consulta_reg_ctas(ruta_bd, parametros):
    # TERCEROS: leer solo COD_TER+NOMBRE en binario (evita parsear campos de 254 chars)
    # rec_size=739, COD_TER offset=1 len=10, NOMBRE offset=11 len=50
    rows_ter = _leer_tabla_campos_binario(
        os.path.join(ruta_bd, "TERCEROS.DBF"), 739,
        [('COD_TER', 1, 10), ('NOMBRE', 11, 50)])
    terceros = {r['COD_TER']: r['NOMBRE'] for r in rows_ter}

    rows_tip, _ = leer_tabla(ruta_bd, "TIPO_DOC")
    rows_cta, _ = leer_tabla(ruta_bd, "CUENTA")
    tipo_docs = {r['CODIGO']: r['NOMBRE']  for r in rows_tip}
    cuentas   = {r['CODIGO']: r['NOMBRE']  for r in rows_cta}

    empresa = str(parametros.get('empresa', '') or '').strip()
    tercero = str(parametros.get('tercero', '') or '').strip()
    limite  = int(parametros.get('limite', 200))

    lapso_raw   = str(parametros.get('lapso', '') or '').strip().replace('-', '')
    lapso_year  = lapso_raw[:4].encode('ascii') if len(lapso_raw) >= 4 else None
    lapso_month = lapso_raw[4:6].zfill(2).encode('ascii') if len(lapso_raw) >= 6 else None

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

        # Estimar posición de inicio
        start = 0
        if lapso_year:
            try:
                yr = int(lapso_year)
                base_yr = 2018
                rango = (2029 - base_yr) * 12
                meses = (yr - base_yr) * 12 + (int(lapso_month) if lapso_month else 6) - 3
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

        # Filtro LAPSO vectorizado
        if lapso_year:
            yr_arr = np.frombuffer(lapso_year, dtype=np.uint8)
            mask &= np.all(data[:, OFF_LAPSO:OFF_LAPSO+4] == yr_arr, axis=1)
            if lapso_month:
                mn_arr = np.frombuffer(lapso_month, dtype=np.uint8)
                mask &= np.all(data[:, OFF_LAPSO+4:OFF_LAPSO+6] == mn_arr, axis=1)

        indices = np.where(mask)[0]

        def _rec(idx):
            """Parse un registro desde raw bytes."""
            b = raw[idx * REC_SIZE: (idx+1) * REC_SIZE]
            def s(o, n): return b[o:o+n].strip(b' ').decode(ENC, 'replace')
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
            return {
                'consecutivo': int(cr) if cr.isdigit() else cr.decode(ENC, 'replace'),
                'cuenta':      cod_cta,
                'cuenta_nom':  cuentas.get(cod_cta, ''),
                'lapso':       lap_s,
                'fecha':       dt.isoformat() if dt else '',
                'tercero':     cod_ter,
                'tercero_nom': terceros.get(cod_ter, ''),
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
                if lapso_year:
                    yr4 = lap[:4]
                    if yr4 > lapso_year: break
                    if yr4 < lapso_year: continue
                    if lapso_month:
                        mn2 = lap[4:6]
                        if mn2 > lapso_month: break
                        if mn2 < lapso_month: continue
                if empresa and mm[base_off+OFF_EMP:base_off+OFF_EMP+10].rstrip(b' ').decode(ENC,'replace') != empresa:
                    continue
                if tercero and mm[base_off+OFF_TERC:base_off+OFF_TERC+10].strip(b' ').decode(ENC,'replace') != tercero:
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


CONSULTAS = {
    'reg_ctas': consulta_reg_ctas,
}


def _procesar_consulta(base, token, ruta_bd, consulta):
    """Corre en thread separado para no bloquear el ping loop."""
    cid   = consulta['id']
    tipo  = consulta['tipo']
    params = consulta.get('parametros') or {}
    print(f"Consulta #{cid}: {tipo} {params}")

    try:
        if tipo not in CONSULTAS:
            raise ValueError(f'Tipo desconocido: {tipo}')
        resultado = CONSULTAS[tipo](ruta_bd, params)
        requests.post(f"{base}/api/admin-agent/respuesta",
            json={'token': token, 'consulta_id': cid, 'respuesta': resultado},
            timeout=30)
        print(f"  → {len(resultado)} registros enviados")
    except Exception as e:
        try:
            requests.post(f"{base}/api/admin-agent/respuesta",
                json={'token': token, 'consulta_id': cid, 'error': str(e)},
                timeout=10)
        except Exception:
            pass
        print(f"  → ERROR: {e}")
    finally:
        with _lock:
            _en_proceso.discard(cid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--servidor', default='https://tuc-tuc.onrender.com')
    parser.add_argument('--cliente',  required=True)
    args = parser.parse_args()

    base = args.servidor.rstrip('/')
    cliente_id = args.cliente

    print(f"=== Admin Agent — cliente: {cliente_id} ===")
    print(f"Servidor: {base}")

    try:
        ruta_bd = leer_ruta_bd()
        print(f"BD: {ruta_bd}")
    except Exception as e:
        print(f"ERROR leyendo ruta BD: {e}")
        sys.exit(1)

    try:
        r = requests.post(f"{base}/api/admin-agent/checkin",
                          json={'cliente_id': cliente_id}, timeout=15)
        data = r.json()
        if not data.get('ok'):
            print(f"ERROR checkin: {data.get('error')}")
            sys.exit(1)
        token = data['token']
        print(f"Conectado. Token: {token[:12]}...")
    except Exception as e:
        print(f"ERROR conectando a Render: {e}")
        sys.exit(1)

    print("Esperando consultas... (Ctrl+C para salir)\n")

    try:
        while True:
            try:
                r = requests.post(f"{base}/api/admin-agent/ping",
                                  json={'token': token}, timeout=15)
                data = r.json()
                if not data.get('ok'):
                    print("Sesión inválida — reconectando...")
                    break

                consulta = data.get('consulta')
                if consulta:
                    cid = consulta['id']
                    with _lock:
                        ya = cid in _en_proceso
                        if not ya:
                            _en_proceso.add(cid)
                    if not ya:
                        t = threading.Thread(
                            target=_procesar_consulta,
                            args=(base, token, ruta_bd, consulta),
                            daemon=True
                        )
                        t.start()

            except requests.RequestException as e:
                print(f"Red: {e}")

            time.sleep(POLL_INTERVALO)

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
