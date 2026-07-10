"""
interfaz_allegra.py — Interfaz Python directa Alegra → Administrator (SAR)
Reemplaza interfaz_allegra.prg para procesamiento automático.
Lee allegra_pendientes.dbf y escribe directamente en los DBF de Administrator.

Fase actual implementada:
  Pasos 0-5   : setup, leer pendientes, resolver NIT, tipo_doc, llenar PROD_FACT
  Paso  6b    : INSERT PROD_FACT1 (registro definitivo de ventas) ← ACTIVO
  Paso  6a    : STANDAR (REG_PROD + REG_PROD_SALDOS)             ← ACTIVO
  Paso  7     : costo_ventas_contabiliza (REG_CTAS costos)        ← ACTIVO
  Paso  8     : contabilizar (REG_CTAS asientos principales)      ← ACTIVO
  Pasos 9-11  : nota, cleanup, actualizar config                  ← ACTIVO

Nota: reg_costos_temporal.dbf existió como tabla intermedia entre _standar() y
_costo_ventas_contabiliza(). Se eliminó en el rediseño: los items de costo se
pasan directamente en memoria (_items_costo) sin pasar por el DBF.
"""

import os
import sys
import struct
import logging
import json
import uuid
import subprocess
import dbf
from datetime import datetime

# ================================================================
# LOGGING — solo stdout (configurar_allegra.py captura y muestra)
# ================================================================

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ================================================================
# CONSTANTES (equivalentes a PUBLIC de VFP)
# ================================================================

COD_TER_USUARIO  = 1    # COD_TER=1, Rafael — VAR_CODIGO_TERCERO_USUARIO

# ================================================================
# STAGING — Python NO escribe en tablas productivas directamente.
# Escribe en tablas stg_* que el PROCESADOR_STAGING.EXE (VFP)
# mueve a las tablas reales, actualizando CDX automáticamente.
# ================================================================

# Cuando frozen (EXE), buscar junto al ejecutable; si no, junto a este script
if getattr(sys, 'frozen', False):
    PROCESADOR_EXE = os.path.join(os.path.dirname(sys.executable), "PROCESADOR_STAGING.EXE")
else:
    PROCESADOR_EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PROCESADOR_STAGING.EXE")

ESTRUCTURAS_STG = {
    "stg_lotes": (
        "batch_id C(36); empresa C(5); factura_id C(20); num_doc C(20); "
        "procesado L; fecha T; motivo C(200)"
    ),
    "stg_prod_fact1": (
        "batch_id C(36); consecutiv N(10,0); cod_pro C(14); cod_fac C(14); "
        "tip_fac C(10); cantidad N(12,4); precio N(15,2); descuento N(15,2); "
        "usuario N(8,0); empresa C(4); fechahora T; por_iva N(6,2); sector C(10); "
        "vendedor N(8,0); cliente N(8,0); conse_reg_ N(10,0); conse_orig N(10,0); "
        "estado_env N(4,0); costo N(15,2); comision N(8,0)"
    ),
    "stg_reg_prod": (
        "batch_id C(36); consecutiv N(10,0); tip_doc C(10); num_doc C(20); "
        "lap T; can_ent N(12,4); can_sal N(12,4); cos_sal N(15,2); cod_pro C(14); "
        "fec T; usu N(8,0); ter_com N(8,0); emp C(4); ent_bod C(4); "
        "sal_exi N(12,0); val_exi_co N(15,2); cos_und_co N(15,4); "
        "cod_ori C(14); conse_prod N(10,0); concepto N(4,0)"
    ),
    "stg_reg_prod_sal": (
        "batch_id C(36); op C(1); cod_pro C(14); emp C(4); ent_bod N(4,0); "
        "consecutiv N(10,0); tip_doc C(10); num_doc C(20); can_ent N(12,4); "
        "can_sal N(12,4); fec T; usu N(8,0); ter_com N(8,0); "
        "sal_exi N(12,0); cos_und_co N(15,4); val_exi_co N(15,2); conse_reg_ N(10,0)"
    ),
    "stg_reg_ctas": (
        "batch_id C(36); consecutiv N(10,0); cuenta C(15); lapso D; fechahora T; "
        "tercero N(8,0); empresa C(10); tipo C(6); documento C(20); usuario N(8,0); "
        "valor N(15,2); tot_deb N(15,2); tot_cre N(15,2); producto C(25); "
        "ter_cod N(8,0); tip_doc_cr C(6); num_doc_cr C(20)"
    ),
    "stg_sal_doc": (
        "batch_id C(36); op C(1); tip_doc C(10); num_doc C(20); cod_cue C(16); "
        "cod_ter N(8,0); nat_cue C(1); fec_doc D; emp C(10); fec_hor T; "
        "usu N(8,0); valor N(15,2)"
    ),
    "stg_nota": (
        "batch_id C(36); tipo C(10); numero C(20); nota C(254); nota1 C(100); "
        "empresa C(10); cuenta C(15); tercero N(8,0); imagen C(100)"
    ),
    "stg_terceros": (
        "batch_id C(36); cod_ter N(10,0); nombre C(50); identifica C(15); "
        "empresa C(6); usuario N(6,0); tipo N(10,0); cupo N(10,0); num_cue N(1,0)"
    ),
}


def _crear_tablas_staging():
    """Crea tablas de staging en la carpeta BD si no existen. Idempotente."""
    for nombre, estructura in ESTRUCTURAS_STG.items():
        ruta = os.path.join(_BD, f"{nombre}.dbf")
        if not os.path.exists(ruta):
            try:
                t = dbf.Table(ruta, estructura, dbf_type="vfp", codepage="cp1252")
                t.open(dbf.READ_WRITE)
                t.close()
                log.info(f"  Staging creada: {nombre}.dbf")
            except Exception as e:
                log.error(f"  Error creando {nombre}.dbf: {e}")


def _stg_open(nombre: str):
    """Abre tabla staging en READ_WRITE. Crea si no existe."""
    ruta = os.path.join(_BD, f"{nombre}.dbf")
    if not os.path.exists(ruta):
        estructura = ESTRUCTURAS_STG[nombre]
        t = dbf.Table(ruta, estructura, dbf_type="vfp", codepage="cp1252")
    else:
        t = dbf.Table(ruta, codepage="cp1252")
    t.open(dbf.READ_WRITE)
    return t


def _llamar_procesador() -> bool:
    """
    Ejecuta PROCESADOR_STAGING.EXE (VFP) que mueve staging → tablas reales.
    Retorna True si terminó con código 0, False si no se encontró o falló.
    """
    if not os.path.exists(PROCESADOR_EXE):
        log.warning(f"  PROCESADOR_STAGING.EXE no encontrado en {PROCESADOR_EXE} — staging pendiente")
        return False
    try:
        r = subprocess.run([PROCESADOR_EXE], timeout=300, capture_output=True)
        if r.returncode == 0:
            log.info("  PROCESADOR_STAGING.EXE completado OK")
            return True
        else:
            log.error(f"  PROCESADOR_STAGING.EXE error (returncode={r.returncode})")
            return False
    except subprocess.TimeoutExpired:
        log.error("  PROCESADOR_STAGING.EXE timeout (>5 min)")
        return False
    except Exception as e:
        log.error(f"  PROCESADOR_STAGING.EXE: {e}")
        return False


def _registrar_lote_stg(batch_id: str, empresa: str, factura_id: str, num_doc: str):
    """Inserta un lote en stg_lotes (PROCESADO=.F.)."""
    t = _stg_open("stg_lotes")
    t.append({
        "batch_id":   batch_id,
        "empresa":    empresa[:5],
        "factura_id": factura_id[:20],
        "num_doc":    num_doc[:20],
        "procesado":  False,
        "fecha":      datetime.now(),
        "motivo":     "",
    })
    t.close()


def _factura_en_staging_pendiente(factura_id: str) -> bool:
    """True si hay un lote sin procesar para esta factura_id en stg_lotes."""
    ruta = os.path.join(_BD, "stg_lotes.dbf")
    if not os.path.exists(ruta):
        return False
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if str(rec.factura_id).strip() == factura_id and not bool(rec.procesado):
                t.close()
                return True
        t.close()
    except Exception:
        pass
    return False


def _dbf_max_consecutiv(ruta: str) -> int:
    """
    Lee MAX(CONSECUTIV) de un DBF directamente con struct, sin cargar toda la tabla.
    Escanea TODOS los registros no borrados para obtener el máximo real.
    """
    try:
        with open(ruta, "rb") as f:
            hdr = f.read(32)
            if len(hdr) < 32:
                return 0
            num_rec    = struct.unpack_from("<I", hdr, 4)[0]
            hdr_size   = struct.unpack_from("<H", hdr, 8)[0]
            rec_size   = struct.unpack_from("<H", hdr, 10)[0]
            if num_rec == 0 or rec_size == 0:
                return 0
            # Leer descriptores de campos hasta encontrar CONSECUTIV
            f.seek(32)
            field_offset = 1  # byte 0 del registro = flag borrado
            fld_off = None
            fld_len = None
            while True:
                fd = f.read(32)
                if not fd or fd[0] == 0x0D or fd[0] == 0x00:
                    break
                fname = fd[:11].split(b"\x00")[0].decode("ascii", errors="replace").upper()
                flen  = fd[16]
                if fname == "CONSECUTIV":
                    fld_off = field_offset
                    fld_len = flen
                    break
                field_offset += flen
            if fld_off is None:
                return 0
            # Escanear todos los registros no borrados para obtener el MAX real
            max_val = 0
            for i in range(num_rec):
                f.seek(hdr_size + i * rec_size)
                rec = f.read(rec_size)
                if not rec or rec[0] == ord("*"):
                    continue
                val_b = rec[fld_off: fld_off + fld_len]
                try:
                    v = int(float(val_b.decode("ascii", errors="replace").strip()))
                    if v > max_val:
                        max_val = v
                except (ValueError, TypeError):
                    continue
            return max_val
    except Exception:
        pass
    return 0


def _max_consecutivo() -> int:
    """MAX(CONSECUTIV) de PROD_FACT1 — lectura directa sin cargar toda la tabla."""
    return _dbf_max_consecutiv(os.path.join(_BD, "PROD_FACT1.dbf"))


