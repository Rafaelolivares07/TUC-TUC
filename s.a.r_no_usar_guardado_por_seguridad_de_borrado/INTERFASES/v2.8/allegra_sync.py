"""
allegra_sync.py — Sincronizador Alegra -> Administrator (SAR)
Autor: Rafael / Claude — v2 2026-03-28
Estado: OPERATIVO — credenciales y estructura API confirmadas

Propósito:
    Consulta las facturas de las dos empresas de Pilar en Alegra,
    extrae los ítems y los escribe en `allegra_pendientes.dbf` para que
    `interfaz_allegra.prg` los procese en VFP.

Cómo ejecutar:
    python C:\\S.A.R\\allegra_sync.py

Dependencias:
    pip install requests dbf
"""

import requests
import dbf
import json
from datetime import datetime, date
import base64

# ================================================================
# EMPRESAS — dos cuentas Alegra de Pilar
# ================================================================

EMPRESAS = [
    {
        "nombre":   "ELECTRONICAS J&P",
        "email":    "electronicajyp@hotmail.com",
        "token":    "aabde447e95a29efb773",
        "empresa":  "LP",    # JOSE LUIS CHAPARRO NINCO
    },
    {
        "nombre":   "ELECTRONICAS TV & VIDEO",
        "email":    "electronicastvyvideo@hotmail.com",
        "token":    "ade8e319ce85985fb47c",
        "empresa":  "02",    # MARIA DEL PILAR PERALTA MOSQUERA
    },
]

ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"

# ================================================================
# RUTAS — todo dentro del mundo Administrator
# ================================================================

def _leer_ruta_bd():
    """
    Lee la ruta de la BD activa desde C:\\S.A.R\\RutaBaseDatos\\ruta.dbf
    (mecanismo estándar de Administrator — funciona en cualquier equipo).
    Retorna la carpeta con backslash final, ej: "C:\\D\\Pilar Peralta\\basedatosempresas\\"
    """
    import os
    ruta_dbf = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"
    t = dbf.Table(ruta_dbf)
    t.open(dbf.READ_ONLY)
    ruta_dbc = t[0].ruta.strip()
    t.close()
    carpeta = os.path.dirname(ruta_dbc)
    return carpeta + os.sep

_BD = _leer_ruta_bd().rstrip("\\")

DBF_CONFIG     = _BD + r"\allegra_config.dbf"
DBF_PENDIENTES = _BD + r"\allegra_pendientes.dbf"

# ================================================================
# ESTRUCTURA DEL DBF INTERMEDIO
# Debe coincidir con lo que lee interfaz_allegra.prg
# ================================================================

ESTRUCTURA_DBF = (
    "factura_id  C(20);"   # ID de la factura en Alegra
    "nit_cli     C(20);"   # identificación del cliente
    "tipo_doc    C(20);"   # tipo Alegra: saleTicket, invoice, creditNote, etc.
    "num_doc     C(20);"   # número completo (ej: PJP15780)
    "fecha       D;"       # fecha de la factura
    "cod_pro     C(20);"   # referencia del producto (= cod_pro Administrator OK)
    "nombre      C(60);"   # nombre del producto en Alegra (para detectar bolsa plástica)
    "cantidad    N(10,2);" # cantidad vendida
    "precio      N(12,2);" # precio unitario sin IVA
    "por_iva     N(5,2);"  # porcentaje IVA (ej: 19.00)
    "val_iva     N(12,2);" # valor IVA del ítem
    "descuento   N(12,2);" # descuento aplicado
    "costo       N(12,2);" # costo (no disponible en Alegra — queda en 0)
    "met_pago    C(20);"   # método dominante (compat con registros anteriores)
    "val_pago    N(12,2);" # total pagado en la factura (suma de payments)
    "pagos       C(200);"  # JSON: [{"m":"cash","v":10000.0}, ...] — todos los payments
    "procesado   L;"       # .F. = pendiente, .T. = procesado por VFP
    "empresa     C(5);"    # código empresa (LP / 02)
    "nomb_cli    C(60);"   # nombre del cliente en Alegra (para crear TERCERO sin tipear)
    "seller_id   C(10);"   # ID del vendedor en Alegra (para mapeo con Administrator)
    "fecha_hora  T;"       # datetime exacto de Alegra (factura["datetime"])
)


