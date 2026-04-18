"""
admin_agent.py — Agente local Administrator VFP
Corre en el PC del cliente. Lee DBF locales y responde consultas desde Render.

Uso:
    python admin_agent.py --servidor https://tuc-tuc.onrender.com --cliente pilar
"""

import os, sys, time, json, argparse, threading
import requests
import dbf

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
    # Cargar tablas de referencia primero (pequeñas)
    rows_ter, _ = leer_tabla(ruta_bd, "TERCEROS")
    rows_tip, _ = leer_tabla(ruta_bd, "TIPO_DOC")
    rows_cta, _ = leer_tabla(ruta_bd, "CUENTA")

    terceros  = {r['COD_TER']: r['NOMBRE'] for r in rows_ter}
    tipo_docs = {r['CODIGO']: r['NOMBRE']  for r in rows_tip}
    cuentas   = {r['CODIGO']: r['NOMBRE']  for r in rows_cta}

    lapso   = str(parametros.get('lapso',   '') or '').strip()
    empresa = str(parametros.get('empresa', '') or '').strip()
    tercero = str(parametros.get('tercero', '') or '').strip()
    limite  = int(parametros.get('limite', 200))

    # Leer REG_CTAS con filtro inline — nunca carga todo en memoria
    path = os.path.join(ruta_bd, "REG_CTAS.DBF")
    t = dbf.Table(path, ignore_memos=True)
    t.open(dbf.READ_ONLY)
    resultado = []
    try:
        for r in t:
            if dbf.is_deleted(r):
                continue
            if lapso   and str(r['LAPSO']   or '').strip() != lapso:   continue
            if empresa and str(r['EMPRESA'] or '').strip() != empresa: continue
            if tercero and str(r['TERCERO'] or '').strip() != tercero: continue

            cod_ter  = str(r['TERCERO'] or '').strip()
            cod_tipo = str(r['TIPO']    or '').strip()
            cod_cta  = str(r['CUENTA']  or '').strip()

            resultado.append({
                'consecutivo': r['CONSECUTIV'],
                'cuenta':      cod_cta,
                'cuenta_nom':  cuentas.get(cod_cta, ''),
                'lapso':       r['LAPSO'],
                'fecha':       str(r['FECHAHORA'] or ''),
                'tercero':     cod_ter,
                'tercero_nom': terceros.get(cod_ter, ''),
                'tipo':        cod_tipo,
                'tipo_nom':    tipo_docs.get(cod_tipo, ''),
                'documento':   r['DOCUMENTO'],
                'debito':      float(r['TOT_DEB'] or 0),
                'credito':     float(r['TOT_CRE'] or 0),
                'detalle':     str(r['DETALLE_CT'] or '').strip(),
                'anulado':     r['ANULADO'],
            })
            if len(resultado) >= limite:
                break
    finally:
        t.close()

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