def _cod_vendedor_alegra(seller_id: str, empresa: str) -> int:
    """
    Busca el seller_id de Alegra en alegra_vendedores.dbf y devuelve
    el CODIGO de la tabla de vendedores de Administrator (campo VENDEDOR en PROD_FACT1).
    Retorna 0 si no hay mapeo definido.
    """
    if not seller_id:
        return 0
    ruta = os.path.join(_BD, "alegra_vendedores.dbf")
    if not os.path.exists(ruta):
        return 0
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        campos = [f.lower() for f in t.field_names]
        # campo cod_mes (nuevo) o cod_ter (legacy antes del fix)
        campo_cod = 'cod_mes' if 'cod_mes' in campos else 'cod_ter'
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if (str(rec.seller_id).strip() == str(seller_id).strip() and
                    str(rec.empresa).strip() == str(empresa).strip()):
                cod = int(getattr(rec, campo_cod) or 0)
                t.close()
                return cod
        t.close()
    except Exception:
        pass
    return 0

def _accion_nit(nit: str, empresa: str) -> str:
    """
    Devuelve la accion configurada en alegra_nits_pend.dbf para este NIT.
    'pendiente' (default) | 'ignorar'
    """
    ruta = os.path.join(_BD, "alegra_nits_pend.dbf")
    if not os.path.exists(ruta):
        return "pendiente"
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if str(rec.nit).strip() == nit and str(rec.empresa).strip() == empresa:
                accion = str(rec.accion).strip() or "pendiente"
                t.close()
                return accion
        t.close()
    except Exception:
        pass
    return "pendiente"


def _leer_auto_nit() -> bool:
    """Lee la config auto_nit de allegra_config.dbf (primera fila). False si no existe."""
    ruta = os.path.join(_BD, "allegra_config.dbf")
    if not os.path.exists(ruta):
        return False
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        campos = [f.lower() for f in t.field_names]
        for r in t:
            if not dbf.is_deleted(r):
                val = bool(getattr(r, 'auto_nit', False)) if 'auto_nit' in campos else False
                t.close()
                return val
        t.close()
    except Exception:
        pass
    return False


def _leer_estructura_dbf_bin(ruta: str):
    """Lee header y descriptores de campos de un .dbf directamente."""
    with open(ruta, 'rb') as f:
        h = f.read(32)
        num_rec  = struct.unpack_from('<I', h, 4)[0]
        hdr_size = struct.unpack_from('<H', h, 8)[0]
        rec_size = struct.unpack_from('<H', h, 10)[0]
        campos = []
        pos = 1
        while True:
            fd = f.read(32)
            if not fd or fd[0] == 0x0D:
                break
            name = fd[:11].rstrip(b'\x00').decode('cp1252', errors='replace')
            tipo = chr(fd[11])
            size = fd[16]
            dec  = fd[17]
            campos.append((name, tipo, pos, size, dec))
            pos += size
    return num_rec, hdr_size, rec_size, campos


def _auto_crear_tercero(nit: str, nombre: str, empresa: str, batch_id: str = "") -> int:
    """
    Registra un TERCERO nuevo en stg_terceros para que el PROCESADOR VFP
    lo inserte en TERCEROS (con CDX actualizado automáticamente).
    Retorna cod_ter asignado, o 0 si falla.
    Si el NIT ya está en stg_terceros (mismo ciclo), retorna ese cod_ter sin crear duplicado.
    """
    ruta = os.path.join(_BD, "TERCEROS.dbf")
    if not os.path.exists(ruta):
        log.error(f"    auto_nit: TERCEROS.dbf no encontrado en {_BD}")
        return 0
    try:
        # Verificar si el NIT ya fue creado en este ciclo (stg_terceros aún no procesado por VFP)
        ruta_stg_pre = os.path.join(_BD, "stg_terceros.dbf")
        if os.path.exists(ruta_stg_pre):
            try:
                num_pre, hdr_pre, rsz_pre, campos_pre = _leer_estructura_dbf_bin(ruta_stg_pre)
                cm_pre = {c[0]: (c[2], c[3], c[4], c[1]) for c in campos_pre}
                if 'IDENTIFICA' in cm_pre and 'COD_TER' in cm_pre:
                    nit_base = nit.split('-')[0].strip()
                    with open(ruta_stg_pre, 'rb') as fpre:
                        fpre.seek(hdr_pre)
                        id_off = cm_pre['IDENTIFICA'][0]
                        id_sz  = cm_pre['IDENTIFICA'][1]
                        ct_off = cm_pre['COD_TER'][0]
                        ct_sz  = cm_pre['COD_TER'][1]
                        for _ in range(num_pre):
                            rec_pre = fpre.read(rsz_pre)
                            if len(rec_pre) < rsz_pre:
                                break
                            if rec_pre[0] == 0x2A:
                                continue
                            identifica = rec_pre[id_off:id_off+id_sz].decode('cp1252', errors='replace').strip()
                            identifica_base = identifica.split('-')[0].strip()
                            if identifica_base == nit_base:
                                cod_existente = rec_pre[ct_off:ct_off+ct_sz].decode('cp1252', errors='replace').strip()
                                try:
                                    cod = int(float(cod_existente))
                                    log.info(f"    auto_nit: NIT={nit} ya en stg_terceros COD_TER={cod} — reutilizando")
                                    return cod
                                except Exception:
                                    pass
            except Exception:
                pass

        # Calcular siguiente COD_TER leyendo el máximo en TERCEROS.dbf (tabla real)
        num_rec, hdr_size, rec_size, campos = _leer_estructura_dbf_bin(ruta)
        campo_map = {c[0]: (c[2], c[3], c[4], c[1]) for c in campos}
        max_cod = 0
        with open(ruta, 'rb') as f:
            f.seek(hdr_size)
            cod_off = campo_map['COD_TER'][0]
            cod_sz  = campo_map['COD_TER'][1]
            for _ in range(num_rec):
                rec = f.read(rec_size)
                if len(rec) < rec_size:
                    break
                if rec[0] == 0x2A:
                    continue
                val = rec[cod_off:cod_off+cod_sz].decode('cp1252', errors='replace').strip()
                try:
                    v = int(float(val))
                    if v > max_cod:
                        max_cod = v
                except Exception:
                    pass

        # También revisar stg_terceros — terceros creados en el mismo ciclo aún
        # no insertados por VFP. Sin esto, dos facturas nuevas del mismo ciclo
        # leen el mismo MAX y quedan con COD_TER duplicado.
        ruta_stg = os.path.join(_BD, "stg_terceros.dbf")
        if os.path.exists(ruta_stg):
            try:
                num_rec2, hdr2, rsz2, campos2 = _leer_estructura_dbf_bin(ruta_stg)
                campo_map2 = {c[0]: (c[2], c[3], c[4], c[1]) for c in campos2}
                if 'COD_TER' in campo_map2:
                    with open(ruta_stg, 'rb') as f2:
                        f2.seek(hdr2)
                        c_off = campo_map2['COD_TER'][0]
                        c_sz  = campo_map2['COD_TER'][1]
                        for _ in range(num_rec2):
                            rec2 = f2.read(rsz2)
                            if len(rec2) < rsz2:
                                break
                            if rec2[0] == 0x2A:
                                continue
                            val2 = rec2[c_off:c_off+c_sz].decode('cp1252', errors='replace').strip()
                            try:
                                v2 = int(float(val2))
                                if v2 > max_cod:
                                    max_cod = v2
                            except Exception:
                                pass
            except Exception:
                pass

        nuevo_cod = max_cod + 1

        # Insertar en staging — VFP hará el APPEND real con CDX actualizado
        t = _stg_open("stg_terceros")
        t.append({
            "batch_id":   (batch_id or "")[:36],
            "cod_ter":    nuevo_cod,
            "nombre":     nombre[:50],
            "identifica": nit[:15],
            "empresa":    empresa[:6],
            "usuario":    1,
            "tipo":       0,
            "cupo":       0,
            "num_cue":    0,
        })
        t.close()

        log.info(f"    auto_nit: TERCERO en staging NIT={nit} nombre='{nombre}' COD_TER={nuevo_cod}")
        return nuevo_cod

    except Exception as e:
        log.error(f"    auto_nit: error creando TERCERO NIT={nit}: {e}")
        return 0


def _registrar_nit_pendiente(nit: str, num_doc: str, empresa: str, nombre_cli: str = ""):
    """
    Registra en alegra_nits_pend.dbf que este NIT no fue encontrado
    en TERCEROS y la factura num_doc queda pendiente.
    Agrega num_doc a la lista de afectadas si no estaba ya.
    """
    ruta = os.path.join(_BD, "alegra_nits_pend.dbf")
    if not os.path.exists(ruta):
        try:
            t = dbf.Table(
                ruta,
                "nit C(20); empresa C(5); num_docs C(200); accion C(10)",
                dbf_type="vfp",
            )
            t.open(dbf.READ_WRITE)
            t.close()
        except Exception as e:
            log.error(f"No se pudo crear alegra_nits_pend.dbf: {e}")
            return
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        encontrado = False
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if str(rec.nit).strip() == nit and str(rec.empresa).strip() == empresa:
                encontrado = True
                docs_actuales = [d.strip() for d in str(rec.num_docs).split(",") if d.strip()]
                if num_doc not in docs_actuales:
                    docs_actuales.append(num_doc)
                    with rec:
                        rec.num_docs = ", ".join(docs_actuales)[:200]
                break
        if not encontrado:
            campos_nits = [f.lower() for f in t.field_names]
            fila = {
                "nit":      nit[:20],
                "empresa":  empresa[:5],
                "num_docs": num_doc[:200],
                "accion":   "pendiente",
            }
            if "nombre" in campos_nits and nombre_cli:
                fila["nombre"] = nombre_cli[:60]
            t.append(fila)
        elif nombre_cli:
            # Actualizar nombre si estaba vacío
            for rec in t:
                if dbf.is_deleted(rec):
                    continue
                if str(rec.nit).strip() == nit and str(rec.empresa).strip() == empresa:
                    campos_nits = [f.lower() for f in t.field_names]
                    if "nombre" in campos_nits and not str(getattr(rec, "nombre", "") or "").strip():
                        with rec:
                            rec.nombre = nombre_cli[:60]
                    break
        t.close()
    except Exception as e:
        log.error(f"Error registrando NIT pendiente: {e}")