# ================================================================
# MIGRACIÓN AUTOMÁTICA DE allegra_config.dbf
# Corre siempre al inicio — verifica estructura y migra si es necesario
# ================================================================

def _migrar_config():
    """
    Verifica que allegra_config.dbf tiene la estructura correcta (con campo empresa).
    Si no existe -> lo crea con 2 registros (02 y LP).
    Si existe sin campo empresa -> migra: renombra el viejo, crea el nuevo con datos preservados.
    Imprime resultado claro para que Rafael pueda verificar.
    """
    import os
    print("\n[MIGRACIÓN] Verificando allegra_config.dbf...")

    if not os.path.exists(DBF_CONFIG):
        print("  No existe -> creando con estructura nueva (02 y LP)...")
        cfg = dbf.Table(
            DBF_CONFIG,
            "empresa C(5); max_fact N(5,0); intervalo N(3,0); desde_ult L; ultima_sin T; "
            "total_proc N(10,0); num_inicio C(20); ultimo_log M",
            dbf_type="vfp",
        )
        cfg.open(dbf.READ_WRITE)
        for emp in ["02", "LP"]:
            cfg.append({
                "empresa": emp, "max_fact": 50, "intervalo": 0,
                "desde_ult": True, "total_proc": 0,
                "num_inicio": "", "ultimo_log": "Sin sincronizaciones aun.",
            })
        cfg.close()
        print("  OK Creado OK — 2 registros (02 y LP)")
        return

    # Verificar si tiene campo empresa
    t = dbf.Table(DBF_CONFIG)
    t.open(dbf.READ_ONLY)
    tiene_empresa = "EMPRESA" in t.field_names
    registros_viejos = [dict(r) for r in t if not dbf.is_deleted(r)] if not tiene_empresa else None
    n_registros = len([r for r in t if not dbf.is_deleted(r)])
    t.close()

    if tiene_empresa and n_registros >= 2:
        print(f"  OK Estructura OK — {n_registros} registros encontrados")
        return

    if tiene_empresa and n_registros < 2:
        # Tiene empresa pero falta algún registro
        t = dbf.Table(DBF_CONFIG)
        t.open(dbf.READ_WRITE)
        empresas_existentes = set(str(r.empresa).strip() for r in t if not dbf.is_deleted(r))
        for emp in ["02", "LP"]:
            if emp not in empresas_existentes:
                t.append({
                    "empresa": emp, "max_fact": 50, "intervalo": 0,
                    "desde_ult": True, "total_proc": 0,
                    "num_inicio": "", "ultimo_log": "Sin sincronizaciones aun.",
                })
                print(f"  + Registro empresa {emp} agregado")
        t.close()
        print("  OK Migración completada")
        return

    # No tiene campo empresa -> migrar preservando valores del registro viejo
    print("  AVISO:  Campo 'empresa' no existe -> migrando estructura...")
    backup = DBF_CONFIG.replace(".dbf", "_bak.dbf")
    os.rename(DBF_CONFIG, backup)
    print(f"  Backup: Backup guardado en: {backup}")

    rec_viejo = registros_viejos[0] if registros_viejos else {}
    max_fact  = int(rec_viejo.get("max_fact", 50)  or 50)
    intervalo = int(rec_viejo.get("intervalo", 0)  or 0)
    desde_ult = bool(rec_viejo.get("desde_ult", True))

    cfg = dbf.Table(
        DBF_CONFIG,
        "empresa C(5); max_fact N(5,0); intervalo N(3,0); desde_ult L; ultima_sin T; "
        "total_proc N(10,0); num_inicio C(20); ultimo_log M",
        dbf_type="vfp",
    )
    cfg.open(dbf.READ_WRITE)
    for emp in ["02", "LP"]:
        cfg.append({
            "empresa": emp, "max_fact": max_fact, "intervalo": intervalo,
            "desde_ult": desde_ult, "total_proc": 0,
            "num_inicio": "", "ultimo_log": "Sin sincronizaciones aun.",
        })
    cfg.close()
    print(f"  OK Migración completada — max_fact={max_fact}, intervalo={intervalo} preservados")
    print(f"  ℹ️  num_inicio quedó vacío en ambas empresas — definir en el formulario de configuración")


