"""
admin_agent.py — Agente local Administrator VFP
Corre en el PC del cliente. Lee DBF locales y responde consultas desde Render.

Uso:
    python admin_agent.py --servidor https://tuc-tuc.onrender.com --cliente pilar
"""

import os, sys, time, json, argparse
import requests
import dbf

POLL_INTERVALO = 5   # segundos entre pings cuando hay sesión activa
RUTA_DBF_FILE  = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"


def leer_ruta_bd():
    """Lee la ruta activa de BD desde ruta.dbf de Administrator."""
    t = dbf.Table(RUTA_DBF_FILE, ignore_memos=True)
    t.open(dbf.READ_ONLY)
    ruta = None
    for r in t:
        ruta = r['RUTA'].strip()
        break
    t.close()
    if not ruta:
        raise RuntimeError("ruta.dbf vacío")
    # Convertir ruta del DBC a carpeta
    return os.path.dirname(ruta)


def leer_tabla(ruta_bd, nombre):
    """Lee un DBF y retorna lista de dicts."""
    path = os.path.join(ruta_bd, nombre + ".DBF")
    t = dbf.Table(path, ignore_memos=True)
    t.open(dbf.READ_ONLY)
    campos = list(t.field_names)
    rows = []
    for r in t:
        if not r.has_been_deleted:
            rows.append({c: (r[c].strip() if isinstance(r[c], str) else r[c]) for c in campos})
    t.close()
    return rows, campos


def consulta_reg_ctas(ruta_bd, parametros):
    """REG_CTAS con joins a TERCEROS, TIPO_DOC y CUENTA."""
    rows_rc, _ = leer_tabla(ruta_bd, "REG_CTAS")
    rows_ter, _ = leer_tabla(ruta_bd, "TERCEROS")
    rows_tip, _ = leer_tabla(ruta_bd, "TIPO_DOC")
    rows_cta, _ = leer_tabla(ruta_bd, "CUENTA")

    terceros  = {r['COD_TER']: r['NOMBRE'] for r in rows_ter}
    tipo_docs = {r['CODIGO']: r['NOMBRE']  for r in rows_tip}
    cuentas   = {r['CODIGO']: r['NOMBRE']  for r in rows_cta}

    # Filtros opcionales
    lapso    = parametros.get('lapso')
    empresa  = parametros.get('empresa')
    tercero  = parametros.get('tercero')
    limite   = int(parametros.get('limite', 200))

    resultado = []
    for r in rows_rc:
        if lapso   and str(r.get('LAPSO', '')).strip() != str(lapso):
            continue
        if empresa and str(r.get('EMPRESA', '')).strip() != str(empresa):
            continue
        if tercero and str(r.get('TERCERO', '')).strip() != str(tercero):
            continue

        cod_ter  = str(r.get('TERCERO', '')).strip()
        cod_tipo = str(r.get('TIPO', '')).strip()
        cod_cta  = str(r.get('CUENTA', '')).strip()

        resultado.append({
            'consecutivo': r.get('CONSECUTIV'),
            'cuenta':      cod_cta,
            'cuenta_nom':  cuentas.get(cod_cta, ''),
            'lapso':       r.get('LAPSO'),
            'fecha':       str(r.get('FECHAHORA', '')),
            'tercero':     cod_ter,
            'tercero_nom': terceros.get(cod_ter, ''),
            'tipo':        cod_tipo,
            'tipo_nom':    tipo_docs.get(cod_tipo, ''),
            'documento':   r.get('DOCUMENTO'),
            'debito':      float(r.get('TOT_DEB') or 0),
            'credito':     float(r.get('TOT_CRE') or 0),
            'detalle':     str(r.get('DETALLE_CT', '')).strip(),
            'anulado':     r.get('ANULADO'),
        })
        if len(resultado) >= limite:
            break

    return resultado


CONSULTAS = {
    'reg_ctas': consulta_reg_ctas,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--servidor', default='https://tuc-tuc.onrender.com')
    parser.add_argument('--cliente',  required=True, help='ID único del cliente')
    args = parser.parse_args()

    base = args.servidor.rstrip('/')
    cliente_id = args.cliente

    print(f"=== Admin Agent — cliente: {cliente_id} ===")
    print(f"Servidor: {base}")

    # Leer ruta BD
    try:
        ruta_bd = leer_ruta_bd()
        print(f"BD: {ruta_bd}")
    except Exception as e:
        print(f"ERROR leyendo ruta BD: {e}")
        sys.exit(1)

    # Check-in
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
                    print(f"Sesión inválida — reconectando...")
                    break

                consulta = data.get('consulta')
                if consulta:
                    cid   = consulta['id']
                    tipo  = consulta['tipo']
                    params = consulta.get('parametros') or {}
                    print(f"Consulta #{cid}: {tipo} {params}")

                    if tipo in CONSULTAS:
                        try:
                            resultado = CONSULTAS[tipo](ruta_bd, params)
                            requests.post(f"{base}/api/admin-agent/respuesta",
                                json={'token': token, 'consulta_id': cid, 'respuesta': resultado},
                                timeout=20)
                            print(f"  → {len(resultado)} registros enviados")
                        except Exception as e:
                            requests.post(f"{base}/api/admin-agent/respuesta",
                                json={'token': token, 'consulta_id': cid, 'error': str(e)},
                                timeout=10)
                            print(f"  → ERROR: {e}")
                    else:
                        requests.post(f"{base}/api/admin-agent/respuesta",
                            json={'token': token, 'consulta_id': cid, 'error': f'Tipo desconocido: {tipo}'},
                            timeout=10)

            except requests.RequestException as e:
                print(f"Red: {e}")

            time.sleep(POLL_INTERVALO)

    except KeyboardInterrupt:
        print("\nDesconectando...")
        try:
            requests.post(f"{base}/api/admin-agent/checkout",
                          json={'token': token}, timeout=10)
        except:
            pass
        print("Agente detenido.")


if __name__ == '__main__':
    main()