def _marcar_nit_creado(nit: str, empresa: str, nombre_cli: str, num_doc: str):
    """
    Registra en alegra_nits_pend.dbf el NIT creado automáticamente con accion='creado'.
    Si ya existía como pendiente, actualiza la acción. Si no existía, lo inserta.
    Queda visible en la pestaña Terceros para auditoría.
    """
    ruta = os.path.join(_BD, "alegra_nits_pend.dbf")
    if not os.path.exists(ruta):
        _registrar_nit_pendiente(nit, num_doc, empresa, nombre_cli)
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        campos = [f.lower() for f in t.field_names]
        encontrado = False
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if str(rec.nit).strip() == nit and str(rec.empresa).strip() == empresa:
                with rec:
                    rec.accion = 'creado'
                    if 'nombre' in campos and nombre_cli:
                        rec.nombre = nombre_cli[:60]
                encontrado = True
                break
        if not encontrado:
            fila = {"nit": nit[:20], "empresa": empresa[:5],
                    "num_docs": num_doc[:200], "accion": "creado"}
            if "nombre" in campos and nombre_cli:
                fila["nombre"] = nombre_cli[:60]
            t.append(fila)
        t.close()
    except Exception as e:
        log.warning(f"    _marcar_nit_creado: {e}")


def _bodega(empresa: str) -> int:
    """LP → bodega 1,  02 → bodega 2."""
    return 1 if empresa.strip() == "LP" else 2

# ================================================================
# RUTAS
# ================================================================

def _leer_ruta_bd() -> str:
    """Devuelve la carpeta BD de Administrator (sin backslash final)."""
    ruta_dbf = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"
    t = dbf.Table(ruta_dbf)
    t.open(dbf.READ_ONLY)
    ruta_dbc = t[0].ruta.strip()
    t.close()
    return os.path.dirname(ruta_dbc)

_BD = _leer_ruta_bd()

def _ruta(nombre: str) -> str:
    return os.path.join(_BD, nombre)

DBF_PENDIENTES = _ruta("allegra_pendientes.dbf")
DBF_CONFIG     = _ruta("allegra_config.dbf")

# Crear tablas staging en la BD al cargar el módulo
try:
    _crear_tablas_staging()
except Exception as _e_stg:
    log.warning(f"  No se pudieron crear tablas staging: {_e_stg}")

# ================================================================
# LECTOR BINARIO DE DBF
# Necesario para tablas con .fpt huérfano (ej: TERCEROS).
# ================================================================

def _leer_estructura_dbf(ruta: str):
    """
    Lee header y descriptores de campos de un .dbf directamente.
    Devuelve (num_records, header_size, record_size, campos)
    donde campos = [(name, tipo, offset_en_registro, size), ...]
    """
    with open(ruta, 'rb') as f:
        header = f.read(32)
        num_records = struct.unpack_from('<I', header, 4)[0]
        header_size = struct.unpack_from('<H', header, 8)[0]
        record_size = struct.unpack_from('<H', header, 10)[0]

        campos = []
        pos = 1  # byte 0 es el flag de borrado
        while True:
            fd = f.read(32)
            if not fd or fd[0] == 0x0D:
                break
            name = fd[:11].rstrip(b'\x00').decode('cp1252', errors='replace')
            tipo = chr(fd[11])
            size = fd[16]
            campos.append((name, tipo, pos, size))
            pos += size

    return num_records, header_size, record_size, campos


def _buscar_campo_bin(ruta: str, campo_busqueda: str, valor: str,
                      campo_retorno: str, normalizar: bool = False) -> str | None:
    """
    Busca valor en campo_busqueda de un DBF via lectura binaria.
    Devuelve el valor de campo_retorno como string, o None si no encuentra.
    Útil para tablas con .fpt huérfano que la librería dbf rechaza.

    normalizar=True: compara solo la parte antes del primer '-' en el campo
    (necesario para NITs colombianos con dígito de verificación, ej: '860013730-5').
    """
    valor = valor.strip()
    num_records, header_size, record_size, campos = _leer_estructura_dbf(ruta)

    busqueda_info  = next((c for c in campos if c[0].upper() == campo_busqueda.upper()), None)
    retorno_info   = next((c for c in campos if c[0].upper() == campo_retorno.upper()), None)

    if busqueda_info is None or retorno_info is None:
        return None

    _, _, b_off, b_size = busqueda_info
    _, _, r_off, r_size = retorno_info

    with open(ruta, 'rb') as f:
        f.seek(header_size)
        for _ in range(num_records):
            rec = f.read(record_size)
            if len(rec) < record_size:
                break
            if rec[0] == 0x2A:   # '*' = borrado
                continue
            leido = rec[b_off:b_off + b_size].decode('cp1252', errors='replace').strip()
            if normalizar:
                leido = leido.split('-')[0].strip()
            if leido == valor:
                return rec[r_off:r_off + r_size].decode('cp1252', errors='replace').strip()

    return None


# ================================================================
# PASO 3 — Resolver NIT → COD_TER en TERCEROS
# (usa lector binario porque TERCEROS tiene .fpt huérfano)
# ================================================================

def _resolver_nit(nit: str) -> int | None:
    """
    Busca nit en TERCEROS.IDENTIFICA usando lector binario (evita error de .fpt huérfano).
    Los NITs en Administrator pueden tener dígito de verificación ('860013730-5'),
    mientras que Alegra los envía sin guión ('860013730') — se compara la parte base.
    """
    ruta = _ruta("TERCEROS.dbf")
    resultado = _buscar_campo_bin(ruta, "IDENTIFICA", nit, "COD_TER", normalizar=True)
    if resultado is None:
        return None
    try:
        return int(float(resultado))
    except (ValueError, TypeError):
        return None


# ================================================================
# PASO 3B — Resolver tipo_doc Alegra → TIP_ADMIN
# ================================================================

TIPOS_DOC_DEFAULT = [
    ("saleTicket", "013", "02"),
    ("saleTicket", "013", "LP"),
    ("invoice",    "",    "02"),
    ("invoice",    "",    "LP"),
    ("creditNote", "",    "02"),
    ("creditNote", "",    "LP"),
]

def _asegurar_tiposdoc():
    """Crea alegra_tiposdoc.dbf con mapeos por defecto si no existe."""
    ruta = _ruta("alegra_tiposdoc.dbf")
    if os.path.exists(ruta):
        return
    try:
        t = dbf.Table(ruta, "tip_alegra C(20); tip_admin C(10); empresa C(5)", dbf_type="vfp")
        t.open(dbf.READ_WRITE)
        for tip_alegra, tip_admin, empresa in TIPOS_DOC_DEFAULT:
            t.append((tip_alegra, tip_admin, empresa))
        t.close()
        log.info(f"alegra_tiposdoc.dbf creado con mapeos por defecto en {ruta}")
    except Exception as e:
        log.error(f"No se pudo crear alegra_tiposdoc.dbf: {e}")


def _resolver_tipo_doc(tipo_doc_alegra: str, empresa: str) -> str | None:
    """
    Busca (TIP_ALEGRA, EMPRESA) en alegra_tiposdoc.dbf.
    Devuelve TIP_ADMIN (ej: '013') o None si no hay mapeo.
    """
    tipo_doc_alegra = tipo_doc_alegra.strip()
    empresa = empresa.strip()
    ruta = _ruta("alegra_tiposdoc.dbf")
    _asegurar_tiposdoc()
    if not os.path.exists(ruta):
        return None
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        tip_admin = None
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if (str(rec.tip_alegra).strip() == tipo_doc_alegra and
                    str(rec.empresa).strip() == empresa):
                tip_admin = str(rec.tip_admin).strip() or None
                break
        t.close()
        return tip_admin
    except Exception as e:
        log.error(f"Error leyendo alegra_tiposdoc: {e}")
        return None


# ================================================================
# HELPERS DBF
# ================================================================

def _open_rw(nombre: str):
    t = dbf.Table(_ruta(nombre), codepage="cp1252")
    t.open(dbf.READ_WRITE)
    return t


def _num_doc_int(num_doc: str) -> int:
    """'PJP15780' → 15780"""
    digits = ''.join(c for c in num_doc if c.isdigit())
    return int(digits) if digits else 0


# ================================================================
# PASO 5 — Llenar PROD_FACT (staging)
# ================================================================

def _limpiar_prod_fact(cod_ter_cliente: int, empresa: str):
    """No-op — PROD_FACT.dbf ya no se usa en el flujo staging."""
    pass


def _llenar_prod_fact(items: list, cod_ter_cliente: int, empresa: str,
                      num_doc: str, seller_id: str = "", kw_bolsa: str = "BOLSA") -> list:
    """
    Calcula items_efectivos (filtra bolsas según kw_bolsa, agrega val_con_iv).
    Ya no escribe en PROD_FACT.dbf — el APPEND real lo hace VFP via staging.
    """
    items_efectivos = []
    for item in items:
        if kw_bolsa.upper() in str(item["nombre"]).upper():
            continue
        cantidad   = float(item["cantidad"])
        precio     = float(item["precio"])
        val_iva    = float(item["val_iva"])
        descuento  = float(item["descuento"])
        val_con_iv = (precio * cantidad) - descuento + (val_iva * cantidad)
        items_efectivos.append({**item, "val_con_iv": val_con_iv})
    return items_efectivos


# ================================================================
# PASO 6a — STANDAR (inventario) — TODO
# ================================================================

_BODEGAS = {"LP": 1, "02": 2}   # cod_bod de bodega.dbf por empresa


def _bodega_empresa(empresa: str) -> int:
    return _BODEGAS.get(empresa.strip().upper(), 1)


def _max_conse_reg_prod() -> int:
    """MAX(CONSECUTIV) de REG_PROD — lectura directa sin cargar toda la tabla."""
    return _dbf_max_consecutiv(_ruta("REG_PROD.dbf"))


def _conse_prod_fact1_item(num_doc: str, cod_pro: str) -> int:
    """PROD_FACT1.CONSECUTIV para este num_doc + cod_pro (ya insertado en f_prod1)."""
    try:
        t = dbf.Table(_ruta("PROD_FACT1.dbf"), codepage="cp1252")
        t.open(dbf.READ_ONLY)
        for r in t:
            if dbf.is_deleted(r):
                continue
            if (str(r.cod_fac).strip().upper() == num_doc.strip().upper() and
                    str(r.cod_pro).strip().upper() == cod_pro.strip().upper()):
                conse = int(r.consecutiv or 0)
                t.close()
                return conse
        t.close()
    except Exception:
        pass
    return 0