# ================================================================
# LEER PARÁMETROS DESDE allegra_config.dbf
# ================================================================

def leer_config():
    """
    Lee la configuración desde allegra_config.dbf (un registro por empresa).
    Retorna dict con:
      - max_fact, intervalo, desde_ult  -> globales (del primer registro)
      - por_empresa: { "02": {num_inicio, ultima_sin}, "LP": {num_inicio, ultima_sin} }
    """
    defaults = {
        "max_fact": 50, "intervalo": 0, "desde_ult": True,
        "por_empresa": {
            "02": {"num_inicio": "", "ultima_sin": None},
            "LP": {"num_inicio": "", "ultima_sin": None},
        }
    }
    try:
        t = dbf.Table(DBF_CONFIG)
        t.open(dbf.READ_ONLY)
        cfg = None
        por_empresa = {}
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            emp = str(rec.empresa).strip()
            if cfg is None:
                cfg = {
                    "max_fact":  int(rec.max_fact)  if rec.max_fact  else 50,
                    "intervalo": int(rec.intervalo) if rec.intervalo else 0,
                    "desde_ult": bool(rec.desde_ult),
                }
            por_empresa[emp] = {
                "num_inicio": str(rec.num_inicio).strip() if hasattr(rec, 'num_inicio') else "",
                "ultima_sin": rec.ultima_sin if rec.ultima_sin else None,
            }
        t.close()
        if cfg is None:
            return defaults
        cfg["por_empresa"] = por_empresa
        return cfg
    except Exception as e:
        print(f"Aviso: no se pudo leer allegra_config.dbf ({e}) — usando defaults")
        return defaults


# ================================================================
# AUTENTICACIÓN
# ================================================================

def _headers(email, token):
    cred = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {
        "Authorization": f"Basic {cred}",
        "Accept": "application/json",
    }


# ================================================================
# OBTENER FACTURAS DE ALEGRA
# ================================================================

def obtener_facturas(empresa, desde_fecha=None, max_fact=50):
    """
    Trae facturas de una empresa desde Alegra.
    Filtra por fecha si desde_fecha (date) está disponible.
    Retorna lista de dicts de factura con sus ítems incluidos.
    """
    h = _headers(empresa["email"], empresa["token"])
    params = {"limit": min(max_fact, 30), "start": 0}
    if desde_fecha:
        params["date-start"] = desde_fecha.strftime("%Y-%m-%d")

    facturas = []
    while len(facturas) < max_fact:
        resp = requests.get(f"{ALEGRA_BASE_URL}/invoices", headers=h, params=params, timeout=30)
        resp.raise_for_status()
        lote = resp.json()
        if not lote:
            break
        facturas.extend(lote)
        if len(lote) < params["limit"]:
            break
        params["start"] += len(lote)

    return facturas[:max_fact]


# ================================================================
# EXTRAER CÓDIGO DE PRODUCTO
# ================================================================

import re as _re