def _leer_trans_mat(cod_pro: str) -> list:
    """
    Lee TRANS_MAT para cod_pro y retorna lista de componentes:
    [{"codutil": str, "cantidad": float}, ...]
    Si no tiene filas o solo tiene el producto contra sí mismo,
    retorna el producto mismo con cantidad 1 (producto simple).
    """
    cod_pro_u = cod_pro.strip().upper()
    componentes = []
    try:
        t = dbf.Table(_ruta("TRANS_MAT.dbf"), codepage="cp1252")
        t.open(dbf.READ_ONLY)
        for r in t:
            if dbf.is_deleted(r):
                continue
            if str(r.codpro).strip().upper() == cod_pro_u:
                componentes.append({
                    "codutil":  str(r.codutil).strip().upper(),
                    "cantidad": float(r.cantidad or 1),
                })
        t.close()
    except Exception:
        pass
    if not componentes:
        componentes = [{"codutil": cod_pro_u, "cantidad": 1.0}]
    return componentes


def _saldo_producto(cod_pro_u: str, empresa_s: str, bodega: int) -> tuple:
    """Retorna (sal_exi, cos_und_co, val_exi_co) de REG_PROD_SALDOS."""
    try:
        t = dbf.Table(_ruta("REG_PROD_SALDOS.dbf"), codepage="cp1252")
        t.open(dbf.READ_ONLY)
        for r in t:
            if dbf.is_deleted(r):
                continue
            if (str(r.cod_pro).strip().upper() == cod_pro_u and
                    str(r.emp).strip().upper() == empresa_s and
                    int(r.ent_bod or 0) == bodega):
                sal = float(r.sal_exi or 0)
                cos = float(r.cos_und_co or 0)
                val = float(r.val_exi_co or 0)
                t.close()
                return sal, cos, val
        t.close()
    except Exception:
        pass
    return 0.0, 0.0, 0.0


def _update_reg_prod_saldos(cod_pro_u, empresa_s, bodega, tip_doc, num_doc,
                             var_can_sal, var_sal_exi, var_cos_und, var_val_exi,
                             cod_ter_cliente, lnconse, ahora, batch_id: str = ""):
    """UPDATE si existe, INSERT si no — escribe en stg_reg_prod_sal. VFP aplica en REG_PROD_SALDOS."""
    ruta_saldos = _ruta("REG_PROD_SALDOS.dbf")
    # Determinar si el registro ya existe para op='U' o 'I'
    encontrado = False
    max_conse  = 0
    try:
        ts = dbf.Table(ruta_saldos, codepage="cp1252")
        ts.open(dbf.READ_ONLY)
        for r in ts:
            if dbf.is_deleted(r):
                continue
            n = int(r.consecutiv or 0)
            if n > max_conse:
                max_conse = n
            if (str(r.cod_pro).strip().upper() == cod_pro_u and
                    str(r.emp).strip().upper() == empresa_s and
                    int(r.ent_bod or 0) == bodega):
                encontrado = True
        ts.close()
    except Exception:
        pass

    ts_stg = _stg_open("stg_reg_prod_sal")
    ts_stg.append({
        "batch_id":   batch_id,
        "op":         "U" if encontrado else "I",
        "cod_pro":    cod_pro_u[:14],
        "emp":        empresa_s[:4],
        "ent_bod":    bodega,
        "consecutiv": (0 if encontrado else max_conse + 1),
        "tip_doc":    tip_doc[:10],
        "num_doc":    num_doc[:20],
        "can_ent":    0.0,
        "can_sal":    var_can_sal,
        "fec":        ahora,
        "usu":        COD_TER_USUARIO,
        "ter_com":    cod_ter_cliente,
        "sal_exi":    var_sal_exi,
        "cos_und_co": var_cos_und,
        "val_exi_co": var_val_exi,
        "conse_reg_": lnconse,
    })
    ts_stg.close()

    # VFP aplica el INSERT o UPDATE en REG_PROD_SALDOS desde stg_reg_prod_sal


def _standar(tip_doc: str, num_doc: str, fecha, cantidad: float,
             cod_pro: str, costo: float, empresa: str,
             cod_ter_cliente: int, conse_prod_fact: int = 0,
             batch_id: str = "") -> float:
    """
    Replica standar.prg Modo 2 — salida por venta.
    Lee TRANS_MAT para obtener componentes del producto (kits o simple).
    Por cada componente: INSERT REG_PROD + UPDATE/INSERT REG_PROD_SALDOS.
    Retorna vncosto acumulado.
    """
    empresa_s  = empresa.strip().upper()
    cod_pro_u  = cod_pro.strip().upper()
    bodega     = _bodega_empresa(empresa_s)
    bodega_str = str(bodega)
    from datetime import date as _date_type
    ahora      = datetime.now()
    fecha_lap  = (datetime.combine(fecha, datetime.min.time()) if isinstance(fecha, _date_type)
                  else (fecha if isinstance(fecha, datetime) else ahora))

    # Tarjeta estándar del producto — puede ser kit con varios componentes
    componentes = _leer_trans_mat(cod_pro_u)

    # PROD_FACT1 consecutivo de este ítem (para CONSE_PROD en REG_PROD)
    # Si se pasa como parámetro (ciclo normal), se usa directamente.
    # Si es 0 (fase retomada), se busca en PROD_FACT1.
    if conse_prod_fact == 0:
        conse_prod_fact = _conse_prod_fact1_item(num_doc, cod_pro_u)

    vncosto = 0.0

    # Calcular base de consecutivo una sola vez — evita scan completo de REG_PROD por componente
    lnconse_base = _max_conse_reg_prod()

    for i_comp, comp in enumerate(componentes):
        codutil    = comp["codutil"]
        lccantidad = comp["cantidad"]
        var_can_sal = round(lccantidad * cantidad, 4)

        # Saldo actual del componente
        sal_exi_act, cos_und_act, val_exi_act = _saldo_producto(codutil, empresa_s, bodega)

        # Nuevos valores
        var_sal_exi = round(sal_exi_act - var_can_sal, 0)
        var_cos_und = round(cos_und_act, 2) if var_sal_exi > 0 else 0.0
        var_val_exi = round(val_exi_act - (var_can_sal * var_cos_und), 2) if var_sal_exi > 0 else 0.0
        vncosto    += cos_und_act * var_can_sal

        lnconse = lnconse_base + i_comp + 1

        # INSERT REG_PROD → staging
        tr = _stg_open("stg_reg_prod")
        tr.append({
            "batch_id":   batch_id,
            "consecutiv": lnconse,
            "tip_doc":    tip_doc[:10],
            "num_doc":    num_doc[:20],
            "lap":        fecha_lap,
            "can_ent":    0.0,
            "can_sal":    var_can_sal,
            "cos_sal":    costo,
            "cod_pro":    codutil[:14],
            "fec":        ahora,
            "usu":        COD_TER_USUARIO,
            "ter_com":    cod_ter_cliente,
            "emp":        empresa_s[:4],
            "ent_bod":    bodega_str,
            "sal_exi":    var_sal_exi,
            "val_exi_co": var_val_exi,
            "cos_und_co": var_cos_und,
            "cod_ori":    cod_pro_u[:14],
            "conse_prod": conse_prod_fact,
            "concepto":   0,
        })
        tr.close()

        # UPDATE/INSERT REG_PROD_SALDOS → staging
        _update_reg_prod_saldos(
            codutil, empresa_s, bodega, tip_doc, num_doc,
            var_can_sal, var_sal_exi, var_cos_und, var_val_exi,
            cod_ter_cliente, lnconse, ahora, batch_id=batch_id
        )

        log.info(f"    STANDAR {codutil} (ori={cod_pro_u}): can_sal={var_can_sal} sal_exi={var_sal_exi} cos={var_cos_und}")

    return vncosto


# ================================================================
# PASO 6b — INSERT PROD_FACT1 (registro definitivo de ventas)
# ================================================================

def _insertar_prod_fact1(items_efectivos: list, cod_ter_cliente: int,
                         empresa: str, num_doc: str, tip_fac: str,
                         seller_id: str = "", fecha=None, fecha_hora=None,
                         batch_id: str = ""):
    """
    Escribe en stg_prod_fact1 (staging). VFP hace el APPEND real en PROD_FACT1.
    """
    from datetime import date as _date_type

    if isinstance(fecha_hora, datetime):
        fecha_doc = fecha_hora
    elif isinstance(fecha, _date_type):
        fecha_doc = datetime.combine(fecha, datetime.min.time())
    elif isinstance(fecha, datetime):
        fecha_doc = fecha
    else:
        fecha_doc = datetime.now()

    empresa_s   = empresa.strip()
    cod_fac     = str(num_doc).strip()[:14]
    vendedor    = _cod_vendedor_alegra(seller_id, empresa_s)
    consecutivo = _max_consecutivo()
    t = _stg_open("stg_prod_fact1")

    for item in items_efectivos:
        consecutivo += 1
        t.append({
            "batch_id":    batch_id,
            "consecutiv":  consecutivo,
            "cod_pro":     str(item["cod_pro"])[:14],
            "cod_fac":     cod_fac,
            "tip_fac":     tip_fac[:10],
            "cantidad":    float(item["cantidad"]),
            "precio":      float(item["precio"]),
            "descuento":   float(item["descuento"]),
            "usuario":     COD_TER_USUARIO,
            "empresa":     empresa_s[:4],
            "fechahora":   fecha_doc,
            "por_iva":     float(item["por_iva"]),
            "sector":      "",
            "vendedor":    vendedor,
            "cliente":     cod_ter_cliente,
            "conse_reg_":  0,
            "conse_orig":  0,
            "estado_env":  0,
            "costo":       float(item.get("costo", 0.0)),
            "comision":    0,
        })

    t.close()
    log.info(f"    stg_prod_fact1: {len(items_efectivos)} items (fac {num_doc}, consecutiv hasta {consecutivo}, vendedor={vendedor})")


# ================================================================
# ================================================================
# PASO 7 — costo_ventas_contabiliza (REG_CTAS costos)
# ================================================================

def _costo_ventas_contabiliza(empresa: str, bodega: int, fecha=None,
                              _items_costo: list = None, batch_id: str = ""):
    """
    Replica costo_ventas_contabiliza.prg.
    _items_costo: lista de items en memoria (cod_pro, cantidad, costo, etc.)
    """
    # Cargar mapa grupo → cuentas desde GRUPOS (solo empresa o globales)
    grupos_map: dict[int, tuple[str, str]] = {}  # cod_grupo → (cuenta_inv, cuenta_cos)
    t_grp = dbf.Table(_ruta("GRUPOS.dbf"), codepage="cp1252")
    t_grp.open(dbf.READ_ONLY)
    for r in t_grp:
        if dbf.is_deleted(r):
            continue
        cg = int(r.cod_grupo or 0)
        grupos_map[cg] = (str(r.cuenta_inv).strip(), str(r.cuenta_cos).strip())
    t_grp.close()

    # Cargar mapa cod_pro → grupo desde PRODUCTOS
    prod_map: dict[str, int] = {}
    t_pro = dbf.Table(_ruta("PRODUCTOS.dbf"), codepage="cp1252")
    t_pro.open(dbf.READ_ONLY)
    for r in t_pro:
        if dbf.is_deleted(r):
            continue
        cod = str(r.codigo).strip().upper()
        prod_map[cod] = int(r.grupo or 0)
    t_pro.close()

    empresa_s = empresa.strip()
    registros = [
        {
            "cod_pro":  str(it["cod_pro"]).strip(),
            "cantidad": float(it["cantidad"]),
            "cod_fac":  str(it.get("num_doc", "")).strip(),
            "usuario":  COD_TER_USUARIO,
            "empresa":  empresa_s,
            "tipo_doc": str(it.get("tipo_doc", "")).strip(),
            "tercero":  int(it.get("tercero", 0)),
            "costo":    float(it.get("costo", 0)),
        }
        for it in (_items_costo or [])
    ]
    if not registros:
        log.info("    costo_ventas_contabiliza: sin registros — omitido")
        return []

    # Abrir stg_reg_ctas (staging) y REGCTA_CONSE (para reservar consecutivos)
    t_stg_ctas = _stg_open("stg_reg_ctas")
    t_conse    = dbf.Table(_ruta("REGCTA_CONSE.dbf"), codepage="cp1252")
    t_conse.open(dbf.READ_WRITE)

    from datetime import date as _date_type
    ahora     = datetime.now()
    fecha_lap = fecha.date() if hasattr(fecha, 'date') else (fecha if isinstance(fecha, _date_type) else ahora.date())
    n_asientos = 0
    var_consecutivo = 0
    sin_cuentas = []

    for reg in registros:
        cod_pro_u = reg["cod_pro"].upper()
        grupo     = prod_map.get(cod_pro_u, 0)
        cuentas   = grupos_map.get(grupo, ("", ""))
        cuenta_inv = cuentas[0]
        cuenta_cos = cuentas[1]

        if not cuenta_inv or not cuenta_cos:
            log.warning(f"    costo_ventas_contabiliza: {reg['cod_pro']} sin cuentas (grupo={grupo})")
            sin_cuentas.append(reg["cod_pro"])
            continue

        # Reservar consecutivos en REGCTA_CONSE (+2 por par)
        var_consecutivo = 0
        for r_conse in t_conse:
            var_consecutivo = int(r_conse.num_reg_ct or 0) + 2
            with r_conse:
                r_conse.num_reg_ct = var_consecutivo
            break

        # Record 1 → stg_reg_ctas: crédito inventario
        t_stg_ctas.append({
            "batch_id":   batch_id,
            "consecutiv": var_consecutivo - 1,
            "cuenta":     cuenta_inv[:15],
            "lapso":      fecha_lap,
            "fechahora":  ahora,
            "tercero":    reg["tercero"],
            "empresa":    reg["empresa"][:10],
            "tipo":       reg["tipo_doc"][:6],
            "documento":  reg["cod_fac"][:20],
            "usuario":    reg["usuario"],
            "valor":      reg["cantidad"],
            "tot_deb":    0.0,
            "tot_cre":    reg["costo"],
            "producto":   reg["cod_pro"][:25],
            "ter_cod":    reg["tercero"],
            "tip_doc_cr": "",
            "num_doc_cr": "",
        })

        # Record 2 → stg_reg_ctas: débito costo de ventas
        t_stg_ctas.append({
            "batch_id":   batch_id,
            "consecutiv": var_consecutivo,
            "cuenta":     cuenta_cos[:15],
            "lapso":      fecha_lap,
            "fechahora":  ahora,
            "tercero":    reg["tercero"],
            "empresa":    reg["empresa"][:10],
            "tipo":       reg["tipo_doc"][:6],
            "documento":  reg["cod_fac"][:20],
            "usuario":    reg["usuario"],
            "valor":      reg["cantidad"],
            "tot_deb":    reg["costo"],
            "tot_cre":    0.0,
            "producto":   reg["cod_pro"][:25],
            "ter_cod":    reg["tercero"],
            "tip_doc_cr": "",
            "num_doc_cr": "",
        })
        n_asientos += 2

    t_stg_ctas.close()
    t_conse.close()
    log.info(f"    stg_reg_ctas (costos): {n_asientos} asientos (conse hasta {var_consecutivo if registros else '—'})")
    return sin_cuentas


def _parsear_pagos(rec, campos: list) -> list:
    """
    Devuelve lista de dicts [{"m": método, "v": monto}, ...].
    Si el registro tiene el campo 'pagos' (JSON), lo parsea.
    Fallback: construye un solo elemento con met_pago + val_pago.
    """
    import json as _json
    if 'pagos' in campos:
        raw = str(getattr(rec, 'pagos', '') or '').strip()
        if raw:
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, list) and parsed:
                    return parsed
            except Exception:
                pass
    # Fallback: registro antiguo sin campo pagos
    met = str(getattr(rec, 'met_pago', '') or '').strip()
    val = float(getattr(rec, 'val_pago', 0) or 0)
    return [{"m": met, "v": val}]


def _met_coincide(met_pago: str, config_met: str) -> bool:
    """True si met_pago coincide exactamente con el método configurado."""
    if not config_met or not met_pago:
        return False
    return met_pago.strip().lower() == config_met.strip().lower()


# ================================================================
# PASO 8 — contabilizar (asientos principales)
# ================================================================