def _extraer_cod_pro(item):
    """
    Intenta obtener el código del producto en este orden:
    1. Campo reference si está lleno  -> "8099"
    2. Número al inicio del name antes de "..." o "…" -> "9560...MICROFONO" -> "9560"
    3. Número al inicio del name sin separador -> "10692EXTENSION..." -> "10692"
    4. S/REF si no se puede determinar (ej: bolsa sin código)
    """
    ref = item.get("reference")
    if ref:
        return str(ref)

    name = item.get("name") or ""
    # Patrón: dígitos al inicio seguidos de ... o … o letra/espacio
    m = _re.match(r'^(\d+)[\.\…]', name)
    if m:
        return m.group(1)

    # Dígitos pegados al inicio sin separador explícito
    m = _re.match(r'^(\d{3,})', name)
    if m:
        return m.group(1)

    return "S/REF"


# ================================================================
# MAPEAR FACTURA + ÍTEM -> REGISTRO DBF
# ================================================================

def mapear_item(factura, item, empresa_codigo):
    """
    Convierte un ítem de Alegra al formato del DBF intermedio.

    Campos confirmados en API real (2026-03-28):
    - factura.id             -> factura_id
    - factura.client.identification -> nit_cli
    - factura.numberTemplate.documentType -> tipo_doc (saleTicket, invoice, etc.)
    - factura.numberTemplate.fullNumber   -> num_doc
    - factura.date           -> fecha (string YYYY-MM-DD)
    - item.reference         -> cod_pro (idéntico a Administrator OK)
    - item.name              -> nombre (para detección bolsa plástica)
    - item.quantity          -> cantidad
    - item.price             -> precio sin IVA (precio unitario)
    - item.tax[0].percentage -> por_iva
    - item.tax[0].amount     -> val_iva
    - item.discount          -> descuento
    - factura.payments       -> met_pago (método dominante), val_pago (total pagado)
    (costo no disponible en Alegra — se deja en 0 para calcular luego en VFP)
    """
    fecha_fact    = datetime.strptime(factura["date"], "%Y-%m-%d").date() if factura.get("date") else date.today()
    datetime_fact = datetime.strptime(factura["datetime"], "%Y-%m-%d %H:%M:%S") if factura.get("datetime") else datetime.combine(fecha_fact, datetime.min.time())

    tax_pct   = 0.0
    tax_monto = 0.0
    if item.get("tax"):
        t = item["tax"][0]
        tax_pct   = float(t.get("percentage", 0))
        tax_monto = float(t.get("amount", 0))

    payments    = factura.get("payments") or []
    met_pago    = payments[0].get("paymentMethod", "") if payments else ""
    val_pago    = sum(float(p.get("amount", 0)) for p in payments)
    pagos_json  = json.dumps(
        [{"m": p.get("paymentMethod", ""), "v": float(p.get("amount", 0))} for p in payments],
        ensure_ascii=False, separators=(',', ':')
    )[:200]

    seller_id = str((factura.get("seller") or {}).get("id", "") or "")[:10]

    return {
        "factura_id":  str(factura.get("id", ""))[:20],
        "nit_cli":     str((factura.get("client") or {}).get("identification", ""))[:20],
        "nomb_cli":    str((factura.get("client") or {}).get("name", "") or "").encode('cp1252', errors='replace').decode('cp1252')[:60],
        "tipo_doc":    str((factura.get("numberTemplate") or {}).get("documentType", ""))[:20],
        "num_doc":     str((factura.get("numberTemplate") or {}).get("fullNumber", ""))[:20],
        "fecha":       fecha_fact,
        "fecha_hora":  datetime_fact,
        "cod_pro":     _extraer_cod_pro(item)[:20],
        "nombre":      str(item.get("name", "")).encode('cp1252', errors='replace').decode('cp1252')[:60],
        "cantidad":    float(item.get("quantity", 0)),
        "precio":      float(item.get("price", 0)),
        "por_iva":     tax_pct,
        "val_iva":     tax_monto,
        "descuento":   float(item.get("discount", 0)),
        "costo":       0.0,
        "met_pago":    met_pago[:20],
        "val_pago":    val_pago,
        "pagos":       pagos_json,
        "procesado":   False,
        "empresa":     empresa_codigo[:5],
        "seller_id":   seller_id,
    }