def _contabilizar(tip_fac: str, num_doc: str, empresa: str, bodega: int,
                  cod_ter_cliente: int, items_efectivos: list,
                  pagos: list, ln_bolsa: float, fecha=None, batch_id: str = ""):
    """
    Replica contabilizar.prg → valores_insertar.prg → inserta_reg_ctas.prg.
    Gate: verifica tip_fac en CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA.
    Construye pvar[1..9] desde totales de la factura.
    Escribe REG_CTAS por cada cuenta activa + SAL_DOC para cuentas con DOC_CRUZE=1.
    """
    from datetime import date as date_type

    empresa_s = empresa.strip()
    tip_fac_u = tip_fac.strip().upper()
    num_doc_u = num_doc.strip().upper()
    fecha_doc = fecha.date() if hasattr(fecha, 'date') else (fecha if isinstance(fecha, date_type) else date_type.today())
    ahora     = datetime.now()

    # ── Gate: doc automático configurado? ───────────────────────────────────
    t_gate = dbf.Table(_ruta("CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA.dbf"), codepage="cp1252")
    t_gate.open(dbf.READ_ONLY)
    es_automatico = False
    for r in t_gate:
        if dbf.is_deleted(r): continue
        if str(r.empresa).strip() == empresa_s and str(r.documento).strip().upper() == tip_fac_u:
            es_automatico = True
            break
    t_gate.close()
    if not es_automatico:
        log.info(f"    contabilizar: {tip_fac_u} no configurado como automático — omitido")
        return

    # ── Leer config de métodos de pago desde allegra_config.dbf ─────────────
    cfg_met = {"met_efect": "", "met_tarjet": "", "met_debito": "", "met_credit": "", "met_transf": "", "met_cxc": "", "kw_bolsa": "BOLSA"}
    try:
        t_ac = dbf.Table(os.path.join(_BD, "allegra_config.dbf"), codepage="cp1252")
        t_ac.open(dbf.READ_ONLY)
        campos_ac = [f.lower() for f in t_ac.field_names]
        for r in t_ac:
            if dbf.is_deleted(r): continue
            if str(r.empresa).strip() != empresa_s: continue
            for k in cfg_met:
                if k == "kw_bolsa":
                    continue  # se lee aparte, sin lowercase
                if k in campos_ac:
                    cfg_met[k] = str(getattr(r, k) or "").strip().lower()
            if "kw_bolsa" in campos_ac:
                val = str(getattr(r, "kw_bolsa") or "").strip()
                cfg_met["kw_bolsa"] = val if val else "BOLSA"
            break
        t_ac.close()
    except Exception:
        pass

    # ── Calcular valores base ────────────────────────────────────────────────
    subtotal = round(sum(float(it["cantidad"]) * float(it["precio"]) - float(it["descuento"])
                         for it in items_efectivos), 2)
    iva      = round(sum(float(it.get("val_iva", 0))
                         for it in items_efectivos), 0)  # val_iva ya es el total de la línea
    bolsas   = round(ln_bolsa, 0)

    # Ventas = subtotal de items efectivos (bolsas ya excluidas de items_efectivos)
    ventas   = round(subtotal, 0)

    # ── Mapa OBJETO → valor a grabar (soporta múltiples métodos de pago) ─────
    # Para cada objeto de cobro, suma los montos de todos los payments que
    # coincidan con el método configurado.
    # Ejemplo: cash=10k + credit-card=10k + accounts-receivable=10k →
    #   TXT_ABONA_EFECTIVO=10k, TXT_TARJETA_RECIBIDO=10k, TXT_COBRAR_CLIENTE=10k
    def _val_por_objeto(objeto: str) -> float:
        o = objeto.strip().upper()
        if o == "TXT_SUBTOTAL":              return ventas
        if o == "TXT_IVA_DEFINITIVO":        return iva
        if o == "TXT_BOLSA_IMPUESTO":        return bolsas
        if o == "TXT_DESCUENTO_DEFINITIVO":  return 0.0
        if o == "TXT_ABONA_EFECTIVO":
            return round(sum(p["v"] for p in pagos
                             if _met_coincide(p["m"], cfg_met["met_efect"])), 0)
        if o == "TXT_TARJETA_RECIBIDO":
            return round(sum(p["v"] for p in pagos
                             if (_met_coincide(p["m"], cfg_met["met_debito"]) or
                                 _met_coincide(p["m"], cfg_met["met_credit"]) or
                                 _met_coincide(p["m"], cfg_met["met_tarjet"]))), 0)
        if o in ("TXT_CONSIGNA_TRASFIERE", "TXT_CONSIGNA"):
            return round(sum(p["v"] for p in pagos
                             if _met_coincide(p["m"], cfg_met["met_transf"])), 0)
        if o == "TXT_COBRAR_CLIENTE":
            return round(sum(p["v"] for p in pagos
                             if _met_coincide(p["m"], cfg_met["met_cxc"])), 0)
        return 0.0

    # ── Cargar AYUDA: CONSECUTIVO → OBJETO ───────────────────────────────────
    ayuda_map: dict[int, str] = {}
    try:
        t_ay = dbf.Table(_ruta("AYUDA.dbf"), codepage="cp1252")
        t_ay.open(dbf.READ_ONLY)
        for r in t_ay:
            if dbf.is_deleted(r): continue
            ayuda_map[int(r.consecutiv or 0)] = str(r.objeto).strip()
        t_ay.close()
    except Exception:
        pass

    # ── Construir pvar[1..9] ─────────────────────────────────────────────────
    # pvar[1] = ventas (row con DOCUMENTO_='' — sin AYUDA link — siempre = subtotal)
    # pvar[n] para n>1 se resuelven dinámicamente via AYUDA
    pvar: dict[int, float] = {i: 0.0 for i in range(10)}
    pvar[1] = ventas   # fallback fijo: siempre es la base de ventas

    # Se completan en el loop de config rows (más abajo), una vez que tengamos
    # el DOCUMENTO_ de cada row para buscar en ayuda_map

    # ── Cargar config contable ────────────────────────────────────────────
    t_cfg = dbf.Table(_ruta("CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR.dbf"), codepage="cp1252")
    t_cfg.open(dbf.READ_ONLY)
    rows = []
    for r in t_cfg:
        if dbf.is_deleted(r): continue
        if str(r.empresa).strip() != empresa_s: continue
        if str(r.documento).strip().upper() != tip_fac_u: continue
        doc_cruze_raw = int(float(str(r.documento_).strip() or "0") if str(r.documento_).strip() else 0)
        objeto = ayuda_map.get(doc_cruze_raw, "")
        var_con_pr = int(r.var_con_pr or 0)
        # Si el row tiene un objeto en AYUDA, poblar pvar[n] desde _val_por_objeto
        if objeto and var_con_pr > 0:
            pvar[var_con_pr] = _val_por_objeto(objeto)
        rows.append({
            "orden":       int(r.orden or 0),
            "cuenta":      str(r.cuenta).strip(),
            "debito":      int(r.debito or 0),
            "diferencia":  int(r.diferencia or 0),
            "porcentaje":  float(r.porcentaje or 0),
            "valor_fijo":  float(r.valor_fijo or 0),
            "var_con_pr":  var_con_pr,
            "tercero_cu":  int(r.tercero_cu or 0),
            "tercero":     int(r.tercero or 0),
            "cruze":       int(r.cruze or 0),
        })
    t_cfg.close()
    rows.sort(key=lambda x: x["orden"])

    if not rows:
        log.info(f"    contabilizar: sin config contable para {tip_fac_u}/{empresa_s}")
        return

    # ── Calcular montos (valores_insertar.prg) ────────────────────────────
    total_deb = 0.0
    total_cre = 0.0
    activos = []

    for row in rows:
        lnvalor = 0.0
        if row["diferencia"] == 1:
            diff = abs(total_deb - total_cre)
            if total_deb > total_cre:
                row["tot_deb"] = 0.0; row["tot_cre"] = diff
            else:
                row["tot_deb"] = diff; row["tot_cre"] = 0.0
            if diff > 0:
                if total_deb > total_cre: total_cre += diff
                else: total_deb += diff
                row["actualizo"] = True
            else:
                row["actualizo"] = False
            activos.append(row)
            continue
        if row["var_con_pr"] > 0:
            lnvalor = pvar.get(row["var_con_pr"], 0.0)
        if row["valor_fijo"] > 0:
            lnvalor = row["valor_fijo"]
        if lnvalor > 0:
            if row["debito"] == 1:
                row["tot_deb"] = lnvalor; row["tot_cre"] = 0.0
                total_deb += lnvalor
            else:
                row["tot_deb"] = 0.0; row["tot_cre"] = lnvalor
                total_cre += lnvalor
            row["actualizo"] = True
        else:
            row["tot_deb"] = 0.0; row["tot_cre"] = 0.0
            row["actualizo"] = False
        activos.append(row)

    # ── Cargar DOC_CRUZE por cuenta desde CUENTAS ────────────────────────
    cuentas_set = {r["cuenta"] for r in activos if r.get("actualizo")}
    doc_cruze_map: dict[str, int] = {}
    nat_cue_map: dict[str, str] = {}
    if cuentas_set:
        t_cue = dbf.Table(_ruta("CUENTAS.dbf"), codepage="cp1252")
        t_cue.open(dbf.READ_ONLY)
        for r in t_cue:
            if dbf.is_deleted(r): continue
            cod = str(r.codigo).strip()
            if cod in cuentas_set:
                doc_cruze_map[cod] = int(r.doc_cruze or 0)
                nat_cue_map[cod]   = str(r.naturaleza).strip().upper()
        t_cue.close()

    # ── Insertar en staging stg_reg_ctas + stg_sal_doc ───────────────────────
    t_ctas  = _stg_open("stg_reg_ctas")
    t_conse = dbf.Table(_ruta("REGCTA_CONSE.dbf"), codepage="cp1252")
    t_conse.open(dbf.READ_WRITE)
    t_sal   = _stg_open("stg_sal_doc")

    n_asientos = 0
    var_consecutivo = 0

    for row in activos:
        if not row.get("actualizo"):
            continue

        # Consecutivo (+1 por asiento, a diferencia de costo_ventas que usa +2)
        for r_conse in t_conse:
            var_consecutivo = int(r_conse.num_reg_ct or 0) + 1
            with r_conse:
                r_conse.num_reg_ct = var_consecutivo
            break

        # Tercero del asiento
        if row["tercero_cu"] == 1:
            tercero_asiento = cod_ter_cliente
        elif row["tercero_cu"] == 2:
            tercero_asiento = cod_ter_cliente   # simplificado: mismo tercero
        else:
            tercero_asiento = row["tercero"] or 0

        cuenta = row["cuenta"]
        doc_cruze_val = doc_cruze_map.get(cuenta, 0)

        t_ctas.append({
            "batch_id":   batch_id,
            "consecutiv": var_consecutivo,
            "cuenta":     cuenta[:15],
            "lapso":      fecha_doc,
            "fechahora":  ahora,
            "tercero":    tercero_asiento,
            "empresa":    empresa_s[:10],
            "tipo":       tip_fac_u[:6],
            "documento":  num_doc_u[:20],
            "usuario":    COD_TER_USUARIO,
            "valor":      0,
            "tot_deb":    row["tot_deb"],
            "tot_cre":    row["tot_cre"],
            "producto":   "",
            "ter_cod":    cod_ter_cliente,
            "tip_doc_cr": tip_fac_u[:6] if doc_cruze_val == 1 else "",
            "num_doc_cr": num_doc_u[:20] if doc_cruze_val == 1 else "",
        })
        n_asientos += 1

        # SAL_DOC para cuentas con DOC_CRUZE=1 (cartera) → stg_sal_doc
        if doc_cruze_val == 1:
            lnvalor_sal = row["tot_deb"] if row["tot_deb"] > 0 else row["tot_cre"]
            nat = nat_cue_map.get(cuenta, "D")
            # Verificar si ya existe en SAL_DOC real (para OP='U') o en staging (OP='I')
            existe_real = False
            t_sal_real = dbf.Table(_ruta("SAL_DOC.dbf"), codepage="cp1252")
            t_sal_real.open(dbf.READ_ONLY)
            for r_sal in t_sal_real:
                if dbf.is_deleted(r_sal): continue
                if (str(r_sal.tip_doc).strip().upper() == tip_fac_u
                        and str(r_sal.num_doc).strip().upper() == num_doc_u
                        and str(r_sal.cod_cue).strip() == cuenta
                        and int(r_sal.cod_ter or 0) == tercero_asiento
                        and str(r_sal.emp).strip() == empresa_s):
                    existe_real = True
                    break
            t_sal_real.close()
            t_sal.append({
                "batch_id": batch_id,
                "op":       "U" if existe_real else "I",
                "tip_doc":  tip_fac_u[:10],
                "num_doc":  num_doc_u[:20],
                "cod_cue":  cuenta[:16],
                "cod_ter":  tercero_asiento,
                "nat_cue":  nat[:1],
                "fec_doc":  fecha_doc,
                "emp":      empresa_s[:10],
                "fec_hor":  ahora,
                "usu":      COD_TER_USUARIO,
                "valor":    lnvalor_sal,
            })

    t_ctas.close()
    t_conse.close()
    t_sal.close()
    log.info(f"    stg_reg_ctas (contab): {n_asientos} asientos (conse hasta {var_consecutivo})")


# ================================================================
# PASO 9 — Nota del documento
# ================================================================

def _insertar_nota(tip_fac: str, num_doc: str, empresa: str,
                   cod_ter_cliente: int, factura_id: str, batch_id: str = ""):
    t = _stg_open("stg_nota")
    t.append({
        "batch_id": batch_id,
        "tipo":     tip_fac[:10],
        "numero":   num_doc[:20],
        "nota":     f"Importado de Allegra - {factura_id}"[:254],
        "nota1":    "",
        "empresa":  empresa.strip()[:10],
        "cuenta":   "",
        "tercero":  cod_ter_cliente,
        "imagen":   "",
    })
    t.close()


# ================================================================
# PASO 10 — Cleanup
# ================================================================

def _limpiar_prod_fact_final(cod_ter_cliente: int, empresa: str):
    """No-op — PROD_FACT.dbf ya no se usa en el flujo staging."""
    pass


# Fases implementadas — agregar aqui al activar cada nueva fase
FASES_ACTIVAS = ['f_prod1', 'f_standar', 'f_costos', 'f_contab']
# FASES_ACTIVAS = ['f_prod1']                     # solo prod_fact1
# FASES_ACTIVAS = ['f_prod1', 'f_standar']        # sin contabilidad
# FASES_ACTIVAS = ['f_prod1', 'f_standar', 'f_costos']  # sin asientos principales