# ================================================================
# MIGRACIÓN allegra_pendientes.dbf — agregar campo pagos si falta
# ================================================================

def _migrar_pendientes():
    """Agrega campos nuevos al DBF si faltan (pagos, fecha_hora)."""
    import os, shutil, tempfile
    if not os.path.exists(DBF_PENDIENTES) or os.path.getsize(DBF_PENDIENTES) == 0:
        return  # se creará nuevo con la estructura completa
    t = dbf.Table(DBF_PENDIENTES, codepage='cp1252')
    t.open(dbf.READ_ONLY)
    campos = [f.lower() for f in t.field_names]
    t.close()
    if 'pagos' in campos and 'fecha_hora' in campos:
        return  # ya migrado
    # Recrear con campo extra preservando datos
    print("[MIGRACIÓN] allegra_pendientes.dbf — agregando campos faltantes (pagos, fecha_hora)...")
    t_old = dbf.Table(DBF_PENDIENTES, codepage='cp1252')
    t_old.open(dbf.READ_ONLY)
    filas = []
    for r in t_old:
        if dbf.is_deleted(r): continue
        fila = {c: getattr(r, c) for c in campos}
        if 'pagos' not in campos:
            fila['pagos'] = json.dumps(
                [{"m": str(fila.get('met_pago', '') or '').strip(), "v": float(fila.get('val_pago', 0) or 0)}],
                separators=(',', ':')
            )[:200]
        if 'fecha_hora' not in campos:
            fila['fecha_hora'] = datetime.combine(fila['fecha'], datetime.min.time()) if fila.get('fecha') else datetime.now()
        filas.append(fila)
    t_old.close()
    tmp = DBF_PENDIENTES + '.bak'
    shutil.copy2(DBF_PENDIENTES, tmp)
    os.remove(DBF_PENDIENTES)
    t_new = dbf.Table(DBF_PENDIENTES, ESTRUCTURA_DBF, dbf_type='vfp', codepage='cp1252')
    t_new.open(dbf.READ_WRITE)
    campos_new = [f.lower() for f in t_new.field_names]
    for fila in filas:
        row = {c: fila[c] for c in campos_new if c in fila}
        t_new.append(row)
    t_new.close()
    os.remove(tmp)
    print(f"  Migración OK — {len(filas)} registros preservados")


# ================================================================
# ESCRIBIR EN allegra_pendientes.dbf
# ================================================================

def escribir_dbf(registros):
    """
    Crea o abre el DBF y agrega registros nuevos (evita duplicados).
    VFP lee este archivo con USE ... SHARED.
    """
    import os
    _migrar_pendientes()
    if not os.path.exists(DBF_PENDIENTES) or os.path.getsize(DBF_PENDIENTES) == 0:
        tabla = dbf.Table(DBF_PENDIENTES, ESTRUCTURA_DBF, dbf_type='vfp', codepage='cp1252')
    else:
        tabla = dbf.Table(DBF_PENDIENTES, codepage='cp1252')
    tabla.open(dbf.READ_WRITE)

    nuevos = 0
    for r in registros:
        ya_existe = any(
            rec.factura_id.strip() == r["factura_id"] and
            rec.cod_pro.strip()    == r["cod_pro"]
            for rec in tabla
            if not dbf.is_deleted(rec)
        )
        if not ya_existe:
            campos = [f.lower() for f in tabla.field_names]
            fila = {
                "factura_id": r["factura_id"],
                "nit_cli":    r["nit_cli"],
                "tipo_doc":   r["tipo_doc"],
                "num_doc":    r["num_doc"],
                "fecha":      r["fecha"],
                "cod_pro":    r["cod_pro"],
                "nombre":     r["nombre"],
                "cantidad":   r["cantidad"],
                "precio":     r["precio"],
                "por_iva":    r["por_iva"],
                "val_iva":    r["val_iva"],
                "descuento":  r["descuento"],
                "costo":      r["costo"],
                "met_pago":   r["met_pago"],
                "val_pago":   r["val_pago"],
                "procesado":  r["procesado"],
                "empresa":    r["empresa"],
            }
            if "nomb_cli" in campos:
                fila["nomb_cli"] = r.get("nomb_cli", "")
            if "seller_id" in campos:
                fila["seller_id"] = r.get("seller_id", "")
            if "pagos" in campos:
                fila["pagos"] = r.get("pagos", "")
            if "fecha_hora" in campos:
                fila["fecha_hora"] = r.get("fecha_hora")
            tabla.append(fila)
            nuevos += 1

    tabla.close()
    print(f"  {nuevos} ítems nuevos escritos en {DBF_PENDIENTES}")
    return nuevos


# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 55)
    print("  Alegra Sync — SAR Administrator")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    _migrar_config()

    cfg = leer_config()
    print(f"Config: max_fact={cfg['max_fact']}, desde_ult={cfg['desde_ult']}")
    for emp_cod, emp_cfg in cfg["por_empresa"].items():
        print(f"  {emp_cod}: num_inicio={emp_cfg['num_inicio']}, ultima_sin={emp_cfg['ultima_sin']}")

    total_registros = []

    for emp in EMPRESAS:
        emp_cod = emp["empresa"]
        emp_cfg = cfg["por_empresa"].get(emp_cod, {"num_inicio": "", "ultima_sin": None})
        num_inicio = emp_cfg["num_inicio"]

        desde_fecha = None
        if cfg["desde_ult"] and emp_cfg["ultima_sin"]:
            ult = emp_cfg["ultima_sin"]
            # Ignorar fecha sentinel de reinicio (2000-01-01)
            if isinstance(ult, datetime) and ult.year >= 2001:
                desde_fecha = ult
            elif isinstance(ult, date) and not isinstance(ult, datetime) and ult.year >= 2001:
                desde_fecha = ult

        num_inicio_n = int(''.join(filter(str.isdigit, num_inicio))) if num_inicio and any(c.isdigit() for c in num_inicio) else 0
        print(f"\n--- {emp['nombre']} ({emp_cod}) — desde: {desde_fecha or 'todo'}, num_inicio: {num_inicio or 'ninguno'} ---")
        try:
            # Paginar hasta encontrar facturas <= num_inicio (extraccion completa, sin limite max_fact)
            registros = []
            start = 0
            BATCH = 30
            while True:
                h = _headers(emp["email"], emp["token"])
                params = {"limit": BATCH, "start": start}
                if desde_fecha:
                    params["date-start"] = desde_fecha.strftime("%Y-%m-%d")
                resp = requests.get(f"{ALEGRA_BASE_URL}/invoices", headers=h, params=params, timeout=30)
                resp.raise_for_status()
                lote = resp.json()
                if not lote:
                    break
                alcanzamos_limite = False
                for factura in lote:
                    num_fact = str((factura.get("numberTemplate") or {}).get("fullNumber", ""))
                    num_fact_n = int(''.join(filter(str.isdigit, num_fact))) if any(c.isdigit() for c in num_fact) else 0
                    if num_inicio_n and num_fact_n <= num_inicio_n:
                        alcanzamos_limite = True
                        continue
                    for item in factura.get("items", []):
                        registros.append(mapear_item(factura, item, emp_cod))
                if alcanzamos_limite or len(lote) < BATCH:
                    break
                start += BATCH

            print(f"  {len(registros)} ítems a procesar")
            total_registros.extend(registros)

        except Exception as e:
            print(f"  ERROR: {e}")

    if total_registros:
        print(f"\nEscribiendo {len(total_registros)} registros en DBF...")
        escribir_dbf(total_registros)
        print("\nListo. Ejecuta en VFP:")
        print("  DO C:\\S.A.R\\PROYECTO\\interfaz_allegra.prg")
    else:
        print("\nNo hay ítems nuevos para procesar.")

    print("=" * 55)


if __name__ == "__main__":
    main()