def _leer_max_fact(empresa: str) -> int:
    """Lee max_fact de allegra_config.dbf — cuantas facturas procesar por ciclo."""
    try:
        t = dbf.Table(DBF_CONFIG, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if str(rec.empresa).strip() == empresa.strip():
                v = int(rec.max_fact or 0)
                t.close()
                return v if v > 0 else 50
        t.close()
    except Exception:
        pass
    return 50


def _marcar_motivo(factura_id: str, motivo: str):
    """Escribe el motivo de error en todos los items de la factura en allegra_pendientes."""
    try:
        t = dbf.Table(DBF_PENDIENTES, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        campos = [f.lower() for f in t.field_names]
        if "motivo" not in campos:
            t.close()
            return
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if str(rec.factura_id).strip() == factura_id:
                with rec:
                    rec.motivo = motivo[:100]
        t.close()
    except Exception as e:
        log.error(f"Error escribiendo motivo: {e}")


def _marcar_fases(factura_id: str, fases: dict):
    """
    Actualiza flags de fase en allegra_pendientes para una factura.
    fases: {'f_prod1': True, ...}  — NO toca el campo procesado.
    """
    try:
        t = dbf.Table(DBF_PENDIENTES, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        campos = [f.lower() for f in t.field_names]
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if str(rec.factura_id).strip() == factura_id:
                with rec:
                    for campo, val in fases.items():
                        if campo in campos:
                            setattr(rec, campo, val)
        t.close()
    except Exception as e:
        log.warning(f"_marcar_fases {factura_id} - no se pudo escribir flags: {e}")


def _marcar_completo(factura_id: str):
    """
    Marca la factura como completamente procesada (todas las fases).
    Pone procesado=True y limpia el motivo.
    """
    t = dbf.Table(DBF_PENDIENTES, codepage="cp1252")
    t.open(dbf.READ_WRITE)
    campos = [f.lower() for f in t.field_names]
    for rec in t:
        if dbf.is_deleted(rec):
            continue
        if str(rec.factura_id).strip() == factura_id:
            with rec:
                rec.procesado = True
                if "motivo" in campos:
                    rec.motivo = ""
    t.close()


def _marcar_completo_con_alerta(factura_id: str, motivo: str):
    """
    Marca la factura como procesada pero con alertas — procesado=True, motivo=descripcion.
    Aparece en la pestaña 'Procesadas con alertas' del formulario.
    """
    t = dbf.Table(DBF_PENDIENTES, codepage="cp1252")
    t.open(dbf.READ_WRITE)
    campos = [f.lower() for f in t.field_names]
    for rec in t:
        if dbf.is_deleted(rec):
            continue
        if str(rec.factura_id).strip() == factura_id:
            with rec:
                rec.procesado = True
                if "motivo" in campos:
                    rec.motivo = motivo[:254]
    t.close()


def _marcar_procesado(factura_id: str, fases: dict = None):
    """Compatibilidad — delega a _marcar_fases y/o _marcar_completo."""
    if fases:
        _marcar_fases(factura_id, fases)
    else:
        _marcar_completo(factura_id)


# ================================================================
# PASO 11 — Actualizar allegra_config
# ================================================================

def _actualizar_config(empresa: str, fact_procesadas: int):
    if fact_procesadas == 0:
        return
    t = dbf.Table(DBF_CONFIG, codepage="cp1252")
    t.open(dbf.READ_WRITE)
    empresa_s = empresa.strip()
    for rec in t:
        if dbf.is_deleted(rec):
            continue
        if str(rec.empresa).strip() == empresa_s:
            with rec:
                rec.ultima_sin  = datetime.now()
                rec.total_proc  = int(rec.total_proc) + fact_procesadas
            break
    t.close()


# ================================================================
# FUNCIÓN PRINCIPAL — procesar una empresa
# ================================================================

def procesar_empresa(empresa: str, max_por_ciclo: int = 0, _tw=None) -> int:
    """
    Procesa facturas pendientes de una empresa (02 o LP).
    max_por_ciclo: limite de facturas por llamada (0 = sin limite).
    Devuelve cantidad de facturas en las que avanzo al menos una fase.
    """
    empresa = empresa.strip()
    if _tw is None:
        _tw = lambda msg: None  # no-op si no se pasa
    log.info(f"=== Empresa {empresa} (max={max_por_ciclo or 'sin limite'}) ===")
    print(f"\n=== Empresa {empresa} ===")

    bodega = _bodega(empresa)

    # --- Leer kw_bolsa global desde allegra_config.dbf ---
    kw_bolsa = "BOLSA"
    try:
        t_kw = dbf.Table(DBF_CONFIG, codepage="cp1252")
        t_kw.open(dbf.READ_ONLY)
        campos_kw = [f.lower() for f in t_kw.field_names]
        for r in t_kw:
            if dbf.is_deleted(r): continue
            if "kw_bolsa" in campos_kw:
                val = str(getattr(r, "kw_bolsa") or "").strip()
                if val:
                    kw_bolsa = val.upper()
            break  # global — primera fila basta
        t_kw.close()
    except Exception:
        pass

    # --- Leer pendientes: excluir solo las completamente procesadas ---
    pend = dbf.Table(DBF_PENDIENTES, codepage="cp1252")
    pend.open(dbf.READ_ONLY)
    campos = [f.lower() for f in pend.field_names]

    facturas: dict[str, dict] = {}
    for rec in pend:
        if dbf.is_deleted(rec):
            continue
        if str(rec.empresa).strip() != empresa:
            continue
        # Incluir si NO está completamente procesada
        if bool(rec.procesado):
            continue
        fid = str(rec.factura_id).strip()
        if fid not in facturas:
            facturas[fid] = {
                "factura_id": fid,
                "nit_cli":    str(rec.nit_cli).strip(),
                "tipo_doc":   str(rec.tipo_doc).strip(),
                "num_doc":    str(rec.num_doc).strip(),
                "fecha":      rec.fecha,
                "empresa":    empresa,
                "met_pago":   str(rec.met_pago).strip(),
                "val_pago":   float(rec.val_pago),
                "pagos":      _parsear_pagos(rec, campos),
                "seller_id":  str(getattr(rec, "seller_id", "") or "").strip() if "seller_id"  in campos else "",
                "nomb_cli":   str(getattr(rec, "nomb_cli",  "") or "").strip() if "nomb_cli"   in campos else "",
                "fecha_hora": getattr(rec, "fecha_hora", None) if "fecha_hora" in campos else None,
                # Flags de fase — estado actual en la BD
                "f_prod1":    bool(getattr(rec, "f_prod1",   False)) if "f_prod1"   in campos else False,
                "f_standar":  bool(getattr(rec, "f_standar", False)) if "f_standar" in campos else False,
                "f_costos":   bool(getattr(rec, "f_costos",  False)) if "f_costos"  in campos else False,
                "f_contab":   bool(getattr(rec, "f_contab",  False)) if "f_contab"  in campos else False,
                "items":      [],
            }
        facturas[fid]["items"].append({
            "cod_pro":   str(rec.cod_pro).strip(),
            "nombre":    str(rec.nombre).strip(),
            "cantidad":  float(rec.cantidad),
            "precio":    float(rec.precio),
            "por_iva":   float(rec.por_iva),
            "val_iva":   float(rec.val_iva),
            "descuento": float(rec.descuento),
            "costo":     float(rec.costo),
        })
    pend.close()

    # Filtrar: solo facturas con al menos una fase activa pendiente
    facturas_a_procesar = {
        fid: fac for fid, fac in facturas.items()
        if not all(fac.get(f) for f in FASES_ACTIVAS)
    }

    total = len(facturas_a_procesar)
    print(f"  {total} facturas con fases pendientes")
    log.info(f"  {total} facturas con fases pendientes (FASES_ACTIVAS={FASES_ACTIVAS})")

    avanzadas    = 0
    inconsistencias = 0
    auto_nit     = _leer_auto_nit()  # leído una vez por ciclo

    # Ordenar por num_doc ascendente — procesar de más antigua a más reciente
    facturas_ordenadas = sorted(
        facturas_a_procesar.values(),
        key=lambda x: int(''.join(c for c in x["num_doc"] if c.isdigit()) or "0")
    )

    for fac in facturas_ordenadas:
        fid = fac["factura_id"]
        # Limite por ciclo
        if max_por_ciclo > 0 and avanzadas >= max_por_ciclo:
            log.info(f"  Limite de {max_por_ciclo} facturas alcanzado")
            break

        num_doc  = fac["num_doc"]
        nit_cli  = fac["nit_cli"]
        tipo_doc = fac["tipo_doc"]
        pagos_fac = fac["pagos"]

        # --- Resolver NIT (necesario para cualquier fase) ---
        _tw(f"  {num_doc}: resolver NIT")
        batch_id = str(uuid.uuid4())  # pre-asignar para compartir con stg_terceros si aplica
        cod_ter_cliente = _resolver_nit(nit_cli)
        if cod_ter_cliente is None:
            if auto_nit:
                # Crear automáticamente y continuar — no reportar como inconsistencia
                nombre_cli = fac.get("nomb_cli", "") or nit_cli
                cod_ter_cliente = _auto_crear_tercero(nit_cli, nombre_cli, empresa, batch_id)
                if cod_ter_cliente == 0:
                    _registrar_nit_pendiente(nit_cli, num_doc, empresa, nombre_cli)
                    _marcar_motivo(fid, f"NIT '{nit_cli}' — error al crear automáticamente")
                    inconsistencias += 1
                    continue
                # Creado OK — registrar en pestaña Terceros con accion='creado'
                _marcar_nit_creado(nit_cli, empresa, nombre_cli, num_doc)
            else:
                accion = _accion_nit(nit_cli, empresa)
                _registrar_nit_pendiente(nit_cli, num_doc, empresa, fac.get("nomb_cli", ""))
                _marcar_motivo(fid, f"NIT '{nit_cli}' no en TERCEROS")
                if accion != "ignorar":
                    msg = f"  SKIP {num_doc}: NIT '{nit_cli}' no en TERCEROS"
                    print(msg); log.warning(msg)
                    inconsistencias += 1
                continue

        tip_fac = _resolver_tipo_doc(tipo_doc, empresa)
        if tip_fac is None:
            _marcar_motivo(fid, f"tipo_doc '{tipo_doc}' sin mapeo")
            msg = f"  SKIP {num_doc}: tipo_doc '{tipo_doc}' sin mapeo"
            print(msg); log.warning(msg)
            inconsistencias += 1
            continue

        fases_nuevas = {}
        items_efectivos = []
        alertas = []
        # batch_id ya asignado antes de resolver NIT (para compartir con stg_terceros)

        try:
            # Guard anti-duplicado: si ya hay lote pendiente en staging, esperar a PROCESADOR
            if _factura_en_staging_pendiente(fid):
                msg = f"  WAIT {num_doc}: staging pendiente para {fid[:12]} — esperando PROCESADOR"
                print(msg); log.info(msg)
                continue

            # ── FASES 1+2: STANDAR → PROD_FACT1 (orden correcto) ─────────────
            if not fac.get("f_prod1") or not fac.get("f_standar"):
                _limpiar_prod_fact(cod_ter_cliente, empresa)
                items_efectivos = _llenar_prod_fact(fac["items"], cod_ter_cliente, empresa, num_doc, seller_id=fac.get("seller_id", ""), kw_bolsa=kw_bolsa)

                ln_bolsa = sum(
                    float(it["cantidad"]) * float(it["precio"])
                    for it in fac["items"]
                    if kw_bolsa in str(it["nombre"]).upper()
                )

                if items_efectivos:
                    # Pre-calcular consecutivos de PROD_FACT1
                    _tw(f"  {num_doc}: max_consecutivo PROD_FACT1")
                    max_pf1 = _max_consecutivo()

                    # STANDAR primero — calcula costo real por item
                    for i, item in enumerate(items_efectivos):
                        pre_conse = max_pf1 + i + 1
                        _tw(f"  {num_doc}: standar item {i+1}/{len(items_efectivos)} ({item['cod_pro']})")
                        try:
                            vncosto = _standar(
                                tip_fac, num_doc, fac["fecha"], float(item["cantidad"]),
                                item["cod_pro"], float(item.get("costo", 0)),
                                empresa, cod_ter_cliente, conse_prod_fact=pre_conse,
                                batch_id=batch_id
                            )
                            item["costo"] = vncosto
                        except Exception as e_stan:
                            alerta = f"Producto {item['cod_pro']}: saldo/valor fuera de rango ({e_stan})"
                            alertas.append(alerta)
                            log.warning(f"  ALERTA standar {num_doc} — {alerta}")
                            item["costo"] = 0.0

                    # PROD_FACT1 con costos reales → stg_prod_fact1
                    _tw(f"  {num_doc}: insertar PROD_FACT1")
                    _insertar_prod_fact1(items_efectivos, cod_ter_cliente, empresa,
                                         num_doc, tip_fac, seller_id=fac.get("seller_id", ""),
                                         fecha=fac["fecha"],
                                         fecha_hora=fac.get("fecha_hora"),
                                         batch_id=batch_id)
                    for _it in items_efectivos:
                        _it["num_doc"]  = num_doc
                        _it["tipo_doc"] = tip_fac
                        _it["tercero"]  = cod_ter_cliente
                    _tw(f"  {num_doc}: costo_ventas_contabiliza")
                    try:
                        sin_cuentas = _costo_ventas_contabiliza(empresa, bodega, fecha=fac["fecha"],
                                                                _items_costo=items_efectivos,
                                                                batch_id=batch_id)
                        if sin_cuentas:
                            alerta = f"Costo ventas sin contabilizar (sin cuentas grupo=0): {', '.join(sin_cuentas)}"
                            alertas.append(alerta)
                            log.warning(f"  ALERTA costo_ventas {num_doc} — {alerta}")
                    except Exception as e_costo:
                        alerta = f"Costo ventas no contabilizado: {e_costo}"
                        alertas.append(alerta)
                        log.warning(f"  ALERTA costo_ventas {num_doc} — {alerta}")
                    if not fac.get("f_contab"):
                        _tw(f"  {num_doc}: contabilizar")
                        _contabilizar(tip_fac, num_doc, empresa, bodega, cod_ter_cliente,
                                      items_efectivos, pagos_fac, ln_bolsa,
                                      fecha=fac["fecha"], batch_id=batch_id)
                        _tw(f"  {num_doc}: contabilizar FIN")
                        fases_nuevas["f_contab"] = True
                else:
                    log.info(f"  {num_doc}: sin items efectivos (solo bolsas/vacio)")

                _insertar_nota(tip_fac, num_doc, empresa, cod_ter_cliente, fid, batch_id=batch_id)
                _limpiar_prod_fact_final(cod_ter_cliente, empresa)

                # Registrar lote en stg_lotes — VFP lo procesará
                _registrar_lote_stg(batch_id, empresa, fid, num_doc)

                fases_nuevas["f_prod1"]   = True
                fases_nuevas["f_standar"] = True
                fases_nuevas["f_costos"]  = True
                log.info(f"  STAGING OK — {num_doc} ({len(items_efectivos)} items) batch={batch_id[:8]}")

            # ── FASE 4: Contabilidad — descomentar cuando se implemente ───────
            # if not fac.get("f_contab"):
            #     ...
            #     fases_nuevas["f_contab"] = True

            # Guardar flags de fase
            if fases_nuevas:
                _marcar_fases(fid, fases_nuevas)
                fac.update(fases_nuevas)

            # Marcar completo si todas las fases activas terminaron
            if all(fac.get(f) for f in FASES_ACTIVAS):
                if alertas:
                    motivo_alerta = " | ".join(alertas)
                    _marcar_completo_con_alerta(fid, motivo_alerta)
                    msg = f"  OK-ALERTA {num_doc} (cli={cod_ter_cliente}) — {motivo_alerta}"
                else:
                    _marcar_completo(fid)
                    msg = f"  OK {num_doc} (cli={cod_ter_cliente}) fases={list(fases_nuevas)}"
            else:
                faltantes = [f for f in FASES_ACTIVAS if not fac.get(f)]
                msg = f"  PARCIAL {num_doc} — pendientes: {faltantes}"

            avanzadas += 1
            print(msg); log.info(msg)

        except Exception as e:
            msg = f"  FALLA {num_doc}: {e}"
            print(msg); log.exception(msg)
            _marcar_motivo(fid, f"FALLA: {e}")
            inconsistencias += 1

    _actualizar_config(empresa, avanzadas)
    resumen = f"  Empresa {empresa}: {avanzadas} avanzadas, {inconsistencias} con inconsistencias"
    print(resumen); log.info(resumen)

    # Llamar al PROCESADOR_STAGING.EXE para mover staging → tablas reales
    if avanzadas > 0:
        _llamar_procesador()

    return avanzadas


# ================================================================
# MAIN
# ================================================================

def _stats_pendientes_json() -> dict:
    """Lee allegra_pendientes.dbf y devuelve conteos para estado_proceso.json."""
    stats = {}
    ruta = os.path.join(_BD, "allegra_pendientes.dbf")
    if not os.path.exists(ruta):
        return stats
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        campos = [f.lower() for f in t.field_names]
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            emp = str(rec.empresa).strip()
            if emp not in stats:
                stats[emp] = {"pendientes": 0, "inconsistencias": 0, "procesadas": 0}
            procesado = bool(rec.procesado)
            motivo    = str(getattr(rec, "motivo", "") or "").strip() if "motivo" in campos else ""
            if procesado:
                stats[emp]["procesadas"] += 1
            elif motivo:
                stats[emp]["inconsistencias"] += 1
            else:
                stats[emp]["pendientes"] += 1
        t.close()
    except Exception:
        pass
    return stats


def _terceros_json() -> list:
    """Lee alegra_nits_pend.dbf y devuelve NITs pendientes de resolución."""
    resultado = []
    ruta = os.path.join(_BD, "alegra_nits_pend.dbf")
    if not os.path.exists(ruta):
        return resultado
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        campos = [f.lower() for f in t.field_names]
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            num_docs_raw = str(rec.num_docs).strip() if "num_docs" in campos else ""
            resultado.append({
                "nit":      str(rec.nit).strip(),
                "empresa":  str(rec.empresa).strip(),
                "nombre":   str(rec.nombre).strip() if "nombre" in campos else "",
                "num_docs": len([d for d in num_docs_raw.split(",") if d.strip()]),
                "accion":   str(rec.accion).strip() if "accion" in campos else "pendiente",
            })
        t.close()
    except Exception:
        pass
    return resultado


def _ultimo_log_json() -> str:
    """Lee el ultimo_log de allegra_config.dbf (empresa 02)."""
    try:
        ruta = os.path.join(_BD, "allegra_config.dbf")
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        for rec in t:
            if str(rec.empresa).strip() == "02":
                txt = str(rec.ultimo_log or "").strip()
                t.close()
                return txt
        t.close()
    except Exception:
        pass
    return ""


def _bd_config_json() -> dict:
    """BD esperada vs BD activa."""
    bd_esperada = ""
    bd_activa   = ""
    try:
        esperada_txt = r"C:\S.A.R\bd_esperada.txt"
        if os.path.exists(esperada_txt):
            bd_esperada = open(esperada_txt, encoding="utf-8").read().strip()
    except Exception:
        pass
    try:
        ruta_dbf = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"
        t = dbf.Table(ruta_dbf, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        for rec in t:
            bd_activa = str(rec.ruta).strip()
            break
        t.close()
    except Exception:
        pass
    return {
        "bd_esperada": bd_esperada,
        "bd_activa":   bd_activa,
        "coincide":    bd_esperada.upper() == bd_activa.upper() if bd_esperada else None,
    }


def _actualizar_estado_json(procesadas_ciclo: int):
    """Actualiza estado_proceso.json con resultado completo del ciclo."""
    json_path = r"C:\S.A.R\estado_proceso.json"
    try:
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

        data["ultimo_ciclo"] = {
            "fecha":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "procesadas": procesadas_ciclo,
        }
        data["facturas"]    = _stats_pendientes_json()
        data["terceros"]    = _terceros_json()
        data["ultimo_log"]  = _ultimo_log_json()
        data["bd_config"]   = _bd_config_json()
        data["_actualizado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def main():
    import time as _time
    _t0 = _time.time()
    _timing_log = r"C:\S.A.R\interfaz_timing.txt"

    def _tw(msg):
        elapsed = _time.time() - _t0
        line = f"[{elapsed:6.1f}s] {msg}"
        print(line)
        try:
            with open(_timing_log, "a", encoding="utf-8") as _f:
                _f.write(line + "\n")
        except Exception:
            pass

    sep = "=" * 55
    _tw(sep)
    _tw("  interfaz_allegra.py — SAR Administrator")
    _tw(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _tw(sep)
    log.info("=== interfaz_allegra.py inicio ===")

    # Limpiar log de timing anterior
    try:
        open(_timing_log, "w").close()
        _tw(f"Timing log: {_timing_log}")
    except Exception:
        pass

    total = 0
    for empresa in ["02", "LP"]:
        _tw(f"--- Empresa {empresa} ---")
        total += procesar_empresa(empresa, max_por_ciclo=_leer_max_fact(empresa), _tw=_tw)
        _tw(f"--- Empresa {empresa} fin ---")

    msg = f"Total facturas procesadas: {total}"
    _tw(f"\n{msg}")
    log.info(msg)
    _tw(sep)
    _tw("Actualizando estado JSON...")
    _actualizar_estado_json(total)

    _tw("FIN")


if __name__ == "__main__":
    main()
