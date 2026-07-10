"""
configurar_allegra.py
Formulario de configuracion del modulo Alegra -> Administrator (SAR)
Tabs: Configuracion | Estado & Log
Al abrir: verifica que el daemon correcto este corriendo; si no, lo (re)inicia.

Uso: python C:\\S.A.R\\configurar_allegra.py
"""

VERSION = "2.8"

import tkinter as tk
from tkinter import ttk, messagebox
import dbf
import subprocess
import sys
import os
import struct
import ctypes
import json
from datetime import datetime

DAEMON_VERSION  = "3.0"   # debe coincidir con alegra_daemon.py
BD_ESPERADA_TXT = r"C:\S.A.R\bd_esperada.txt"
PID_FILE_PATH   = r"C:\S.A.R\alegra_daemon.pid"
DAEMON_PY       = r"C:\S.A.R\alegra_daemon.py"
DAEMON_EXE      = r"C:\S.A.R\ACTUALIZACIONES\INTERFASES\AlegraDaemon.exe"
PAUSA_FILE      = r"C:\S.A.R\alegra_daemon_pausa.txt"
LOG_REFRESH_MS  = 30_000

# ── BD esperada ───────────────────────────────────────────────────────────────
def leer_bd_esperada() -> str:
    if not os.path.exists(BD_ESPERADA_TXT):
        return ""
    try:
        return open(BD_ESPERADA_TXT, encoding="utf-8").read().strip()
    except Exception:
        return ""

def guardar_bd_esperada(ruta: str):
    open(BD_ESPERADA_TXT, "w", encoding="utf-8").write(ruta.strip())

# ── Ruta BD activa ────────────────────────────────────────────────────────────
def get_bd_path() -> str | None:
    ruta_dbf = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"
    if not os.path.exists(ruta_dbf):
        messagebox.showerror("Error", f"No se encontro:\n{ruta_dbf}")
        return None
    t = dbf.Table(ruta_dbf)
    t.open(dbf.READ_ONLY)
    ruta_dbc = t[0].ruta.strip()
    t.close()
    sep = ruta_dbc.rfind('\\')
    return ruta_dbc[:sep+1] if sep >= 0 else ruta_dbc + '\\'

def get_bd_actual_dbc() -> str:
    ruta_dbf = r"C:\S.A.R\RutaBaseDatos\ruta.dbf"
    if not os.path.exists(ruta_dbf):
        return ""
    try:
        t = dbf.Table(ruta_dbf)
        t.open(dbf.READ_ONLY)
        v = t[0].ruta.strip()
        t.close()
        return v
    except Exception:
        return ""

# ── Tablas ────────────────────────────────────────────────────────────────────
TIPOS_DOC_DEFAULT = [
    ("saleTicket", "013", "02"),
    ("saleTicket", "013", "LP"),
    ("invoice",    "",    "02"),
    ("invoice",    "",    "LP"),
    ("creditNote", "",    "02"),
    ("creditNote", "",    "LP"),
]

def _asegurar_tablas_bd(bd_path: str):
    """Crea tablas faltantes e intenta migrar allegra_pendientes si ya existe."""
    path_cfg = os.path.join(bd_path, "allegra_config.dbf")
    if not os.path.exists(path_cfg):
        try:
            cfg = dbf.Table(
                path_cfg,
                "empresa C(5); max_fact N(5,0); intervalo N(4,0); desde_ult L; ultima_sin T; "
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
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear allegra_config.dbf:\n{e}")

    path_td = os.path.join(bd_path, "alegra_tiposdoc.dbf")
    if not os.path.exists(path_td):
        try:
            td = dbf.Table(
                path_td,
                "tip_alegra C(20); tip_admin C(10); empresa C(5)",
                dbf_type="vfp",
            )
            td.open(dbf.READ_WRITE)
            for tip_alegra, tip_admin, empresa in TIPOS_DOC_DEFAULT:
                td.append((tip_alegra, tip_admin, empresa))
            td.close()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear alegra_tiposdoc.dbf:\n{e}")

    # Si la tabla existe pero no tiene filas para ambas empresas, las crea
    _asegurar_filas_config(bd_path)
    # Migrar allegra_config: agregar campos contabilización si no existen
    _migrar_allegra_config(bd_path)
    # Migrar allegra_pendientes: agregar campos de fase si no existen
    _migrar_allegra_pendientes(bd_path)
    # Crear tabla de NITs pendientes si no existe
    _asegurar_nits_pend(bd_path)


def _asegurar_filas_config(bd_path: str):
    """Inserta filas para 02 y LP en allegra_config.dbf si no existen."""
    ruta = os.path.join(bd_path, "allegra_config.dbf")
    if not os.path.exists(ruta):
        return
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        empresas_existentes = set()
        for r in t:
            if not dbf.is_deleted(r):
                empresas_existentes.add(str(r.empresa).strip())
        for emp in ["02", "LP"]:
            if emp not in empresas_existentes:
                t.append({"empresa": emp, "max_fact": 50, "intervalo": 0,
                          "desde_ult": True, "total_proc": 0,
                          "num_inicio": "", "ultimo_log": "Sin sincronizaciones aun."})
        t.close()
    except Exception as e:
        messagebox.showerror("Error", f"No se pudieron crear filas en allegra_config.dbf:\n{e}")


def _migrar_allegra_config(bd_path: str):
    """
    Agrega campos de contabilización a allegra_config.dbf si no existen.
    Recrea la tabla completa para evitar pérdida de datos con add_fields().
    """
    ruta = os.path.join(bd_path, "allegra_config.dbf")
    if not os.path.exists(ruta):
        return
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        campos = [f.lower() for f in t.field_names]
        specs_nuevos = [
            ("tip_doc", "C(10)"),
            ("met_efect",   "C(30)"),
            ("met_tarjet",  "C(30)"),
            ("met_transf",  "C(30)"),
            ("met_cxc",     "C(30)"),
            ("met_debito", "C(30)"),
            ("met_credit", "C(30)"),
            ("kw_bolsa",    "C(40)"),
            ("auto_nit",    "L"),
        ]
        nuevos_nombres = [n for n, _ in specs_nuevos if n not in campos]

        # Forzar migración si intervalo sigue siendo N(3) — ampliar a N(4)
        intervalo_angosto = False
        try:
            for fdef in t.structure():
                if fdef.lower().startswith('intervalo'):
                    intervalo_angosto = 'n(3' in fdef.lower()
                    break
        except Exception:
            pass
        if intervalo_angosto:
            nuevos_nombres = nuevos_nombres or ['_resize_intervalo']

        if nuevos_nombres:
            # Leer todos los datos antes de tocar la tabla
            backup = []
            for r in t:
                if dbf.is_deleted(r):
                    continue
                fila = {f: getattr(r, f, None) for f in campos}
                # Asegurar strings en memo
                for k, v in fila.items():
                    if hasattr(v, 'strip'):
                        fila[k] = str(v)
                backup.append(fila)
            t.close()

            # Recrear la tabla con la estructura completa
            ruta_tmp = ruta + ".migr_tmp"
            campos_todos = (
                "empresa C(5); max_fact N(5,0); intervalo N(4,0); desde_ult L; "
                "ultima_sin T; total_proc N(10,0); num_inicio C(20); ultimo_log M; "
                "tip_doc C(10); met_efect C(30); met_tarjet C(30); met_transf C(30); "
                "met_cxc C(30); met_debito C(30); met_credit C(30); kw_bolsa C(40); "
                "auto_nit L; timer_act L; ult_tick T"
            )
            nueva = dbf.Table(ruta_tmp, campos_todos, dbf_type="vfp", codepage="cp1252")
            nueva.open(dbf.READ_WRITE)
            for fila in backup:
                row = {
                    "empresa":    str(fila.get("empresa", "") or "").strip(),
                    "max_fact":   int(fila.get("max_fact", 50) or 50),
                    "intervalo":  int(fila.get("intervalo", 0) or 0),
                    "desde_ult":  bool(fila.get("desde_ult", True)),
                    "total_proc": int(fila.get("total_proc", 0) or 0),
                    "num_inicio": str(fila.get("num_inicio", "") or "").strip(),
                    "ultimo_log": str(fila.get("ultimo_log", "") or "").strip(),
                    "tip_doc":   str(fila.get("tip_doc",   "") or "").strip(),
                    "met_efect":  str(fila.get("met_efect",  "") or "").strip(),
                    "met_tarjet": str(fila.get("met_tarjet", "") or "").strip(),
                    "met_transf": str(fila.get("met_transf", "") or "").strip(),
                    "met_cxc":    str(fila.get("met_cxc",    "") or "").strip(),
                    "met_debito": str(fila.get("met_debito", "") or "").strip(),
                    "met_credit": str(fila.get("met_credit", "") or "").strip(),
                    "kw_bolsa":   str(fila.get("kw_bolsa",   "") or "").strip(),
                    "auto_nit":   bool(fila.get("auto_nit", False)),
                }
                ultima_sin = fila.get("ultima_sin")
                if ultima_sin is not None:
                    row["ultima_sin"] = ultima_sin
                ult_tick = fila.get("ult_tick")
                if ult_tick is not None:
                    row["ult_tick"] = ult_tick
                nueva.append(row)
            nueva.close()

            # Reemplazar archivo original
            fpt_viejo = ruta.replace(".dbf", ".fpt")
            fpt_tmp   = ruta_tmp.replace(".dbf", ".fpt")
            os.replace(ruta_tmp, ruta)
            if os.path.exists(fpt_tmp):
                os.replace(fpt_tmp, fpt_viejo)
        else:
            # Sin campos nuevos — solo migrar met_tarjet -> met_credit si hace falta
            for r in t:
                if dbf.is_deleted(r):
                    continue
                val_tarjet  = str(getattr(r, "met_tarjet",  "") or "").strip()
                val_tcredit = str(getattr(r, "met_credit", "") or "").strip()
                if val_tarjet and not val_tcredit:
                    with r:
                        r.met_credit = val_tarjet
            t.close()
    except Exception as e:
        import traceback
        with open(r"C:\S.A.R\migracion_error.log", "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now()}] _migrar_allegra_config: {e}\n{traceback.format_exc()}")


def _migrar_allegra_pendientes(bd_path: str):
    """Agrega campos de fase a allegra_pendientes.dbf si no existen."""
    ruta = os.path.join(bd_path, "allegra_pendientes.dbf")
    if not os.path.exists(ruta):
        return
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        campos = [f.lower() for f in t.field_names]
        specs = [("f_prod1", "L"), ("f_standar", "L"), ("f_costos", "L"),
                 ("f_contab", "L"), ("seller_id", "C(10)"), ("motivo", "C(100)"),
                 ("nomb_cli", "C(60)")]
        nuevos = [f"{n} {tp}" for n, tp in specs if n not in campos]
        if nuevos:
            t.add_fields("; ".join(nuevos))
        t.close()
    except Exception:
        pass


# ── NITs pendientes de resolución ────────────────────────────────────────────

def _asegurar_nits_pend(carpeta: str):
    """Crea alegra_nits_pend.dbf si no existe. Migra si le falta el campo nombre."""
    ruta = os.path.join(carpeta, "alegra_nits_pend.dbf")
    if not os.path.exists(ruta):
        try:
            t = dbf.Table(
                ruta,
                "nit C(20); empresa C(5); nombre C(60); num_docs C(200); accion C(10)",
                dbf_type="vfp",
            )
            t.open(dbf.READ_WRITE)
            t.close()
        except Exception:
            pass
        return
    # Migrar si existe sin campo nombre
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        if "nombre" not in [f.lower() for f in t.field_names]:
            t.add_fields("nombre C(60)")
        t.close()
    except Exception:
        pass


def _leer_nits_pend(carpeta: str) -> list:
    """Lee alegra_nits_pend.dbf — lista de dicts {nit, empresa, num_docs, accion}."""
    ruta = os.path.join(carpeta, "alegra_nits_pend.dbf")
    if not os.path.exists(ruta):
        return []
    result = []
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            result.append({
                "nit":      str(rec.nit).strip(),
                "empresa":  str(rec.empresa).strip(),
                "nombre":   str(getattr(rec, "nombre", "") or "").strip(),
                "num_docs": str(rec.num_docs).strip(),
                "accion":   str(rec.accion).strip() or "pendiente",
            })
        t.close()
    except Exception:
        pass
    return result


def _guardar_accion_nit(carpeta: str, nit: str, empresa: str, accion: str):
    """Actualiza el campo accion en alegra_nits_pend.dbf para (nit, empresa)."""
    ruta = os.path.join(carpeta, "alegra_nits_pend.dbf")
    if not os.path.exists(ruta):
        return
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if str(rec.nit).strip() == nit and str(rec.empresa).strip() == empresa:
                with rec:
                    rec.accion = accion[:10]
        t.close()
    except Exception:
        pass


# ── Leer facturas de allegra_pendientes ──────────────────────────────────────
def _leer_facturas(carpeta: str) -> dict:
    """
    Lee allegra_pendientes.dbf y devuelve tres grupos:
    {
      'pendientes':  [{...}],  # procesado=False, sin motivo — no tocadas aun
      'con_error':   [{...}],  # procesado=False, con motivo — intentadas y fallidas
      'procesadas':  [{...}],  # procesado=True
    }
    Cada factura agrupa todos sus items (empresa + factura_id unico).
    """
    result = {'pendientes': [], 'con_error': [], 'procesadas': [], 'con_alerta': []}
    ruta = os.path.join(carpeta, "allegra_pendientes.dbf")
    if not os.path.exists(ruta):
        return result
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        campos = [f.lower() for f in t.field_names]
        tiene_fases  = "f_prod1" in campos
        tiene_motivo = "motivo"  in campos

        facturas = {}
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            fid = str(rec.factura_id).strip()
            emp = str(rec.empresa).strip()
            key = (emp, fid)
            if key not in facturas:
                motivo_rec = str(getattr(rec, "motivo", "") or "").strip() if tiene_motivo else ""
                facturas[key] = {
                    "factura_id": fid,
                    "num_doc":    str(rec.num_doc).strip(),
                    "nit_cli":    str(rec.nit_cli).strip(),
                    "empresa":    emp,
                    "fecha":      str(rec.fecha)[:10] if rec.fecha else "",
                    "procesado":  bool(rec.procesado),
                    "f_prod1":    bool(getattr(rec, "f_prod1",  False)) if tiene_fases else bool(rec.procesado),
                    "f_standar":  bool(getattr(rec, "f_standar", False)) if tiene_fases else False,
                    "f_costos":   bool(getattr(rec, "f_costos",  False)) if tiene_fases else False,
                    "f_contab":   bool(getattr(rec, "f_contab",  False)) if tiene_fases else False,
                    "motivo":     motivo_rec,
                    "items":      [],
                }
            facturas[key]["items"].append({
                "cod_pro":  str(rec.cod_pro).strip(),
                "nombre":   str(rec.nombre).strip(),
                "cantidad": float(rec.cantidad),
                "precio":   float(rec.precio),
            })
        t.close()

        for fac in facturas.values():
            if fac["procesado"] and fac["motivo"]:
                result["con_alerta"].append(fac)
            elif fac["procesado"]:
                result["procesadas"].append(fac)
            elif fac["motivo"]:
                result["con_error"].append(fac)
            else:
                result["pendientes"].append(fac)

        for k in result:
            result[k].sort(key=lambda x: (x["empresa"], x["num_doc"]))
    except Exception:
        pass
    return result


def _revertir_fases_dbf(carpeta: str, factura_id: str, empresa: str, fases: list) -> tuple:
    """
    Revierte las fases indicadas en allegra_pendientes.dbf para la factura dada.
    Siempre pone procesado=False y limpia motivo para que el daemon vuelva a intentarlo.
    fases: lista de nombres de campo a resetear, ej. ['f_prod1']
    Retorna (ok, mensaje).
    """
    ruta = os.path.join(carpeta, "allegra_pendientes.dbf")
    if not os.path.exists(ruta):
        return False, "No se encontró allegra_pendientes.dbf"
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_WRITE)
        campos = [f.lower() for f in t.field_names]
        cnt = 0
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            if str(rec.factura_id).strip() != factura_id:
                continue
            if str(rec.empresa).strip() != empresa:
                continue
            with rec:
                for fase in fases:
                    if fase in campos:
                        setattr(rec, fase, False)
                rec.procesado = False
                if "motivo" in campos:
                    rec.motivo = ""
            cnt += 1
        t.close()
        if cnt == 0:
            return False, "No se encontraron registros para esa factura"
        return True, f"Fases revertidas en {cnt} item(s)"
    except Exception as e:
        return False, f"No se pudo revertir: {e}"


# ── Estadísticas de pendientes ────────────────────────────────────────────────
def _stats_pendientes(carpeta: str) -> dict:
    """
    Devuelve stats por empresa contando facturas unicas (no items).
    {
      '02': {'pendientes': N, 'f_prod1': N, 'f_standar': N, 'f_costos': N, 'f_contab': N},
      'LP': ...
    }
    """
    emps = ("02", "LP")
    base = lambda: {'pendientes': 0, 'f_prod1': 0, 'f_standar': 0, 'f_costos': 0, 'f_contab': 0}
    stats = {e: base() for e in emps}
    ruta = os.path.join(carpeta, "allegra_pendientes.dbf")
    if not os.path.exists(ruta):
        return stats
    try:
        t = dbf.Table(ruta, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        campos = [f.lower() for f in t.field_names]
        tiene_fases = "f_prod1" in campos
        vistas = set()
        for rec in t:
            if dbf.is_deleted(rec):
                continue
            emp = str(rec.empresa).strip()
            if emp not in stats:
                continue
            fid = str(rec.factura_id).strip()
            key = (emp, fid)
            if key in vistas:
                continue
            vistas.add(key)
            if not bool(rec.procesado):
                stats[emp]['pendientes'] += 1
            else:
                if tiene_fases:
                    for f in ('f_prod1', 'f_standar', 'f_costos', 'f_contab'):
                        if bool(getattr(rec, f, False)):
                            stats[emp][f] += 1
                else:
                    stats[emp]['f_prod1'] += 1  # asumir que procesado = fase1
        t.close()
    except Exception:
        pass
    return stats


# ── Sugerir num_inicio ────────────────────────────────────────────────────────

def _sugerir_num_inicio(carpeta: str, tip_docs: dict = None) -> dict:
    """
    tip_docs: {"02": "030", "LP": "031"} — tip_fac configurado por empresa.
    Solo considera registros de PROD_FACT1 cuyo tip_fac coincide.
    Si tip_doc de una empresa está vacío, esa empresa queda en "".
    """
    if tip_docs is None:
        tip_docs = {}
    resultado  = {"02": "", "LP": ""}
    diagnostico = {"fuente": None, "error": None, "registros_leidos": 0,
                   "muestra_cod_fac": [], "ruta": None}

    ruta_pf1 = os.path.join(carpeta, "PROD_FACT1.dbf")
    diagnostico["ruta"] = ruta_pf1
    diagnostico["existe"] = os.path.exists(ruta_pf1)

    if os.path.exists(ruta_pf1):
        t = None
        try:
            t = dbf.Table(ruta_pf1, codepage="cp1252")
            t.open(dbf.READ_ONLY)
            diagnostico["campos"] = [f.lower() for f in t.field_names]
            maximos     = {"02": 0, "LP": 0}
            maximos_cod = {"02": "", "LP": ""}
            muestra = []
            for rec in t:
                if dbf.is_deleted(rec):
                    continue
                diagnostico["registros_leidos"] += 1
                emp = str(rec.empresa).strip()
                if emp not in maximos:
                    continue
                tip_cfg = tip_docs.get(emp, "").strip().upper()
                if not tip_cfg:
                    continue  # empresa sin tipo de documento configurado
                tip_rec = str(rec.tip_fac).strip().upper()
                if tip_rec != tip_cfg:
                    continue
                cod = str(rec.cod_fac).strip().upper()
                # Solo considerar códigos con prefijo de letras (Alegra)
                # Los manuales de Administrator son puramente numéricos
                if not any(c.isalpha() for c in cod):
                    continue
                if len(muestra) < 3:
                    muestra.append(f"emp={emp} tip_fac={tip_rec} cod_fac={cod}")
                digits = ''.join(c for c in cod if c.isdigit())
                n = int(digits) if digits else 0
                if n > maximos[emp]:
                    maximos[emp] = n
                    maximos_cod[emp] = cod
            diagnostico["muestra_cod_fac"] = muestra
            for emp in ("02", "LP"):
                if maximos_cod[emp]:
                    resultado[emp] = maximos_cod[emp]
            diagnostico["fuente"] = "PROD_FACT1"
        except Exception as e:
            diagnostico["error"] = str(e)
        finally:
            if t is not None:
                try: t.close()
                except Exception: pass

    resultado["_diagnostico"] = diagnostico
    return resultado


# ── Config DBF ────────────────────────────────────────────────────────────────
def _config_defaults():
    return {
        'max_fact': 50, 'intervalo': 0, 'num_inicio': '',
        'ultima_sin': None, 'total_proc': 0,
        'ultimo_log': 'Sin sincronizaciones aun.',
        'tip_doc': '', 'met_efect': '', 'met_tarjet': '', 'met_debito': '', 'met_credit': '', 'met_transf': '', 'met_cxc': '',
        'auto_nit': False,
    }

def leer_config(cfg_path):
    datos = {}
    try:
        t = dbf.Table(cfg_path, codepage="cp1252")
        t.open(dbf.READ_ONLY)
        campos = [f.lower() for f in t.field_names]
        for r in t:
            if dbf.is_deleted(r):
                continue
            emp = r.empresa.strip()
            datos[emp] = {
                'max_fact':    r.max_fact,
                'intervalo':   r.intervalo,
                'num_inicio':  r.num_inicio.strip(),
                'ultima_sin':  r.ultima_sin,
                'total_proc':  r.total_proc,
                'ultimo_log':  r.ultimo_log.strip() if hasattr(r.ultimo_log, 'strip') else str(r.ultimo_log),
                'tip_doc': str(getattr(r, 'tip_doc', '') or '').strip() if 'tip_doc' in campos else '',
                'met_efect':   str(getattr(r, 'met_efect',   '') or '').strip() if 'met_efect'   in campos else '',
                'met_tarjet':  str(getattr(r, 'met_tarjet',  '') or '').strip() if 'met_tarjet'  in campos else '',
                'met_debito': str(getattr(r, 'met_debito', '') or '').strip() if 'met_debito' in campos else '',
                'met_credit': str(getattr(r, 'met_credit', '') or '').strip() if 'met_credit' in campos else '',
                'met_transf':  str(getattr(r, 'met_transf',  '') or '').strip() if 'met_transf'  in campos else '',
                'met_cxc':     str(getattr(r, 'met_cxc',     '') or '').strip() if 'met_cxc'     in campos else '',
                'kw_bolsa':    str(getattr(r, 'kw_bolsa',    '') or '').strip() if 'kw_bolsa'    in campos else '',
                'auto_nit':    bool(getattr(r, 'auto_nit', False))              if 'auto_nit'   in campos else False,
            }
        t.close()
    except Exception:
        pass
    # Rellenar empresas faltantes con defaults — nunca fallar por tabla vacía
    for emp in ('02', 'LP'):
        if emp not in datos:
            datos[emp] = _config_defaults()
    return datos

def guardar_config(cfg_path, max_fact, intervalo, num_inicio_02, num_inicio_lp,
                   per_empresa=None, kw_bolsa="", auto_nit=False):
    """
    per_empresa: dict por empresa con claves tip_doc, met_efect, met_tarjet,
                 met_transf, met_cxc.  Ej: {"02": {...}, "LP": {...}}
    kw_bolsa: palabra clave global para detectar ítems de impuesto de bolsa (ej. "BOLSA")
    """
    if per_empresa is None:
        per_empresa = {}
    t = dbf.Table(cfg_path, codepage="cp1252")
    t.open(dbf.READ_WRITE)
    campos = [f.lower() for f in t.field_names]

    # Índice de empresas ya presentes
    empresas_en_tabla = set()
    for r in t:
        if not dbf.is_deleted(r):
            empresas_en_tabla.add(r.empresa.strip())

    # Actualizar filas existentes
    for r in t:
        if dbf.is_deleted(r):
            continue
        emp = r.empresa.strip()
        d   = per_empresa.get(emp, {})
        with r:
            r.max_fact  = max_fact
            r.intervalo = intervalo
            r.desde_ult = True
            if emp == '02':
                r.num_inicio = num_inicio_02.upper()
            elif emp == 'LP':
                r.num_inicio = num_inicio_lp.upper()
            if 'tip_doc' in campos: r.tip_doc = d.get('tip_doc', '').strip()[:10]
            if 'met_efect'   in campos: r.met_efect   = d.get('met_efect',   '').strip()[:30]
            if 'met_tarjet'  in campos: r.met_tarjet  = d.get('met_tarjet',  '').strip()[:30]
            if 'met_debito' in campos: r.met_debito = d.get('met_debito', '').strip()[:30]
            if 'met_credit' in campos: r.met_credit = d.get('met_credit', '').strip()[:30]
            if 'met_transf'  in campos: r.met_transf  = d.get('met_transf',  '').strip()[:30]
            if 'met_cxc'     in campos: r.met_cxc     = d.get('met_cxc',     '').strip()[:30]
            if 'kw_bolsa'    in campos: r.kw_bolsa    = kw_bolsa.strip()[:40]
            if 'auto_nit'    in campos: r.auto_nit    = bool(auto_nit)

    # Insertar filas faltantes
    num_map = {'02': num_inicio_02, 'LP': num_inicio_lp}
    for emp in ('02', 'LP'):
        if emp in empresas_en_tabla:
            continue
        d = per_empresa.get(emp, {})
        row = {"empresa": emp, "max_fact": max_fact, "intervalo": intervalo,
               "desde_ult": True, "total_proc": 0,
               "num_inicio": num_map.get(emp, '').upper(),
               "ultimo_log": "Sin sincronizaciones aun."}
        if 'tip_doc' in campos: row['tip_doc'] = d.get('tip_doc', '').strip()[:10]
        if 'met_efect'   in campos: row['met_efect']   = d.get('met_efect',   '').strip()[:30]
        if 'met_tarjet'  in campos: row['met_tarjet']  = d.get('met_tarjet',  '').strip()[:30]
        if 'met_debito' in campos: row['met_debito'] = d.get('met_debito', '').strip()[:30]
        if 'met_credit' in campos: row['met_credit'] = d.get('met_credit', '').strip()[:30]
        if 'met_transf'  in campos: row['met_transf']  = d.get('met_transf',  '').strip()[:30]
        if 'met_cxc'     in campos: row['met_cxc']     = d.get('met_cxc',     '').strip()[:30]
        if 'kw_bolsa'    in campos: row['kw_bolsa']    = kw_bolsa.strip()[:40]
        if 'auto_nit'    in campos: row['auto_nit']    = bool(auto_nit)
        t.append(row)

    t.close()
    tip_docs = {emp: per_empresa.get(emp, {}).get('tip_doc', '') for emp in ('02', 'LP')}

    # Sincronizar alegra_tiposdoc: saleTicket → tip_doc configurado por empresa
    carpeta = os.path.dirname(cfg_path)
    ruta_td = os.path.join(carpeta, "alegra_tiposdoc.dbf")
    if os.path.exists(ruta_td):
        try:
            td = dbf.Table(ruta_td, codepage="cp1252")
            td.open(dbf.READ_WRITE)
            for rec in td:
                if dbf.is_deleted(rec):
                    continue
                if str(rec.tip_alegra).strip() != "saleTicket":
                    continue
                emp = str(rec.empresa).strip()
                nuevo_tip = tip_docs.get(emp, "").strip()
                if nuevo_tip and str(rec.tip_admin).strip() != nuevo_tip:
                    with rec:
                        rec.tip_admin = nuevo_tip[:10]
            td.close()
        except Exception as e:
            pass  # no bloquear guardado si falla la sincronización

    _actualizar_estado_json(cfg_path, max_fact, intervalo, num_inicio_02, num_inicio_lp, tip_docs)


JSON_PATH = r"C:\S.A.R\estado_proceso.json"
PID_FILE  = r"C:\S.A.R\alegra_daemon.pid"


def _pid_vivo(pid):
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong(0)
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259
    except Exception:
        return False


def _actualizar_daemon_json():
    """Actualiza solo el bloque 'daemon' en estado_proceso.json."""
    try:
        try:
            with open(JSON_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

        pid = None
        try:
            pid = int(open(PID_FILE, encoding="utf-8").readline().strip())
        except Exception:
            pass

        pausado   = os.path.exists(PAUSA_FILE)
        corriendo = _pid_vivo(pid) if pid else False

        data["daemon"] = {
            "estado":               "pausado" if pausado else ("corriendo" if corriendo else "detenido"),
            "pid":                  pid,
            "archivo_pausa":        PAUSA_FILE,
            "fallback_intervalo_min": 5
        }
        data["_actualizado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _actualizar_estado_json(cfg_path, max_fact, intervalo, num_inicio_02, num_inicio_lp, tip_docs=None):
    """Actualiza config + estado daemon en estado_proceso.json tras guardar config."""
    try:
        try:
            with open(JSON_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

        data["_actualizado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Sugeridos desde PROD_FACT1 — diagnóstico
        carpeta = os.path.dirname(cfg_path)
        sugeridos = {}
        diag = {}
        try:
            res = _sugerir_num_inicio(carpeta, tip_docs or {})
            diag = res.pop("_diagnostico", {})
            sugeridos = res
        except Exception as e:
            diag = {"error": str(e)}

        # Leer todo el DBF para monitoreo completo
        allegra_cfg_rows = []
        try:
            t = dbf.Table(cfg_path, codepage="cp1252")
            t.open(dbf.READ_ONLY)
            campos_t = [f.lower() for f in t.field_names]
            for r in t:
                if dbf.is_deleted(r): continue
                emp = str(r.empresa).strip()
                row = {
                    "empresa":     emp,
                    "max_fact":    int(r.max_fact or 0),
                    "intervalo":   int(r.intervalo or 0),
                    "num_inicio":  str(r.num_inicio).strip(),
                    "num_sugerido": sugeridos.get(emp, ""),
                    "tip_doc": str(getattr(r, 'tip_doc', '') or '').strip() if 'tip_doc' in campos_t else '—',
                    "met_efect":   str(getattr(r, 'met_efect',   '') or '').strip() if 'met_efect'   in campos_t else '—',
                    "met_debito": str(getattr(r, 'met_debito', '') or '').strip() if 'met_debito' in campos_t else '—',
                    "met_credit": str(getattr(r, 'met_credit', '') or '').strip() if 'met_credit' in campos_t else '—',
                    "met_transf":  str(getattr(r, 'met_transf',  '') or '').strip() if 'met_transf'  in campos_t else '—',
                    "met_cxc":     str(getattr(r, 'met_cxc',     '') or '').strip() if 'met_cxc'     in campos_t else '—',
                    "kw_bolsa":    str(getattr(r, 'kw_bolsa',    '') or '').strip() if 'kw_bolsa'    in campos_t else '—',
                }
                allegra_cfg_rows.append(row)
            t.close()
            data["allegra_config_campos"] = campos_t
        except Exception as e:
            allegra_cfg_rows = [{"error": str(e)}]

        data["allegra_config"] = allegra_cfg_rows
        data["num_inicio_diagnostico"] = diag

        # Estado daemon al momento de guardar
        pid = None
        try:
            pid = int(open(PID_FILE, encoding="utf-8").readline().strip())
        except Exception:
            pass
        pausado   = os.path.exists(PAUSA_FILE)
        corriendo = _pid_vivo(pid) if pid else False
        data["daemon"] = {
            "estado":               "pausado" if pausado else ("corriendo" if corriendo else "detenido"),
            "pid":                  pid,
            "archivo_pausa":        PAUSA_FILE,
            "fallback_intervalo_min": 5
        }

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ── Daemon ────────────────────────────────────────────────────────────────────
def _leer_pid_version():
    if not os.path.exists(PID_FILE_PATH):
        return None, None
    try:
        lineas = open(PID_FILE_PATH, encoding="utf-8").read().strip().splitlines()
        pid = int(lineas[0]) if lineas else None
        ver = lineas[1].strip() if len(lineas) > 1 else None
        return pid, ver
    except Exception:
        return None, None

def _proceso_vivo(pid: int) -> bool:
    if pid is None:
        return False
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong(0)
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259
    except Exception:
        return False

def _matar_daemons_viejos():
    # Matar por PID conocido
    pid, _ = _leer_pid_version()
    if pid and _proceso_vivo(pid):
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"],
                           capture_output=True)
        except Exception:
            pass

    # Matar cualquier proceso Python corriendo nuestros scripts (daemon + subprocesos hijos)
    scripts = ["alegra_daemon", "allegra_sync", "interfaz_allegra"]
    for script in scripts:
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-WmiObject Win32_Process | "
                 f"Where-Object {{$_.Name -like '*python*' -and $_.CommandLine -like '*{script}*'}} | "
                 f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass

    # Matar exe compilado si existe
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Stop-Process -Name AlegraDaemon -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)
    import time; time.sleep(1)

def _iniciar_daemon():
    import shutil
    # v3.0: preferir EXE; fallback a script Python (v2.8)
    if os.path.exists(DAEMON_EXE):
        try:
            subprocess.Popen([DAEMON_EXE],
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
            return True, "OK"
        except Exception as e:
            return False, str(e)
    pw = shutil.which("pythonw") or shutil.which("python") or sys.executable
    if not os.path.exists(DAEMON_PY):
        return False, f"No encontrado: {DAEMON_EXE} ni {DAEMON_PY}"
    try:
        subprocess.Popen([pw, DAEMON_PY],
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
        return True, "OK"
    except Exception as e:
        return False, str(e)

def _estado_daemon() -> tuple[bool, str]:
    pid, ver = _leer_pid_version()
    if pid and _proceso_vivo(pid):
        return True, f"Activo  v{ver}  (PID {pid})"
    return False, "Inactivo"

def _asegurar_daemon() -> str:
    pid, ver = _leer_pid_version()
    if pid and _proceso_vivo(pid) and ver == DAEMON_VERSION:
        return f"Activo  v{ver}  (PID {pid})"
    _matar_daemons_viejos()
    ok, msg = _iniciar_daemon()
    if not ok:
        return f"ERROR: {msg}"
    import time
    for _ in range(6):
        time.sleep(0.5)
        pid2, ver2 = _leer_pid_version()
        if pid2 and _proceso_vivo(pid2):
            return f"Iniciado  v{ver2}  (PID {pid2})"
    return "Iniciando..."


# ── Escritura binaria en TERCEROS ─────────────────────────────────────────────

def _leer_estructura_dbf(ruta: str):
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


def _crear_tercero_bin(carpeta: str, nit: str, nombre: str,
                       ciudad: str, empresa: str) -> tuple:
    """
    Crea un nuevo TERCERO en TERCEROS.dbf via escritura binaria directa.
    Evita el problema del .fpt huerfano que impide abrir con la libreria dbf.
    Retorna (ok: bool, mensaje: str, cod_ter: int).
    """
    ruta = os.path.join(carpeta, "TERCEROS.dbf")
    if not os.path.exists(ruta):
        return False, "No se encontro TERCEROS.dbf", 0
    try:
        num_rec, hdr_size, rec_size, campos = _leer_estructura_dbf(ruta)
        campo_map = {c[0]: (c[2], c[3], c[4], c[1]) for c in campos}

        # MAX(COD_TER)
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

        nuevo_cod = max_cod + 1
        now = datetime.now()

        # Construir registro binario
        registro = bytearray(rec_size)
        registro[0] = 0x20  # no borrado

        def poner_n(campo, valor):
            if campo not in campo_map:
                return
            off, sz, dec, _ = campo_map[campo]
            s = format(float(valor), f'{sz}.{dec}f') if dec else str(int(valor))
            registro[off:off+sz] = s.rjust(sz).encode('cp1252')

        def poner_c(campo, valor):
            if campo not in campo_map:
                return
            off, sz, _, _ = campo_map[campo]
            registro[off:off+sz] = str(valor).ljust(sz)[:sz].encode('cp1252')

        def poner_t(campo, dt):
            if campo not in campo_map:
                return
            off = campo_map[campo][0]
            jd  = dt.toordinal() + 1721425
            ms  = (dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000
            registro[off:off+8] = struct.pack('<II', jd, ms)

        poner_n('COD_TER',    nuevo_cod)
        poner_c('NOMBRE',     nombre[:50])
        poner_c('IDENTIFICA', nit[:15])
        poner_c('CIUDAD',     ciudad[:20])
        poner_n('ESTADO',     0)
        poner_n('USUARIO',    1)
        poner_c('EMPRESA',    empresa[:6])
        poner_t('FECHA_HORA', now)
        poner_n('TIPO',       0)
        poner_n('CUPO',       0)
        poner_n('NUM_CUE',    0)

        # Escribir al final del archivo + actualizar contador
        offset_nuevo = hdr_size + num_rec * rec_size
        with open(ruta, 'r+b') as f:
            f.seek(4)
            f.write(struct.pack('<I', num_rec + 1))
            f.seek(offset_nuevo)
            f.write(bytes(registro))
            f.write(b'\x1A')  # EOF marker

        return True, f"TERCERO creado: COD_TER={nuevo_cod}", nuevo_cod

    except Exception as e:
        return False, f"Error al crear TERCERO: {e}", 0


# ── Dialogo — crear nuevo TERCERO ─────────────────────────────────────────────

class _DialogRevertirFases(tk.Toplevel):
    """
    Diálogo para seleccionar qué fases revertir en una factura procesada.
    fases_disp: [(campo, descripcion), ...]
    result: lista de campos seleccionados, o None si canceló.
    """
    def __init__(self, parent, num_doc: str, empresa: str, fases_disp: list):
        super().__init__(parent)
        self.title("Revertir fases de factura")
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        tk.Label(self, text=f"Factura: {num_doc}  |  Empresa: {empresa}",
                 font=("Arial", 10, "bold")).pack(padx=16, pady=(14, 4))
        tk.Label(self, text="Seleccione las fases a revertir:",
                 font=("Arial", 9)).pack(padx=16, pady=(0, 6))

        self._vars = {}
        frm = tk.Frame(self)
        frm.pack(padx=20, pady=4, fill="x")
        for campo, desc in fases_disp:
            var = tk.BooleanVar(value=False)
            self._vars[campo] = var
            tk.Checkbutton(frm, text=desc, variable=var,
                           font=("Arial", 9)).pack(anchor="w", pady=2)

        tk.Label(self,
                 text="La factura volverá a 'Pendientes' y el daemon\nla procesará en el próximo ciclo.",
                 font=("Arial", 8), fg="#666").pack(padx=16, pady=(6, 2))

        btn_row = tk.Frame(self)
        btn_row.pack(pady=(8, 12))
        tk.Button(btn_row, text="Revertir", width=12,
                  command=self._ok).pack(side="left", padx=6)
        tk.Button(btn_row, text="Cancelar", width=12,
                  command=self.destroy).pack(side="left", padx=6)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{x}+{y}")

    def _ok(self):
        self.result = [campo for campo, var in self._vars.items() if var.get()]
        self.destroy()


class _DialogCrearTercero(tk.Toplevel):
    def __init__(self, parent, nit: str, empresa: str, nombre_alegra: str = ""):
        super().__init__(parent)
        self.title("Crear nuevo TERCERO en Administrator")
        self.resizable(False, False)
        self.grab_set()
        self.result = None   # (nombre, ciudad) si OK, None si Cancel

        PAD = dict(padx=12, pady=5)

        tk.Label(self, text="Nuevo TERCERO en Administrator",
                 font=("Arial", 11, "bold"), fg="#00468c").grid(
                 row=0, column=0, columnspan=2, pady=(14, 6))

        tk.Label(self, text="NIT:", anchor="e", width=10,
                 font=("Arial", 9)).grid(row=1, column=0, **PAD, sticky="e")
        tk.Label(self, text=nit, font=("Arial", 9, "bold"),
                 fg="#333").grid(row=1, column=1, **PAD, sticky="w")

        tk.Label(self, text="Empresa:", anchor="e", width=10,
                 font=("Arial", 9)).grid(row=2, column=0, **PAD, sticky="e")
        tk.Label(self, text=empresa, font=("Arial", 9),
                 fg="#333").grid(row=2, column=1, **PAD, sticky="w")

        tk.Label(self, text="Nombre *:", anchor="e", width=10,
                 font=("Arial", 9)).grid(row=3, column=0, **PAD, sticky="e")
        self.var_nombre = tk.StringVar(value=nombre_alegra)
        self._e_nombre = tk.Entry(self, textvariable=self.var_nombre,
                                  width=36, font=("Arial", 9))
        self._e_nombre.grid(row=3, column=1, **PAD, sticky="w")
        if nombre_alegra:
            tk.Label(self, text="(nombre de origen — puede editarlo)",
                     font=("Arial", 7, "italic"), fg="#888").grid(
                     row=3, column=1, sticky="sw", padx=12)

        tk.Label(self, text="Ciudad:", anchor="e", width=10,
                 font=("Arial", 9)).grid(row=4, column=0, **PAD, sticky="e")
        self.var_ciudad = tk.StringVar(value="CALI")
        tk.Entry(self, textvariable=self.var_ciudad,
                 width=22, font=("Arial", 9)).grid(row=4, column=1, **PAD, sticky="w")

        frame_btns = tk.Frame(self)
        frame_btns.grid(row=5, column=0, columnspan=2, pady=(6, 14))
        tk.Button(frame_btns, text="Crear", width=11,
                  bg="#007700", fg="white", font=("Arial", 9, "bold"),
                  command=self._ok).pack(side="left", padx=6)
        tk.Button(frame_btns, text="Cancelar", width=11,
                  font=("Arial", 9), command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(100, self._e_nombre.focus_set)

    def _ok(self):
        nombre = self.var_nombre.get().strip().upper()
        if not nombre:
            messagebox.showwarning("Crear TERCERO", "El nombre es obligatorio.", parent=self)
            return
        self.result = (nombre, self.var_ciudad.get().strip().upper())
        self.destroy()


# ── Aplicacion ────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"ADMINISTRATOR INTERFASES  v{VERSION}")
        self.resizable(True, True)
        self.minsize(500, 120)

        # ── Splash de carga — visible de inmediato ────────────────────────────
        self._frm_splash = tk.Frame(self, bg="#00468c")
        self._frm_splash.pack(fill="both", expand=True)
        tk.Label(self._frm_splash, text=f"ADMINISTRATOR INTERFASES  v{VERSION}",
                 font=("Arial", 13, "bold"), fg="white", bg="#00468c").pack(pady=(30, 6))
        self._lbl_cargando = tk.Label(self._frm_splash, text="Iniciando...",
                 font=("Arial", 10), fg="#aad4ff", bg="#00468c")
        self._lbl_cargando.pack()
        self.update()   # forzar render antes de continuar

        self.after(50, self._init_async)  # diferir init pesado

    def _set_cargando(self, msg: str):
        self._lbl_cargando.config(text=msg)
        self.update()

    def _init_async(self):
        self._set_cargando("Leyendo ruta de base de datos...")
        carpeta = get_bd_path()
        if not carpeta:
            self.destroy()
            return

        self.cfg_path = carpeta + "allegra_config.dbf"
        self.carpeta  = carpeta.rstrip("\\")

        self._set_cargando("Verificando tablas...")
        _asegurar_tablas_bd(self.carpeta)

        if not os.path.exists(self.cfg_path):
            messagebox.showerror("Error", f"No se encontro allegra_config.dbf en:\n{carpeta}")
            self.destroy()
            return

        self._set_cargando("Leyendo configuracion...")
        datos = leer_config(self.cfg_path)

        d02 = datos['02']
        dLP = datos['LP']

        self._set_cargando("Consultando PROD_FACT1...")
        tip_docs = {"02": d02.get("tip_doc", ""), "LP": dLP.get("tip_doc", "")}
        sugeridos = _sugerir_num_inicio(self.carpeta, tip_docs)
        sugeridos.pop("_diagnostico", None)
        for emp, d in [("02", d02), ("LP", dLP)]:
            sug = sugeridos.get(emp, "")
            if not sug:
                continue
            sug_n = int(''.join(c for c in sug if c.isdigit()) or "0")
            act_n = int(''.join(c for c in d['num_inicio'] if c.isdigit()) or "0")
            if not d['num_inicio'] or sug_n > act_n:
                d['num_inicio'] = sug

        self.num_inicio_02_orig = d02.get('num_inicio', '')
        self.num_inicio_lp_orig = dLP.get('num_inicio', '')
        self.bd_actual_dbc = get_bd_actual_dbc()

        self._set_cargando("Construyendo interfaz...")
        self._frm_splash.destroy()
        self._construir_ui(d02, dLP)

        # Posicionar y limitar ventana al alto de pantalla disponible
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        alto_max = sh - 60  # margen para barra de tareas
        ww = max(self.winfo_width(), 900)
        self.geometry(f"{ww}x{alto_max}+{max(0,(sw-ww)//2)}+10")

        # Escribir JSON al abrir — captura estado real incluyendo sugeridos
        _actualizar_estado_json(self.cfg_path, d02['max_fact'], d02['intervalo'],
                                d02['num_inicio'], dLP['num_inicio'],
                                {"02": d02.get("tip_doc", ""), "LP": dLP.get("tip_doc", "")})
        self._marcar_ventana_abierta(True)
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self._programar_refresh()

    def _al_cerrar(self):
        self._marcar_ventana_abierta(False)
        self.destroy()

    def _marcar_ventana_abierta(self, abierta: bool):
        try:
            with open(JSON_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["ventana"] = {
            "abierta":  abierta,
            "version":  VERSION,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            with open(JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ── UI ────────────────────────────────────────────────────────────────────

    def _construir_ui(self, d02, dLP):
        PAD = dict(padx=8, pady=3)

        # ── Barra de control global (siempre visible) ─────────────────────────
        barra = tk.Frame(self, bd=1, relief="groove", bg="#f0f0f0")
        barra.pack(fill="x", padx=8, pady=(6, 2))

        # Indicador de estado
        pausado      = os.path.exists(PAUSA_FILE)
        estado_daemon = _asegurar_daemon()
        activo       = any(w in estado_daemon for w in ("Activo", "Iniciado", "Iniciando"))
        if pausado:
            est_texto, est_color = "Pausado", "#cc6600"
        elif activo:
            est_texto, est_color = "Activo", "#007700"
        else:
            est_texto, est_color = "Detenido", "#cc0000"

        _, ver_daemon_real = _leer_pid_version()
        ver_daemon_txt = f"v{ver_daemon_real}" if ver_daemon_real else "v?"

        tk.Label(barra, text="Proceso:", font=("Arial", 9, "bold"),
                 bg="#f0f0f0").pack(side="left", padx=(8, 2), pady=4)
        self.lbl_daemon = tk.Label(barra, text=f"{est_texto} {ver_daemon_txt}",
                                   font=("Arial", 9, "bold"),
                                   fg=est_color, bg="#f0f0f0", width=14)
        self.lbl_daemon.pack(side="left", padx=(0, 8), pady=4)

        ttk.Separator(barra, orient="vertical").pack(side="left", fill="y", pady=4)

        self.btn_pausa = tk.Button(
            barra,
            text="Reanudar" if pausado else "Pausar",
            width=10,
            bg="#cc6600" if pausado else "#555",
            fg="white",
            font=("Arial", 9),
            command=self.toggle_pausa,
        )
        self.btn_pausa.pack(side="left", padx=8, pady=4)

        ttk.Separator(barra, orient="vertical").pack(side="left", fill="y", pady=4)

        self.btn_un_ciclo = tk.Button(barra, text="▶ Un ciclo", width=10, bg="#1a6b2a", fg="white",
                  font=("Arial", 9), command=self.correr_un_ciclo)
        self.btn_un_ciclo.pack(side="left", padx=8, pady=4)

        ttk.Separator(barra, orient="vertical").pack(side="left", fill="y", pady=4)

        tk.Button(barra, text="Cerrar", width=8,
                  font=("Arial", 9), command=self.destroy).pack(side="right", padx=8, pady=4)
        tk.Label(barra, text=f"v{VERSION} / daemon v{DAEMON_VERSION}",
                 font=("Arial", 8), fg="#888", bg="#f0f0f0").pack(side="right", padx=4, pady=4)

        # Banda de modo activo
        self.lbl_modo = tk.Label(self, font=("Arial", 8), anchor="w",
                                 bg="#eef4ee", fg="#1a6b2a", relief="flat", padx=10, pady=2)
        self.lbl_modo.pack(fill="x")
        self._actualizar_lbl_modo()

        # Notebook
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=6)

        # ── Tab 1: Configuracion (con scroll) ────────────────────────────────
        tab_cfg = ttk.Frame(nb)
        nb.add(tab_cfg, text="  Configuracion  ")
        tab_cfg.rowconfigure(0, weight=1)
        tab_cfg.columnconfigure(0, weight=1)

        # Barra fija inferior — siempre visible, fuera del scroll
        barra_cfg = tk.Frame(tab_cfg, bd=1, relief="groove", bg="#f0f0f0")
        barra_cfg.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 4))
        self.lbl_cambios = tk.Label(barra_cfg, text="", font=("Arial", 9, "bold"),
                                    bg="#f0f0f0", width=28, anchor="w")
        self.lbl_cambios.pack(side="left", padx=(10, 4), pady=4)
        tk.Button(barra_cfg, text="Guardar configuracion", width=20,
                  bg="#0064b4", fg="white", font=("Arial", 9, "bold"),
                  command=self.guardar).pack(side="left", padx=4, pady=4)

        _canvas = tk.Canvas(tab_cfg, borderwidth=0, highlightthickness=0)
        _vsb    = ttk.Scrollbar(tab_cfg, orient="vertical", command=_canvas.yview)
        _canvas.configure(yscrollcommand=_vsb.set)
        _vsb.grid(row=0, column=1, sticky="ns")
        _canvas.grid(row=0, column=0, sticky="nsew")
        _inner  = ttk.Frame(_canvas)
        _win_id = _canvas.create_window((0, 0), window=_inner, anchor="nw")
        def _on_inner_configure(e):
            _canvas.configure(scrollregion=_canvas.bbox("all"))
        def _on_canvas_configure(e):
            _canvas.itemconfig(_win_id, width=e.width)
        _inner.bind("<Configure>", _on_inner_configure)
        _canvas.bind("<Configure>", _on_canvas_configure)
        def _on_mousewheel(e):
            _canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        def _bind_scroll(e):   _canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_scroll(e): _canvas.unbind_all("<MouseWheel>")
        _canvas.bind("<Enter>", _bind_scroll)
        _canvas.bind("<Leave>", _unbind_scroll)
        self._tab_configuracion(_inner, d02, dLP, PAD)

        # ── Tab 2: Facturas ───────────────────────────────────────────────────
        tab_fac = ttk.Frame(nb)
        nb.add(tab_fac, text="  Facturas  ")
        try:
            self._tab_facturas(tab_fac)
        except Exception as e:
            tk.Label(tab_fac, text=f"Error: {e}", fg="red").pack(padx=10, pady=10)

        # ── Tab 3: Terceros pendientes ────────────────────────────────────────
        tab_ter = ttk.Frame(nb)
        nb.add(tab_ter, text="  Terceros  ")
        try:
            self._tab_terceros(tab_ter)
        except Exception as e:
            tk.Label(tab_ter, text=f"Error: {e}", fg="red").pack(padx=10, pady=10)

        # ── Tab 4: Estado & Log ───────────────────────────────────────────────
        tab_est = ttk.Frame(nb)
        nb.add(tab_est, text="  Estado & Log  ")
        try:
            self._tab_estado(tab_est, d02)
        except Exception as e:
            tk.Label(tab_est, text=f"Error: {e}", fg="red").pack(padx=10, pady=10)

    def _actualizar_num_sugerido(self, emp_key: str):
        """Lee MAX cod_fac de PROD_FACT1 filtrado por tip_fac del documento seleccionado."""
        lbl = self._lbl_sugerido.get(emp_key)
        if not lbl:
            return
        cod_map = self._tip_doc_map.get(emp_key, {})
        display = self._vars_tip_doc.get(emp_key, tk.StringVar()).get().strip()
        tip_doc = cod_map.get(display, "").strip().upper()
        if not tip_doc:
            lbl.config(text="")
            return
        try:
            ruta = os.path.join(self.carpeta, "PROD_FACT1.dbf")
            if not os.path.exists(ruta):
                lbl.config(text="PROD_FACT1 no encontrado", fg="#cc0000")
                return
            t = dbf.Table(ruta, codepage="cp1252")
            t.open(dbf.READ_ONLY)
            max_n   = 0
            max_cod = ""
            for r in t:
                if dbf.is_deleted(r): continue
                if str(r.tip_fac).strip().upper() != tip_doc: continue
                cod = str(r.cod_fac).strip().upper()
                if not any(c.isalpha() for c in cod):
                    continue  # ignorar códigos puramente numéricos (facturas manuales VFP)
                digits = ''.join(c for c in cod if c.isdigit())
                n = int(digits) if digits else 0
                if n > max_n:
                    max_n   = n
                    max_cod = cod
            t.close()
            if max_cod:
                lbl.config(text=f"Sugerido: {max_cod}", fg="#27ae60")
                var = self._vars_num_ini.get(emp_key)
                if var and not var.get().strip():
                    var.set(max_cod)
            else:
                lbl.config(text=f"Sin registros Alegra para tipo {tip_doc}", fg="#888")
        except Exception as e:
            lbl.config(text=f"Error: {e}", fg="#cc0000")

    def _marcar_cambio(self, *_):
        if hasattr(self, 'lbl_cambios'):
            self.lbl_cambios.config(text="● Cambios sin guardar", fg="#cc4400")

    def _enganchar_diag_traces(self):
        """Engancha traces de _vars_num_ini al diagnóstico Alegra."""
        if not hasattr(self, '_calcular_diag'):
            return
        for var in self._vars_num_ini.values():
            var.trace_add("write", lambda *_: self.after(0, self._calcular_diag))

    def _marcar_guardado(self):
        if hasattr(self, 'lbl_cambios'):
            self.lbl_cambios.config(text="✓ Guardado", fg="#007700")

    def _registrar_inputs_config(self):
        """Vincula todos los inputs de configuracion para detectar cambios."""
        vars_a_vigilar = []
        # Globales
        for v in [self.var_max, self.var_int, self.var_kw_bolsa]:
            vars_a_vigilar.append(v)
        for v in self._vars_num_ini.values():
            vars_a_vigilar.append(v)
        # Por empresa
        for emp in ("02", "LP"):
            for v in self._vars_met.get(emp, {}).values():
                vars_a_vigilar.append(v)
            vd = self._vars_tip_doc.get(emp)
            if vd:
                vars_a_vigilar.append(vd)
        for v in vars_a_vigilar:
            v.trace_add("write", self._marcar_cambio)

    def _tab_facturas(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # ── Encabezado ────────────────────────────────────────────────────────
        hdr = tk.Frame(parent)
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))
        tk.Label(hdr, text="Facturas importadas",
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(hdr, text="Refrescar", font=("Arial", 8),
                  command=self._refrescar_facturas).pack(side="right")

        # ── PanedWindow vertical con 4 paneles ────────────────────────────────
        pw = ttk.PanedWindow(parent, orient="vertical")
        pw.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 2))

        def _make_tree(frame, cols_def, height=5):
            """cols_def = [(id, label, width, anchor), ...]"""
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            ids   = [c[0] for c in cols_def]
            tree  = ttk.Treeview(frame, columns=ids, show="tree headings",
                                  selectmode="browse", height=height)
            tree.column("#0", width=18, stretch=False)
            for cid, lbl, w, anc in cols_def:
                tree.column(cid, width=w, anchor=anc)
                tree.heading(cid, text=lbl)
            sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.grid(row=0, column=0, sticky="nsew")
            sb.grid(row=0, column=1, sticky="ns")
            tree.tag_configure("item_row", foreground="#555555", background="#fafafa")
            return tree

        # Panel 1 — Pendientes (no tocadas)
        frm_pend = ttk.LabelFrame(pw, text="  Pendientes de procesar  ")
        cols_pend = [
            ("empresa", "Empresa",  55, "center"),
            ("num_doc", "Num Doc",  90, "w"),
            ("nit",     "NIT",     110, "w"),
            ("fecha",   "Fecha",    80, "center"),
            ("items",   "Items",    45, "center"),
        ]
        self.tree_pend = _make_tree(frm_pend, cols_pend)
        pw.add(frm_pend, weight=1)

        # Panel 2 — Con inconsistencias (intentadas, no procesadas)
        frm_err = ttk.LabelFrame(pw, text="  No procesadas — con inconsistencias  ")
        cols_err = [
            ("empresa", "Empresa",  55, "center"),
            ("num_doc", "Num Doc",  90, "w"),
            ("nit",     "NIT",     110, "w"),
            ("fecha",   "Fecha",    80, "center"),
            ("items",   "Items",    45, "center"),
            ("motivo",  "Motivo",  220, "w"),
        ]
        self.tree_err = _make_tree(frm_err, cols_err)
        self.tree_err.tag_configure("err_row", foreground="#cc4400")
        pw.add(frm_err, weight=1)

        # Panel 3 — Procesadas
        frm_proc = ttk.LabelFrame(pw, text="  Procesadas en Administrator  ")
        cols_proc = [
            ("empresa", "Empresa",   55, "center"),
            ("num_doc", "Num Doc",   90, "w"),
            ("nit",     "NIT",      110, "w"),
            ("fecha",   "Fecha",     80, "center"),
            ("items",   "Items",     45, "center"),
            ("prod1",   "PROD_FACT1", 70, "center"),
            ("standar", "REG_PROD",  70, "center"),
            ("costos",  "Costos",    70, "center"),
            ("contab",  "Contabilidad", 80, "center"),
        ]
        self.tree_proc = _make_tree(frm_proc, cols_proc)
        self.tree_proc.tag_configure("ok_row", foreground="#007700")
        pw.add(frm_proc, weight=1)

        # Panel 4 — Procesadas con alertas (procesado=True, motivo != '')
        frm_alerta = ttk.LabelFrame(pw, text="  Procesadas con alertas  ")
        cols_alerta = [
            ("empresa", "Empresa",  55, "center"),
            ("num_doc", "Num Doc",  90, "w"),
            ("nit",     "NIT",     110, "w"),
            ("fecha",   "Fecha",    80, "center"),
            ("items",   "Items",    45, "center"),
            ("motivo",  "Alerta",  280, "w"),
        ]
        self.tree_alerta = _make_tree(frm_alerta, cols_alerta)
        self.tree_alerta.tag_configure("alerta_row", foreground="#996600")
        pw.add(frm_alerta, weight=1)
        self.after(100, lambda: self._fijar_sashes(pw))

        # Barra de totales
        self.lbl_conteo = tk.Label(parent, text="", font=("Arial", 8), fg="#555")
        self.lbl_conteo.grid(row=2, column=0, pady=(1, 4))

        self._refrescar_facturas()

    def _actualizar_lbl_modo(self):
        if not hasattr(self, 'lbl_modo'):
            return
        pausado = os.path.exists(PAUSA_FILE)
        es_manual = pausado and getattr(self, '_modo_manual', False)

        if es_manual:
            self.lbl_modo.config(
                text="Modo manual — cada clic en '▶ Un ciclo' corre un ciclo completo y se detiene. Use 'Reanudar' para pasar a modo automatico.",
                bg="#eef4ee", fg="#1a6b2a")
        elif not pausado:
            try:
                intervalo = leer_config(self.cfg_path).get('02', {}).get('intervalo', '?')
            except Exception:
                intervalo = '?'
            self.lbl_modo.config(
                text=f"Modo automatico — el daemon corre un ciclo, espera {intervalo} segundo(s) y repite.",
                bg="#eef0fa", fg="#003399")
        else:
            self.lbl_modo.config(
                text="Proceso pausado — no se esta sincronizando. Use '▶ Un ciclo' para modo manual o 'Reanudar' para modo automatico.",
                bg="#fff8ee", fg="#884400")

    def _fijar_sashes(self, pw):
        h = pw.winfo_height()
        if h > 10:
            pw.sashpos(0, h // 4)
            pw.sashpos(1, h // 2)
            pw.sashpos(2, (h * 3) // 4)

    def _refrescar_facturas(self):
        datos = _leer_facturas(self.carpeta)
        ch = lambda v: "SI" if v else "-"

        def _items_str(it):
            return f"  {it['cod_pro']} — {it['nombre'][:40]}"

        def _qty(it):
            return f"{it['cantidad']:.0f} x {it['precio']:.0f}"

        # ── Pendientes (no tocadas) ───────────────────────────────────────────
        self.tree_pend.delete(*self.tree_pend.get_children())
        for fac in datos["pendientes"]:
            iid = self.tree_pend.insert("", "end",
                values=(fac["empresa"], fac["num_doc"], fac["nit_cli"],
                        fac["fecha"], len(fac["items"])),
                open=False,
            )
            for it in fac["items"]:
                self.tree_pend.insert(iid, "end",
                    values=("", _items_str(it), "", "", _qty(it)),
                    tags=("item_row",),
                )

        # ── Con inconsistencias (intentadas, no procesadas) ──────────────────
        self.tree_err.delete(*self.tree_err.get_children())
        for fac in datos["con_error"]:
            iid = self.tree_err.insert("", "end",
                values=(fac["empresa"], fac["num_doc"], fac["nit_cli"],
                        fac["fecha"], len(fac["items"]), fac["motivo"]),
                tags=("err_row",), open=False,
            )
            for it in fac["items"]:
                self.tree_err.insert(iid, "end",
                    values=("", _items_str(it), "", "", _qty(it), ""),
                    tags=("item_row",),
                )

        # ── Procesadas ────────────────────────────────────────────────────────
        self.tree_proc.delete(*self.tree_proc.get_children())
        for fac in datos["procesadas"]:
            iid = self.tree_proc.insert("", "end",
                values=(fac["empresa"], fac["num_doc"], fac["nit_cli"],
                        fac["fecha"], len(fac["items"]),
                        ch(fac["f_prod1"]), ch(fac["f_standar"]),
                        ch(fac["f_costos"]),  ch(fac["f_contab"])),
                tags=("ok_row",), open=False,
            )
            for it in fac["items"]:
                self.tree_proc.insert(iid, "end",
                    values=("", _items_str(it), "", "", _qty(it), "", "", "", ""),
                    tags=("item_row",),
                )

        # ── Procesadas con alertas ────────────────────────────────────────────
        self.tree_alerta.delete(*self.tree_alerta.get_children())
        for fac in datos["con_alerta"]:
            iid = self.tree_alerta.insert("", "end",
                values=(fac["empresa"], fac["num_doc"], fac["nit_cli"],
                        fac["fecha"], len(fac["items"]), fac["motivo"]),
                tags=("alerta_row",), open=False,
            )
            for it in fac["items"]:
                self.tree_alerta.insert(iid, "end",
                    values=("", _items_str(it), "", "", _qty(it), ""),
                    tags=("item_row",),
                )

        np = len(datos["pendientes"])
        ne = len(datos["con_error"])
        nr = len(datos["procesadas"])
        na = len(datos["con_alerta"])
        self.lbl_conteo.config(
            text=f"Pendientes: {np}   |   Con inconsistencias: {ne}   |   Procesadas: {nr}   |   Con alertas: {na}"
        )

    def _tab_terceros(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Encabezado
        hdr = tk.Frame(parent)
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))
        tk.Label(hdr, text="NITs no encontrados en TERCEROS",
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(hdr, text="Refrescar", font=("Arial", 8),
                  command=self._refrescar_terceros).pack(side="right")

        # Treeview
        frm = ttk.LabelFrame(parent, text="  NITs pendientes de resolucion  ")
        frm.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(0, weight=1)

        cols = ("empresa", "nit", "nombre", "facturas", "accion")
        self.tree_nits = ttk.Treeview(frm, columns=cols, show="headings",
                                       selectmode="browse", height=14)
        self.tree_nits.column("empresa",  width=60,  anchor="center")
        self.tree_nits.column("nit",      width=120, anchor="w")
        self.tree_nits.column("nombre",   width=180, anchor="w")
        self.tree_nits.column("facturas", width=220, anchor="w")
        self.tree_nits.column("accion",   width=75,  anchor="center")
        for col, lbl in [("empresa", "Empresa"), ("nit", "NIT"), ("nombre", "Nombre cliente"),
                          ("facturas", "Facturas afectadas"), ("accion", "Accion")]:
            self.tree_nits.heading(col, text=lbl)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tree_nits.yview)
        self.tree_nits.configure(yscrollcommand=sb.set)
        self.tree_nits.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree_nits.tag_configure("pendiente", foreground="#cc4400")
        self.tree_nits.tag_configure("ignorar",   foreground="#999999")
        self.tree_nits.tag_configure("creado",    foreground="#007700")

        # Botones de accion
        frame_acc = tk.Frame(parent)
        frame_acc.grid(row=2, column=0, padx=8, pady=(2, 4), sticky="w")
        tk.Label(frame_acc, text="Fila seleccionada:",
                 font=("Arial", 9)).pack(side="left", padx=(0, 8))
        self.btn_crear_tercero = tk.Button(frame_acc, text="Crear en Administrator", width=20,
                  bg="#007700", fg="white", font=("Arial", 8, "bold"),
                  command=self._crear_tercero_ui)
        self.btn_crear_tercero.pack(side="left", padx=3)
        self.btn_ignorar_nit = tk.Button(frame_acc, text="Ignorar", width=10,
                  bg="#555555", fg="white", font=("Arial", 8),
                  command=lambda: self._set_accion_nit("ignorar"))
        self.btn_ignorar_nit.pack(side="left", padx=3)
        self.lbl_nits_total = tk.Label(frame_acc, text="", font=("Arial", 8), fg="#555")
        self.lbl_nits_total.pack(side="left", padx=(16, 0))

        # Nota explicativa
        self.lbl_nits_modo = tk.Label(parent, text="", font=("Arial", 8), fg="#666",
                                      justify="left", anchor="w")
        self.lbl_nits_modo.grid(row=3, column=0, padx=10, pady=(0, 6), sticky="w")

        self._refrescar_terceros()
        self.after(0, self._actualizar_modo_nits)

    def _refrescar_terceros(self):
        nits = _leer_nits_pend(self.carpeta)
        self.tree_nits.delete(*self.tree_nits.get_children())
        for n in nits:
            accion = n["accion"]
            tag = accion if accion in ("ignorar", "creado") else "pendiente"
            self.tree_nits.insert("", "end",
                values=(n["empresa"], n["nit"], n["nombre"], n["num_docs"], accion),
                tags=(tag,),
            )
        total  = len(nits)
        pend   = sum(1 for n in nits if n["accion"] == "pendiente")
        creado = sum(1 for n in nits if n["accion"] == "creado")
        self.lbl_nits_total.config(
            text=f"Pendientes: {pend}   Creados: {creado}   Total NITs: {total}"
        )

    def _actualizar_modo_nits(self):
        if not hasattr(self, 'btn_crear_tercero') or not hasattr(self, 'btn_ignorar_nit'):
            return
        auto = getattr(self, 'var_auto_nit', None) and self.var_auto_nit.get()
        if auto:
            self.btn_crear_tercero.config(state="disabled", bg="#aaaaaa")
            self.btn_ignorar_nit.config(state="disabled", bg="#aaaaaa")
            self.lbl_nits_modo.config(
                text="Modo automático activo: el proceso crea los NITs sin intervención manual.\n"
                     "Los botones Crear e Ignorar no tienen efecto mientras esta opción esté habilitada."
            )
        else:
            self.btn_crear_tercero.config(state="normal", bg="#007700")
            self.btn_ignorar_nit.config(state="normal", bg="#555555")
            self.lbl_nits_modo.config(
                text="Modo manual: use 'Crear en Administrator' para crear el NIT y continuar el proceso,\n"
                     "o 'Ignorar' para que el daemon omita silenciosamente las facturas de ese NIT."
            )

    def _set_accion_nit(self, accion: str):
        sel = self.tree_nits.selection()
        if not sel:
            return
        vals = self.tree_nits.item(sel[0], "values")
        empresa, nit = vals[0], vals[1]
        _guardar_accion_nit(self.carpeta, nit, empresa, accion)
        self._refrescar_terceros()

    def _revertir_ui(self):
        sel = self.tree_proc.selection()
        if not sel:
            messagebox.showinfo("Revertir fases", "Seleccione una factura procesada primero.")
            return
        # Solo filas padre (facturas), no hijos (items)
        parent = self.tree_proc.parent(sel[0])
        fid_row = sel[0] if parent == "" else parent
        vals    = self.tree_proc.item(fid_row, "values")
        empresa = vals[0]
        num_doc = vals[1]

        # Obtener factura_id: releer allegra_pendientes para buscar por num_doc+empresa
        factura_id = None
        try:
            import dbf as _dbf
            ruta = os.path.join(self.carpeta, "allegra_pendientes.dbf")
            t = _dbf.Table(ruta, codepage="cp1252")
            t.open(_dbf.READ_ONLY)
            for rec in t:
                if _dbf.is_deleted(rec):
                    continue
                if (str(rec.num_doc).strip() == num_doc and
                        str(rec.empresa).strip() == empresa):
                    factura_id = str(rec.factura_id).strip()
                    break
            t.close()
        except Exception:
            pass

        if not factura_id:
            messagebox.showerror("Revertir fases", "No se pudo identificar la factura.")
            return

        fases_disp = [
            ("f_prod1",  "PROD_FACT1 (registros de ventas)"),
            ("f_standar", "REG_PROD / Estándar (inventario)"),
            ("f_costos",  "Costos de ventas"),
            ("f_contab",  "Contabilidad"),
        ]
        dlg = _DialogRevertirFases(self, num_doc, empresa, fases_disp)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        fases_sel = dlg.result
        if not fases_sel:
            return

        ok, msg = _revertir_fases_dbf(self.carpeta, factura_id, empresa, fases_sel)
        if ok:
            self._refrescar_facturas()
            aviso = (
                f"{msg}\n\nLa factura volverá a 'Pendientes' y el daemon la procesará "
                f"en el próximo ciclo.\n\n"
            )
            if "f_prod1" in fases_sel:
                aviso += (
                    "ATENCIÓN: Si revirtió PROD_FACT1, debe eliminar manualmente "
                    "los registros correspondientes en PROD_FACT1 de Administrator "
                    "antes de que el daemon corra nuevamente."
                )
            messagebox.showinfo("Revertir fases", aviso)
        else:
            messagebox.showerror("Revertir fases", f"No se pudo revertir:\n{msg}")

    def _crear_tercero_ui(self):
        sel = self.tree_nits.selection()
        if not sel:
            return
        vals    = self.tree_nits.item(sel[0], "values")
        empresa = vals[0]
        nit     = vals[1]
        nombre  = vals[2]   # nombre_cli desde Alegra

        dlg = _DialogCrearTercero(self, nit, empresa, nombre)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        nombre, ciudad = dlg.result
        ok, msg, cod_ter = _crear_tercero_bin(self.carpeta, nit, nombre, ciudad, empresa)
        if ok:
            _guardar_accion_nit(self.carpeta, nit, empresa, "creado")
            self._refrescar_terceros()
            messagebox.showinfo(
                "TERCERO creado",
                f"{msg}\nNombre: {nombre}\n\n"
                f"En el proximo ciclo se procesaran automaticamente\n"
                f"todas las facturas bloqueadas por este NIT.",
            )
        else:
            messagebox.showerror("No se pudo crear el TERCERO", msg)

    def _tipos_doc_automaticos(self, empresa_s: str) -> tuple:
        """
        Devuelve (lista_display, dict_codigo_a_display) para el Combobox.
        Display: "013 — FACTURA VENTA POS"
        Filtro: TIPO_DOC.ESTADO_INV=3 AND CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA.
        """
        try:
            carpeta = self.carpeta

            # 1. TIPO_DOC — ventas (ESTADO_INV=3), guardando codigo → nombre
            ruta_td = os.path.join(carpeta, "TIPO_DOC.dbf")
            nombres = {}  # {codigo: nombre}
            if os.path.exists(ruta_td):
                t = dbf.Table(ruta_td, codepage="cp1252")
                t.open(dbf.READ_ONLY)
                campos_td = [f.lower() for f in t.field_names]
                campo_estado = 'estado_inv' if 'estado_inv' in campos_td else 'estado_inve'
                for r in t:
                    if dbf.is_deleted(r): continue
                    try:
                        if int(getattr(r, campo_estado) or 0) == 3:
                            cod = str(r.codigo).strip()
                            nom = str(r.nombre).strip() if 'nombre' in campos_td else ''
                            nombres[cod] = nom
                    except Exception:
                        pass
                t.close()

            # 2. CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA — filtrado por empresa
            ruta_auto = os.path.join(carpeta, "CONTABILIDAD_DOCUMENTOS_AUTOMATICOS_EMPRESA.dbf")
            docs_auto = set(nombres.keys())  # fallback si no existe la tabla
            if os.path.exists(ruta_auto):
                t2 = dbf.Table(ruta_auto, codepage="cp1252")
                t2.open(dbf.READ_ONLY)
                docs_auto = set()
                for r in t2:
                    if dbf.is_deleted(r): continue
                    if str(r.empresa).strip().upper() == empresa_s.strip().upper():
                        docs_auto.add(str(r.documento).strip())
                t2.close()

            codigos = sorted(set(nombres.keys()) & docs_auto)
            display  = [f"{c} — {nombres.get(c, '')}" for c in codigos]
            cod_map  = {f"{c} — {nombres.get(c, '')}": c for c in codigos}
            return display, cod_map
        except Exception:
            return [], {}

    def _objetos_en_documento(self, empresa_s: str, cod_doc: str) -> set:
        """
        Devuelve el conjunto de objetos TXT_* configurados contablemente
        para el tipo de documento dado en CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR.
        """
        objetos = set()
        if not cod_doc:
            return objetos
        try:
            carpeta = self.carpeta
            # Cargar mapa AYUDA: consecutivo → objeto
            ayuda_map = {}
            ruta_ay = os.path.join(carpeta, "AYUDA.dbf")
            if os.path.exists(ruta_ay):
                t = dbf.Table(ruta_ay, codepage="cp1252")
                t.open(dbf.READ_ONLY)
                for r in t:
                    if dbf.is_deleted(r): continue
                    ayuda_map[int(r.consecutiv or 0)] = str(r.objeto).strip().upper()
                t.close()
            # Leer config contable del documento
            ruta_cfg = os.path.join(carpeta, "CONTABILIDAD_DOCUMENTOS_CONTABLES_CONFIGURAR.dbf")
            if os.path.exists(ruta_cfg):
                t2 = dbf.Table(ruta_cfg, codepage="cp1252")
                t2.open(dbf.READ_ONLY)
                for r in t2:
                    if dbf.is_deleted(r): continue
                    if str(r.empresa).strip().upper() != empresa_s.strip().upper(): continue
                    if str(r.documento).strip().upper() != cod_doc.strip().upper(): continue
                    doc_cruze_raw = int(float(str(r.documento_).strip() or "0") if str(r.documento_).strip() else 0)
                    obj = ayuda_map.get(doc_cruze_raw, "")
                    if obj:
                        objetos.add(obj)
                t2.close()
        except Exception:
            pass
        return objetos

    def _actualizar_estado_inputs(self, emp_key: str):
        """
        Pinta verde/gris cada fila de met_pago según si el objeto TXT_*
        está configurado contablemente en el tipo de documento seleccionado.
        """
        display = self._vars_tip_doc.get(emp_key, None)
        if display is None:
            return
        cod_map  = self._tip_doc_map.get(emp_key, {})
        cod_doc  = cod_map.get(display.get().strip(), "")
        activos  = self._objetos_en_documento(emp_key, cod_doc)

        for objeto, frame_fila, cmb in self._filas_met.get(emp_key, []):
            obj_up = objeto.strip().upper()
            configurado = obj_up in activos
            if configurado:
                frame_fila.config(highlightbackground="#27ae60", highlightthickness=2)
                frame_fila._merlin_msg = None
            else:
                frame_fila.config(highlightbackground="#cccccc", highlightthickness=1)
                frame_fila._merlin_msg = (
                    f"{obj_up} no está configurado contablemente\n"
                    f"para el documento seleccionado.\n"
                    f"El método asignado aquí no se usará en contabilización."
                )
            cmb.config(state="readonly")  # siempre visible y seleccionable

        if not cod_doc:
            return
        # Mensaje de resumen al pintar
        n_act = len([o for o, _, _ in self._filas_met.get(emp_key, []) if o.upper() in activos])
        n_tot = len(self._filas_met.get(emp_key, []))
        self._set_log(
            f"[{emp_key}] Documento {cod_doc}: {n_act} de {n_tot} inputs contables activos "
            f"({', '.join(sorted(activos)) or 'ninguno'})"
        )

    def _tab_configuracion(self, parent, d02, dLP, PAD):
        ANCHO = 560
        LW = 36
        row = 0

        def sep():
            nonlocal row
            ttk.Separator(parent, orient="horizontal").grid(
                row=row, column=0, columnspan=3, sticky="ew", padx=8, pady=3)
            row += 1

        # BD activa
        tk.Label(parent, text="BD activa en Administrator:",
                 font=("Arial", 9, "bold"), anchor="w").grid(
                 row=row, column=0, columnspan=3, sticky="w", padx=10, pady=(8,0)); row += 1
        tk.Label(parent, text=self.bd_actual_dbc or "(no detectada)",
                 font=("Arial", 8), fg="#333", anchor="w",
                 wraplength=ANCHO, justify="left").grid(
                 row=row, column=0, columnspan=3, sticky="w", padx=22, pady=(0,3)); row += 1

        bd_esp = leer_bd_esperada()
        coincide = (self.bd_actual_dbc.lower() == bd_esp.lower()) if bd_esp else False
        ind_txt = "OK — coincide" if coincide else ("Advertencia: NO coincide" if bd_esp else "Sin definir")
        ind_col = "#007700" if coincide else "#cc4400"

        tk.Label(parent, text="BD esperada (Administrator Interfases):",
                 font=("Arial", 9, "bold"), anchor="w").grid(
                 row=row, column=0, columnspan=3, sticky="w", padx=10, pady=(3,0)); row += 1
        self.lbl_bd_esp = tk.Label(parent, text=bd_esp or "(sin definir)",
                 font=("Arial", 8), fg="#333", anchor="w",
                 wraplength=ANCHO, justify="left")
        self.lbl_bd_esp.grid(row=row, column=0, columnspan=3, sticky="w", padx=22, pady=(0,2)); row += 1

        frame_ind = tk.Frame(parent)
        frame_ind.grid(row=row, column=0, columnspan=3, sticky="w", padx=10, pady=(0,4)); row += 1
        self.lbl_indicador = tk.Label(frame_ind, text=ind_txt, font=("Arial", 9, "bold"), fg=ind_col)
        self.lbl_indicador.pack(side="left", padx=(0,10))
        tk.Button(frame_ind, text="Usar BD activa como esperada", font=("Arial", 8),
                  command=self.definir_bd_esperada).pack(side="left")

        sep()

        # Parámetros globales
        tk.Label(parent, text="Max facturas por lote:", width=LW, anchor="e",
                 font=("Arial", 9)).grid(row=row, column=0, **PAD)
        self.var_max = tk.IntVar(value=d02['max_fact'])
        tk.Spinbox(parent, from_=1, to=200, textvariable=self.var_max,
                   width=6, font=("Arial", 13)).grid(row=row, column=1, sticky="w", **PAD)
        tk.Label(parent, text="≈30s/fac local · ≈90s/fac servidor", font=("Arial", 8), fg="#888").grid(
                 row=row, column=2, sticky="w"); row += 1

        self.lbl_estimado = tk.Label(parent, text="", font=("Arial", 8), fg="#555", anchor="w")
        self.lbl_estimado.grid(row=row, column=1, columnspan=2, sticky="w", padx=(4,0)); row += 1

        TIMEOUT_CICLO = 3600  # segundos — límite fijo del formulario "Un ciclo"
        def _actualizar_estimado(*_):
            try: mf = self.var_max.get()
            except Exception: return
            try: intv = self.var_int.get()
            except Exception: intv = 0
            loc = mf * 30
            srv = mf * 90
            pct = int(srv / TIMEOUT_CICLO * 100)
            if srv >= TIMEOUT_CICLO:
                color = "#cc0000"
                aviso = "  ⚠ SUPERA EL TIMEOUT — reducir facturas"
            elif pct >= 80:
                color = "#cc6600"
                aviso = f"  ⚠ {pct}% del timeout"
            else:
                color = "#555"
                aviso = ""
            self.lbl_estimado.config(fg=color,
                text=f"Duración estimada del ciclo: ~{loc//60}m{loc%60:02d}s local  /  ~{srv//60}m{srv%60:02d}s servidor  "
                     f"(timeout: {TIMEOUT_CICLO}seg){aviso}"
            )

        self.var_max.trace_add("write", _actualizar_estimado)
        _actualizar_estimado()

        tk.Label(parent, text="Pausa entre ciclos (seg, 0=manual):", width=LW, anchor="e",
                 font=("Arial", 9)).grid(row=row, column=0, **PAD)
        self.var_int = tk.IntVar(value=d02['intervalo'])
        tk.Spinbox(parent, from_=0, to=9999, textvariable=self.var_int,
                   width=6, font=("Arial", 13)).grid(row=row, column=1, sticky="w", **PAD)
        self.var_int.trace_add("write", _actualizar_estimado)
        tk.Label(parent, text="0 = solo manual  ·  pausa después de que termina el ciclo anterior",
                 font=("Arial", 8), fg="#888").grid(
                 row=row, column=2, sticky="w"); row += 1

        sep()

        # ── Diagnóstico fuente ────────────────────────────────────────────────
        tk.Label(parent, text="Diagnóstico fuente:", width=LW, anchor="e",
                 font=("Arial", 9, "bold")).grid(row=row, column=0, **PAD)
        self.lbl_diag_estado = tk.Label(parent, text="Consultando fuente...",
                                        font=("Arial", 8), fg="#888", anchor="w")
        self.lbl_diag_estado.grid(row=row, column=1, columnspan=2, sticky="w"); row += 1

        # Frame tabla diagnóstico
        self._diag_frame = tk.Frame(parent, bg="#f7f7f7", relief="groove", bd=1)
        self._diag_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=4, pady=(0,4)); row += 1

        # Guardar últimos de Alegra en memoria
        self._alegra_ultimo = {"02": None, "LP": None}  # número entero

        def _calcular_diag(*_):
            """Recalcula diagnóstico con datos en memoria — sin llamada API."""
            try: mf = self.var_max.get()
            except Exception: mf = 1
            try: intv = self.var_int.get()
            except Exception: intv = 0
            ni_02 = self._vars_num_ini.get("02", tk.StringVar()).get().strip().upper()
            ni_lp = self._vars_num_ini.get("LP", tk.StringVar()).get().strip().upper()

            def _n(s):
                digits = ''.join(filter(str.isdigit, s))
                return int(digits) if digits else 0

            ul_02 = self._alegra_ultimo.get("02") or 0
            ul_lp = self._alegra_ultimo.get("LP") or 0
            pend_02 = max(0, ul_02 - _n(ni_02))
            pend_lp = max(0, ul_lp - _n(ni_lp))
            total_pend = pend_02 + pend_lp

            # Ciclos estimados (por empresa — la que más tiene manda)
            ciclos = max(
                (pend_02 + mf - 1) // mf if mf > 0 else 0,
                (pend_lp + mf - 1) // mf if mf > 0 else 0,
            ) if mf > 0 else 0

            # Tiempo total: ciclos × (duración estimada ciclo + pausa entre ciclos)
            seg_ciclo_est = mf * 90  # estimado duración del ciclo en servidor
            seg_por_ciclo = seg_ciclo_est + intv  # ciclo + pausa
            seg_total = ciclos * seg_por_ciclo
            if seg_total < 3600:
                tiempo_txt = f"~{seg_total//60} min"
            else:
                h = seg_total // 3600
                m = (seg_total % 3600) // 60
                tiempo_txt = f"~{h}h {m}m"

            # Limpiar frame y redibujar
            for w in self._diag_frame.winfo_children():
                w.destroy()

            headers = ["", "LP (J&P)", "02 (TV&Video)"]
            err_02 = getattr(self, "_alegra_error", {}).get("02", "")
            err_lp = getattr(self, "_alegra_error", {}).get("LP", "")
            ul_02_txt = f"PTV{ul_02}" if ul_02 else (f"Error: {err_02[:30]}" if err_02 else "...")
            ul_lp_txt = f"PJP{ul_lp}" if ul_lp else (f"Error: {err_lp[:30]}" if err_lp else "...")
            rows_data = [
                ("Último en Alegra",  ul_lp_txt,         ul_02_txt),
                ("Num inicio config", ni_lp or "—",      ni_02 or "—"),
                ("Por descargar",     f"~{pend_lp}",     f"~{pend_02}"),
                ("Por ciclo",         f"{mf}",            f"{mf}"),
                ("Ciclos estimados",  f"~{ciclos}",       f"~{ciclos}"),
                ("Tiempo total est.", tiempo_txt,         tiempo_txt),
            ]
            col_w = (22, 14, 14)
            for ci, h in enumerate(headers):
                tk.Label(self._diag_frame, text=h, font=("Arial", 8, "bold"),
                         bg="#e8e8e8", width=col_w[ci], anchor="center",
                         relief="flat", padx=4).grid(row=0, column=ci, sticky="ew", padx=1, pady=1)
            for ri, (lbl, v_lp, v_02) in enumerate(rows_data):
                bg = "#f7f7f7" if ri % 2 == 0 else "#efefef"
                color_lp = "#cc0000" if pend_lp > 500 and "descargar" in lbl else "#222"
                color_02 = "#cc0000" if pend_02 > 500 and "descargar" in lbl else "#222"
                tk.Label(self._diag_frame, text=lbl, font=("Arial", 8),
                         bg=bg, anchor="e", width=col_w[0], padx=4).grid(row=ri+1, column=0, sticky="ew", padx=1)
                tk.Label(self._diag_frame, text=v_lp, font=("Arial", 8),
                         bg=bg, fg=color_lp, anchor="center", width=col_w[1]).grid(row=ri+1, column=1, sticky="ew", padx=1)
                tk.Label(self._diag_frame, text=v_02, font=("Arial", 8),
                         bg=bg, fg=color_02, anchor="center", width=col_w[2]).grid(row=ri+1, column=2, sticky="ew", padx=1)

        self._calcular_diag = _calcular_diag

        # Enganchar traces de num_inicio — después de que se creen los vars
        self.after(300, self._enganchar_diag_traces)

        # Llamada API en background al abrir
        self._alegra_error = {}   # emp -> str de error
        def _consultar_alegra():
            import base64, requests as _req
            creds = [
                ("02", "electronicastvyvideo@hotmail.com", "ade8e319ce85985fb47c"),
                ("LP", "electronicajyp@hotmail.com",       "aabde447e95a29efb773"),
            ]
            for emp, email, token in creds:
                try:
                    cred = base64.b64encode(f"{email}:{token}".encode()).decode()
                    h = {"Authorization": f"Basic {cred}", "Accept": "application/json"}
                    r = _req.get("https://api.alegra.com/api/v1/invoices",
                                 headers=h, params={"limit": 30, "start": 0}, timeout=15)
                    if r.status_code != 200:
                        self._alegra_error[emp] = f"HTTP {r.status_code}: {r.text[:120]}"
                        continue
                    data = r.json()
                    if data:
                        # Factura más reciente → número máximo
                        num = (data[0].get("numberTemplate") or {}).get("fullNumber", "")
                        n = int(''.join(filter(str.isdigit, num))) if num else 0
                        self._alegra_ultimo[emp] = n
                    else:
                        self._alegra_error[emp] = "respuesta vacía"
                except Exception as ex:
                    self._alegra_error[emp] = str(ex)
            # Guardar sellers detectados y refrescar sección vendedores
            self.after(0, lambda: self.lbl_diag_estado.config(text="", fg="#888"))
            self.after(0, _calcular_diag)

        import threading
        threading.Thread(target=_consultar_alegra, daemon=True).start()

        # Trace de var_max y var_int ya engancha con _actualizar_estimado;
        # aquí enganchamos diag por separado
        self.var_max.trace_add("write", lambda *_: self.after(0, _calcular_diag))
        self.var_int.trace_add("write", lambda *_: self.after(0, _calcular_diag))

        sep()

        # Keyword global impuesto de bolsa
        tk.Label(parent, text="Palabra clave ítem bolsa:", width=LW, anchor="e",
                 font=("Arial", 9)).grid(row=row, column=0, **PAD)
        kw_inicial = d02.get('kw_bolsa', '') or 'BOLSA'
        self.var_kw_bolsa = tk.StringVar(value=kw_inicial)
        tk.Entry(parent, textvariable=self.var_kw_bolsa, width=20,
                 font=("Arial", 9)).grid(row=row, column=1, sticky="w", **PAD)
        tk.Label(parent, text="Texto que identifica el ítem de bolsa en Alegra",
                 font=("Arial", 8), fg="#888").grid(row=row, column=2, sticky="w"); row += 1

        self.var_auto_nit = tk.BooleanVar(value=d02.get('auto_nit', False))

        # ── Toggle switch canvas ──────────────────────────────────────────────
        W, H, R = 44, 22, 11   # ancho, alto, radio píldora
        frame_toggle = tk.Frame(parent)
        frame_toggle.grid(row=row, column=0, columnspan=3,
                          sticky="w", padx=10, pady=(4, 4)); row += 1
        cv = tk.Canvas(frame_toggle, width=W, height=H,
                       bd=0, highlightthickness=0, cursor="hand2")
        cv.pack(side="left")
        tk.Label(frame_toggle, text="Crear NITs automáticamente en Administrator",
                 font=("Arial", 9)).pack(side="left", padx=(8, 0))

        def _dibujar_switch():
            cv.delete("all")
            on = self.var_auto_nit.get()
            bg  = "#27ae60" if on else "#cccccc"
            cx  = W - R - 2 if on else R + 2
            # píldora
            cv.create_oval(0, 0, H, H, fill=bg, outline="")
            cv.create_oval(W-H, 0, W, H, fill=bg, outline="")
            cv.create_rectangle(R, 0, W-R, H, fill=bg, outline="")
            # círculo blanco
            cv.create_oval(cx-R+3, 3, cx+R-3, H-3, fill="white", outline="")

        def _toggle_auto_nit(_=None):
            self.var_auto_nit.set(not self.var_auto_nit.get())
            _dibujar_switch()
            self._actualizar_modo_nits()

        cv.bind("<Button-1>", _toggle_auto_nit)
        _dibujar_switch()  # estado inicial

        sep()

        # ── Contabilización por empresa ────────────────────────────────────────
        tk.Label(parent, text="Contabilizacion de facturas importadas",
                 font=("Arial", 9, "bold"), anchor="w").grid(
                 row=row, column=0, columnspan=3, sticky="w", padx=10, pady=(4,2)); row += 1

        INPUTS_PAGO = [
            ("TXT_ABONA_EFECTIVO",     "Efectivo",       "met_efect"),
            ("TXT_TARJETA_RECIBIDO",   "Tarjeta débito",  "met_debito"),
            ("TXT_TARJETA_RECIBIDO",   "Tarjeta crédito", "met_credit"),
            ("TXT_CONSIGNA_TRASFIERE", "Transferencia",  "met_transf"),
            ("TXT_COBRAR_CLIENTE",     "Cobrar cliente", "met_cxc"),
        ]

        self._vars_tip_doc  = {}
        self._tip_doc_map   = {}   # {empresa: {display: codigo}}
        self._vars_met      = {}   # {empresa: {cfg_key: StringVar}}
        self._filas_met     = {}   # {empresa: [(objeto, frame_fila, cmb), ...]}
        self._vars_num_ini  = {}   # {empresa: StringVar}
        self._lbl_sugerido  = {}   # {empresa: Label}

        for emp_key, emp_label, emp_datos in [("02", "02 TV & Video", d02), ("LP", "LP J&P", dLP)]:
            # Marco por empresa
            frame_emp = tk.LabelFrame(parent, text=f"  {emp_label}  ",
                                      font=("Arial", 9, "bold"), padx=8, pady=4)
            frame_emp.grid(row=row, column=0, columnspan=3, sticky="ew",
                           padx=10, pady=(4,2)); row += 1

            docs_display, cod_map = self._tipos_doc_automaticos(emp_key)
            self._tip_doc_map[emp_key] = cod_map
            cod_guardado = emp_datos.get('tip_doc', '')
            val_inicial  = next((d for d, c in cod_map.items() if c == cod_guardado), cod_guardado)
            var_doc = tk.StringVar(value=val_inicial)
            self._vars_tip_doc[emp_key] = var_doc

            # Fila 0: frame full-width con tipo doc + última factura usando pack
            frame_top = tk.Frame(frame_emp)
            frame_top.grid(row=0, column=0, columnspan=4, sticky="ew", **PAD)
            frame_emp.columnconfigure(0, weight=1)

            tk.Label(frame_top, text="Tipo de documento:", font=("Arial", 9)).pack(side="left")
            cmb = ttk.Combobox(frame_top, textvariable=var_doc, values=docs_display,
                               font=("Arial", 9), state="readonly")
            cmb.pack(side="left", fill="x", expand=True, padx=(4, 12))
            cmb.bind("<MouseWheel>", lambda e: "break")
            cmb.bind("<Button-4>",   lambda e: "break")
            cmb.bind("<Button-5>",   lambda e: "break")
            cmb.bind("<<ComboboxSelected>>",
                     lambda e, ek=emp_key: (self._actualizar_estado_inputs(ek),
                                            self._actualizar_num_sugerido(ek)))

            tk.Label(frame_top, text="Última factura:", font=("Arial", 9)).pack(side="left")
            num_ini_val = emp_datos.get('num_inicio', '')
            var_num = tk.StringVar(value=num_ini_val)
            self._vars_num_ini[emp_key] = var_num
            tk.Entry(frame_top, textvariable=var_num, width=12,
                     font=("Arial", 9)).pack(side="left", padx=(4, 0))

            # Fila 1: sugerido
            lbl_sug = tk.Label(frame_emp, text="", font=("Arial", 8), fg="#27ae60", anchor="w")
            lbl_sug.grid(row=1, column=0, columnspan=4, sticky="w", padx=(8, 0), pady=(0, 2))
            self._lbl_sugerido[emp_key] = lbl_sug

            # Cabecera tabla emparejamiento
            tk.Label(frame_emp, text="Input Administrator", font=("Arial", 8, "bold"),
                     relief="groove", anchor="center").grid(
                     row=2, column=0, columnspan=3, sticky="ew", padx=(0,2), pady=(4,1))
            tk.Label(frame_emp, text="Metodo de pago Alegra",
                     font=("Arial", 8, "bold"), relief="groove", anchor="center").grid(
                     row=2, column=3, sticky="ew", padx=(2,0), pady=(4,1))

            METS_ALEGRA = [
                "",
                "cash",
                "credit-card",
                "debit-card",
                "transfer",
                "credit",
                "check",
                "online",
                "bank-remittance",
            ]

            self._vars_met[emp_key]  = {}
            self._filas_met[emp_key] = []
            for idx, (objeto, titulo, cfg_key) in enumerate(INPUTS_PAGO):
                fila = idx + 3
                bg = "#f5f5f5" if idx % 2 == 0 else "#ebebeb"
                # Frame con borde — se colorea verde/gris según config contable
                frame_fila = tk.Frame(frame_emp, bg=bg,
                                      highlightbackground="#cccccc", highlightthickness=1)
                frame_fila.grid(row=fila, column=0, columnspan=3,
                                sticky="ew", padx=(0,2), pady=1)
                tk.Label(frame_fila, text=f"{titulo}  ({objeto})", font=("Arial", 8),
                         anchor="w", bg=bg, padx=4).pack(fill="x")
                var = tk.StringVar(value=emp_datos.get(cfg_key, ''))
                self._vars_met[emp_key][cfg_key] = var
                cmb_met = ttk.Combobox(frame_emp, textvariable=var, values=METS_ALEGRA,
                                       width=20, font=("Arial", 9), state="readonly")
                cmb_met.grid(row=fila, column=3, sticky="w", padx=(2,0), pady=1)
                cmb_met.bind("<MouseWheel>", lambda e: "break")
                cmb_met.bind("<Button-4>",   lambda e: "break")
                cmb_met.bind("<Button-5>",   lambda e: "break")
                self._filas_met[emp_key].append((objeto, frame_fila, cmb_met))

            frame_emp.columnconfigure(1, weight=1)
            frame_emp.columnconfigure(3, weight=0)
            # Pintar estado inicial si ya hay documento configurado
            # Diferido 200ms para que el Canvas haya completado el primer render
            if cod_guardado:
                self.after(200, lambda ek=emp_key: self._actualizar_estado_inputs(ek))
                self.after(200, lambda ek=emp_key: self._actualizar_num_sugerido(ek))

        sep()

        # ── Equivalencia de vendedores ─────────────────────────────────────────
        tk.Label(parent, text="Equivalencia de vendedores",
                 font=("Arial", 9, "bold"), anchor="w").grid(
                 row=row, column=0, columnspan=3, sticky="w", padx=10, pady=(4,2)); row += 1

        # Leer vendedores de Administrator una sola vez → instancia vars
        self._vendedores_adm = []  # [(codigo_int, display)]
        try:
            tv = dbf.Table(os.path.join(self.carpeta, "MESEROS.dbf"), codepage="cp1252")
            tv.open(dbf.READ_ONLY)
            for rv in tv:
                if dbf.is_deleted(rv): continue
                cod = str(rv.CODIGO).strip()
                nom = str(rv.DESCRIPCIO).strip()
                cod_int = int(cod) if cod.isdigit() else 0
                self._vendedores_adm.append((cod_int, f"{cod} — {nom}"))
            tv.close()
        except Exception:
            pass
        self._vendedores_display  = [""] + [d for _, d in self._vendedores_adm]
        self._cod_mes_map_vend    = {d: cod_int for cod_int, d in self._vendedores_adm}
        self._vars_vendedores     = {}

        # Frame container refreshable
        self._vend_body = tk.Frame(parent)
        self._vend_body.grid(row=row, column=0, columnspan=3, sticky="ew"); row += 1
        self._vend_parent_cfg = parent  # referencia para columnconfigure

        self._renderizar_vendedores()

        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=0)
        parent.columnconfigure(2, weight=1)

        # Registrar todos los inputs para detectar cambios
        self._registrar_inputs_config()

    def _renderizar_vendedores(self, advertir_sin_mapear=False):
        """Construye/reconstruye la sección de vendedores en self._vend_body."""
        for w in self._vend_body.winfo_children():
            w.destroy()
        self._vars_vendedores = {}

        # IDs Alegra: 1..N donde N = max CODIGO de MESEROS.dbf
        # El usuario sabe cuáles IDs existen en Alegra y deja en blanco los que no aplican
        n_sellers = max((cod for cod, _ in self._vendedores_adm), default=0)
        sellers = [str(i) for i in range(1, n_sellers + 1)]

        # Mapeos guardados en alegra_vendedores.dbf
        mapeos_existentes = {}
        ruta_vend = os.path.join(self.carpeta, "alegra_vendedores.dbf")
        if os.path.exists(ruta_vend):
            try:
                tv2 = dbf.Table(ruta_vend, codepage="cp1252")
                tv2.open(dbf.READ_ONLY)
                campos_v = [f.lower() for f in tv2.field_names]
                for rv2 in tv2:
                    if dbf.is_deleted(rv2): continue
                    sid = str(rv2.seller_id).strip()
                    emp = str(rv2.empresa).strip().upper()
                    campo_cod = 'cod_mes' if 'cod_mes' in campos_v else 'cod_ter'
                    cod_int = int(getattr(rv2, campo_cod) or 0)
                    mapeos_existentes[(emp, sid)] = cod_int
                tv2.close()
            except Exception:
                pass

        row_v = 0
        if not sellers:
            tk.Label(self._vend_body,
                     text="No hay vendedores en Administrator (MESEROS.dbf vacío).",
                     font=("Arial", 8), fg="#888").grid(
                     row=row_v, column=0, sticky="w", padx=22, pady=(0,4))
        else:
            for emp_key, emp_label in [("02", "02 TV & Video"), ("LP", "LP J&P")]:
                frame_v = tk.LabelFrame(self._vend_body, text=f"  {emp_label}  ",
                                        font=("Arial", 9, "bold"), padx=8, pady=4)
                frame_v.grid(row=row_v, column=0, sticky="ew", padx=10, pady=(4,2))
                row_v += 1

                tk.Label(frame_v, text="ID Alegra", font=("Arial", 8, "bold"),
                         width=10, anchor="center", relief="groove").grid(
                         row=0, column=0, sticky="ew", padx=(0,2), pady=(0,2))
                tk.Label(frame_v, text="Vendedor Administrator", font=("Arial", 8, "bold"),
                         anchor="center", relief="groove").grid(
                         row=0, column=1, sticky="ew", padx=(2,0), pady=(0,2))

                self._vars_vendedores[emp_key] = {}
                for i, sid in enumerate(sellers):
                    tk.Label(frame_v, text=f"ID {sid}", font=("Arial", 9),
                             anchor="center").grid(row=i+1, column=0, sticky="ew",
                                                   padx=(0,4), pady=2)
                    cod_actual = mapeos_existentes.get((emp_key, sid), 0)
                    val_inicial = next((d for cod_int, d in self._vendedores_adm if cod_int == cod_actual), "")
                    var = tk.StringVar(value=val_inicial)
                    self._vars_vendedores[emp_key][sid] = var
                    cmb_v = ttk.Combobox(frame_v, textvariable=var,
                                         values=self._vendedores_display,
                                         font=("Arial", 9), state="readonly", width=32)
                    cmb_v.grid(row=i+1, column=1, sticky="w", padx=(2,0), pady=2)
                    cmb_v.bind("<MouseWheel>", lambda e: "break")
                    cmb_v.bind("<Button-4>",   lambda e: "break")
                    cmb_v.bind("<Button-5>",   lambda e: "break")

                frame_v.columnconfigure(1, weight=1)

        self._vend_body.columnconfigure(0, weight=1)

        if advertir_sin_mapear:
            sin_mapear = [
                f"  Empresa {emp} — ID {sid}"
                for emp, vars_sid in self._vars_vendedores.items()
                for sid, var in vars_sid.items()
                if not var.get().strip()
            ]
            if sin_mapear:
                self.after(600, lambda: messagebox.showwarning(
                    "Vendedores sin configurar",
                    "Los siguientes vendedores de Alegra no tienen equivalencia en Administrator:\n\n"
                    + "\n".join(sin_mapear)
                    + "\n\nVaya a la sección 'Equivalencia de vendedores' en tab Configuracion."
                ))

    def _tab_estado(self, parent, d02):
        frame_d = tk.Frame(parent)
        frame_d.pack(fill="x", padx=10, pady=(8, 4))
        pausado = os.path.exists(PAUSA_FILE)
        self.btn_borrado_dbf = tk.Button(
            frame_d, text="Borrado DBF (DELETE)", width=20,
            bg="#4a4a8a", fg="white", font=("Arial", 8),
            command=self.borrado_dbf,
            state="normal" if pausado else "disabled",
        )
        self.btn_borrado_dbf.pack(side="left")

        self.btn_reiniciar = tk.Button(
            frame_d, text="Reiniciar proceso", width=16,
            bg="#8b0000", fg="white", font=("Arial", 8),
            command=self.reiniciar_proceso,
            state="normal" if pausado else "disabled",
        )
        self.btn_reiniciar.pack(side="left", padx=(12, 0))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=8, pady=4)

        # Tabla de fases
        tk.Label(parent, text="Estado de facturas por empresa:",
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=10)

        frame_tabla = tk.Frame(parent, bd=1, relief="solid")
        frame_tabla.pack(fill="x", padx=10, pady=(4,6))

        hdrs = ["Empresa", "Pendientes", "PROD_FACT1", "REG_PROD", "Costos", "Contabilidad"]
        for col, h in enumerate(hdrs):
            tk.Label(frame_tabla, text=h, font=("Arial", 8, "bold"),
                     bg="#dde8f0", width=11, relief="groove", anchor="center").grid(
                     row=0, column=col, sticky="nsew", ipadx=2, ipady=2)

        self.lbl_fases = {}
        for fila, emp in enumerate(("02", "LP"), start=1):
            tk.Label(frame_tabla, text=emp, font=("Arial", 9, "bold"),
                     width=11, relief="groove", anchor="center").grid(
                     row=fila, column=0, sticky="nsew", ipady=2)
            self.lbl_fases[emp] = {}
            for col, key in enumerate(("pendientes", "f_prod1", "f_standar", "f_costos", "f_contab"), start=1):
                lbl = tk.Label(frame_tabla, text="–", font=("Arial", 9),
                               width=11, relief="groove", anchor="center")
                lbl.grid(row=fila, column=col, sticky="nsew", ipady=2)
                self.lbl_fases[emp][key] = lbl

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=8, pady=4)

        # Log
        frame_log_hdr = tk.Frame(parent)
        frame_log_hdr.pack(fill="x", padx=10)
        tk.Label(frame_log_hdr, text="Ultimo ciclo:", font=("Arial", 9, "bold")).pack(side="left")
        self.lbl_log_ts = tk.Label(frame_log_hdr, text="", font=("Arial", 8), fg="#888")
        self.lbl_log_ts.pack(side="right")

        frame_log = tk.Frame(parent)
        frame_log.pack(fill="both", expand=True, padx=10, pady=(2,6))
        frame_log.columnconfigure(0, weight=1)
        frame_log.rowconfigure(0, weight=1)
        self.txt_log = tk.Text(frame_log, font=("Courier", 8),
                               bg="#f4f4f4", state="disabled", wrap="word")
        _sb_log = ttk.Scrollbar(frame_log, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=_sb_log.set)
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        _sb_log.grid(row=0, column=1, sticky="ns")

        # Actualizar tabla con datos iniciales
        self._actualizar_tabla_fases()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _set_log(self, texto):
        if not hasattr(self, 'txt_log'):
            return
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.insert("end", texto or "(sin registros aun)")
        self.txt_log.config(state="disabled")

    def _actualizar_tabla_fases(self):
        try:
            stats = _stats_pendientes(self.carpeta)
            for emp in ("02", "LP"):
                s = stats[emp]
                for key in ("pendientes", "f_prod1", "f_standar", "f_costos", "f_contab"):
                    val = s[key]
                    lbl = self.lbl_fases[emp][key]
                    lbl.config(text=str(val))
                    if key == "pendientes":
                        lbl.config(fg="#cc4400" if val > 0 else "#333")
                    else:
                        lbl.config(fg="#007700" if val > 0 else "#999")
        except Exception:
            pass

    def _programar_refresh(self):
        self._refresh()
        self._refrescar_facturas()
        self._refrescar_terceros()
        self._refresh_id = self.after(LOG_REFRESH_MS, self._programar_refresh)

    def _cancelar_refresh(self):
        rid = getattr(self, "_refresh_id", None)
        if rid:
            self.after_cancel(rid)
            self._refresh_id = None

    def _refresh(self):
        try:
            datos = leer_config(self.cfg_path)
            log_txt = datos.get('02', {}).get('ultimo_log', '')
            if log_txt:
                self._set_log(log_txt)
            self.lbl_log_ts.config(text=f"ref. {datetime.now().strftime('%H:%M:%S')}")
            # Sincronizar indicador y botón pausa en barra global
            pausado = os.path.exists(PAUSA_FILE)
            if pausado:
                self.lbl_daemon.config(text="Pausado", fg="#cc6600")
                self.btn_pausa.config(text="Reanudar", bg="#cc6600")
            else:
                activo, _ = _estado_daemon()
                if activo:
                    self.lbl_daemon.config(text="Activo", fg="#007700")
                else:
                    self.lbl_daemon.config(text="Detenido", fg="#cc0000")
                self.btn_pausa.config(text="Pausar", bg="#555")
        except Exception:
            pass
        # Refrescar sugeridos desde estado_proceso.json (ya calculado por el daemon al final del ciclo)
        try:
            import json as _json
            with open(JSON_PATH, encoding='utf-8') as f:
                jdata = _json.load(f)
            for cfg_row in jdata.get('allegra_config', []):
                emp = cfg_row.get('empresa', '')
                emp_key = emp  # '02' o 'LP'
                sug = cfg_row.get('num_sugerido', '')
                num_ini = cfg_row.get('num_inicio', '')
                lbl = self._lbl_sugerido.get(emp_key)
                if lbl and sug:
                    lbl.config(text=f"Sugerido: {sug}", fg="#27ae60")
                var = self._vars_num_ini.get(emp_key)
                if var and num_ini and not var.get().strip():
                    var.set(num_ini)
        except Exception:
            pass
        self._actualizar_tabla_fases()

    def toggle_pausa(self):
        if os.path.exists(PAUSA_FILE):
            # Reanudar: ciclo inmediato en background + daemon queda corriendo
            os.unlink(PAUSA_FILE)
            _asegurar_daemon()
            if os.path.exists(DAEMON_EXE):
                subprocess.Popen([DAEMON_EXE, '--run', 'ciclo'],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                codigo = (
                    "import sys; sys.path.insert(0, r'C:\\S.A.R'); "
                    "import alegra_daemon; alegra_daemon.correr_sync()"
                )
                subprocess.Popen([sys.executable, "-c", codigo])
            self._modo_manual = False
            self.lbl_daemon.config(text="Activo", fg="#007700")
            self.btn_pausa.config(text="Pausar", bg="#555")
            if hasattr(self, 'btn_borrado_dbf'):
                self.btn_borrado_dbf.config(state="disabled")
            if hasattr(self, 'btn_reiniciar'):
                self.btn_reiniciar.config(state="disabled")
            self._actualizar_lbl_modo()
            self._programar_refresh()
        else:
            # Pausar
            open(PAUSA_FILE, "w").write("pausado")
            self._cancelar_refresh()
            _matar_daemons_viejos()
            self.lbl_daemon.config(text="Pausado", fg="#cc6600")
            self.btn_pausa.config(text="Reanudar", bg="#cc6600")
            if hasattr(self, 'btn_borrado_dbf'):
                self.btn_borrado_dbf.config(state="normal")
            if hasattr(self, 'btn_reiniciar'):
                self.btn_reiniciar.config(state="normal")
        _actualizar_daemon_json()


    def borrado_dbf(self):
        """
        Elimina fisicamente los registros marcados como borrados (PACK)
        solo en tablas propias de Alegra: allegra_pendientes y alegra_nits_pend.
        NO toca allegra_config ni PROD_FACT1.
        """
        if not os.path.exists(PAUSA_FILE):
            messagebox.showwarning("Borrado DBF",
                "Primero pausa el daemon para liberar los archivos.")
            return

        tablas = [
            (os.path.join(self.carpeta, "allegra_pendientes.dbf"), "allegra_pendientes"),
            (os.path.join(self.carpeta, "alegra_nits_pend.dbf"),   "alegra_nits_pend"),
        ]
        resultados = []
        errores = []
        for ruta, nombre in tablas:
            if not os.path.exists(ruta):
                continue
            try:
                t = dbf.Table(ruta, codepage="cp1252")
                t.open(dbf.READ_WRITE)
                antes = len(t)
                t.pack()
                despues = len(t)
                t.close()
                resultados.append(f"{nombre}: {antes - despues} eliminados ({despues} quedan)")
            except Exception as e:
                errores.append(f"{nombre}: {e}")

        msg = "\n".join(resultados) if resultados else "Sin cambios."
        if errores:
            msg += "\n\nErrores:\n" + "\n".join(errores)
            messagebox.showerror("Borrado DBF", msg)
        else:
            messagebox.showinfo("Borrado DBF", msg)
        self._refrescar_facturas()

    def definir_bd_esperada(self):
        if not self.bd_actual_dbc:
            messagebox.showwarning("Administrator", "No se pudo detectar la BD activa.")
            return
        guardar_bd_esperada(self.bd_actual_dbc)
        self.lbl_bd_esp.config(text=self.bd_actual_dbc)
        self.lbl_indicador.config(text="OK — coincide", fg="#007700")
        messagebox.showinfo("Administrator", f"BD esperada actualizada:\n{self.bd_actual_dbc}")

    # ── Guardar ───────────────────────────────────────────────────────────────

    def guardar(self):
        max_f = self.var_max.get()
        intv  = self.var_int.get()
        num02 = self._vars_num_ini.get("02", tk.StringVar()).get().strip().upper()
        numLP = self._vars_num_ini.get("LP", tk.StringVar()).get().strip().upper()

        if max_f < 1:
            messagebox.showwarning("Validacion", "El maximo debe ser al menos 1.")
            return False

        # Bloqueo si el ciclo estimado supera el timeout absoluto (3600s)
        seg_srv = max_f * 90
        if seg_srv >= 3600:
            messagebox.showerror("Configuración inválida",
                f"Con {max_f} facturas por lote, el ciclo puede tardar\n"
                f"~{seg_srv//60} minuto(s) en servidor, lo que iguala o supera\n"
                f"el timeout del sistema (60 minutos).\n\n"
                f"Reduzca las facturas por lote (máximo recomendado: 39).")
            return False

        cambio_num = (num02 != self.num_inicio_02_orig.upper() or
                      numLP != self.num_inicio_lp_orig.upper())
        if cambio_num:
            if not messagebox.askyesno("Advertencia",
                "Cambio el numero de inicio.\n"
                "Esto puede reprocesar facturas ya ingresadas en Administrator.\n\n"
                "Desea continuar?"):
                return False

        per_empresa = {}
        for emp in ("02", "LP"):
            mets    = self._vars_met.get(emp, {})
            display = self._vars_tip_doc.get(emp, tk.StringVar()).get().strip()
            cod_map = self._tip_doc_map.get(emp, {})
            tip_doc = cod_map.get(display, "")
            # Si no coincide con el mapa, rechazar — no guardar código desconocido
            if not tip_doc:
                messagebox.showwarning("Tipo de documento inválido",
                    f"Empresa {emp}: el tipo de documento seleccionado\n"
                    f"'{display}' no es válido. Selecciónelo del listado.\n\n"
                    f"No se guardará la configuración.")
                return False
            per_empresa[emp] = {
                "tip_doc": tip_doc,
                "met_efect":   mets.get("met_efect",  tk.StringVar()).get().strip(),
                "met_tarjet":  mets.get("met_tarjet", tk.StringVar()).get().strip(),
                "met_debito": mets.get("met_debito", tk.StringVar()).get().strip(),
                "met_credit": mets.get("met_credit", tk.StringVar()).get().strip(),
                "met_transf":  mets.get("met_transf", tk.StringVar()).get().strip(),
                "met_cxc":     mets.get("met_cxc",    tk.StringVar()).get().strip(),
            }
        guardar_config(self.cfg_path, max_f, intv, num02, numLP,
                       per_empresa=per_empresa,
                       kw_bolsa=self.var_kw_bolsa.get().strip(),
                       auto_nit=self.var_auto_nit.get())
        self.num_inicio_02_orig = num02
        self.num_inicio_lp_orig = numLP

        # ── Guardar equivalencia de vendedores ────────────────────────────────
        ruta_vend = os.path.join(self.carpeta, "alegra_vendedores.dbf")
        STRUCT_VEND = "seller_id C(10); empresa C(5); cod_mes N(6,0)"
        try:
            # Recoger mapeos desde la UI
            mapeos = []
            for emp, vars_sid in getattr(self, '_vars_vendedores', {}).items():
                for sid, var in vars_sid.items():
                    display = var.get().strip()
                    cod_mes = getattr(self, '_cod_mes_map_vend', {}).get(display, 0)
                    if cod_mes:
                        mapeos.append({"seller_id": sid[:10], "empresa": emp[:5],
                                       "cod_mes": cod_mes})
            if mapeos:
                # Recrear tabla completa
                if os.path.exists(ruta_vend):
                    os.remove(ruta_vend)
                tv = dbf.Table(ruta_vend, STRUCT_VEND, dbf_type='vfp', codepage='cp1252')
                tv.open(dbf.READ_WRITE)
                for m in mapeos:
                    tv.append(m)
                tv.close()
        except Exception as e:
            messagebox.showwarning("Vendedores", f"No se pudo guardar la equivalencia de vendedores:\n{e}")

        self._marcar_guardado()
        for emp in ("02", "LP"):
            self._actualizar_estado_inputs(emp)
        messagebox.showinfo("Administrator", "Configuracion guardada.")
        return True

    # ── Sincronizar ───────────────────────────────────────────────────────────

    def sincronizar(self):
        if not self.guardar():
            return
        _timeout_s = 3600
        if os.path.exists(DAEMON_EXE):
            cmd = [DAEMON_EXE, '--run', 'ciclo']
        else:
            codigo = (
                "import sys; sys.path.insert(0, r'C:\\S.A.R'); "
                "import alegra_daemon; alegra_daemon.correr_sync()"
            )
            cmd = [sys.executable, "-c", codigo]
        r = subprocess.run(
            cmd,
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=_timeout_s,
        )
        self._refresh()
        if r.returncode != 0:
            messagebox.showerror("Error", (r.stdout + r.stderr).strip()[:600])
        else:
            messagebox.showinfo("Administrator", "Proceso completado.")


    def correr_un_ciclo(self):
        # Pausar daemon para que no interfiera
        if not os.path.exists(PAUSA_FILE):
            open(PAUSA_FILE, "w").write("pausado")
            self._cancelar_refresh()
            _matar_daemons_viejos()
            _actualizar_daemon_json()

        self._modo_manual = True
        self.lbl_daemon.config(text="Manual", fg="#1a6b2a")
        self.btn_pausa.config(text="Reanudar", bg="#cc6600")
        self.btn_un_ciclo.config(state="normal", text="Corriendo...", bg="#888", fg="white", command=lambda: None)
        self._actualizar_lbl_modo()
        self.update()

        import threading
        def _run():
            errores = []
            _sync_py     = os.path.join(os.path.dirname(__file__), "allegra_sync.py")
            _interfaz_py = os.path.join(os.path.dirname(__file__), "interfaz_allegra.py")

            # Determinar si hace falta sync: comparar pendientes locales vs max_fact por empresa
            necesita_sync = False
            _dbg = {"carpeta": self.carpeta, "error": None, "max_facts": {}, "pendientes": {}}
            try:
                max_facts = {}
                cfg_ruta = os.path.join(self.carpeta, "allegra_config.dbf")
                tc = dbf.Table(cfg_ruta, codepage="cp1252")
                tc.open(dbf.READ_ONLY)
                for rc in tc:
                    if dbf.is_deleted(rc): continue
                    emp = str(rc.empresa).strip()
                    v = int(rc.max_fact or 0)
                    max_facts[emp] = v if v > 0 else 50
                tc.close()
                _dbg["max_facts"] = max_facts

                # Contar facturas únicas sin procesar (no filas)
                pendientes = {}
                pend_ruta = os.path.join(self.carpeta, "allegra_pendientes.dbf")
                if os.path.exists(pend_ruta):
                    tp = dbf.Table(pend_ruta, codepage="cp1252")
                    tp.open(dbf.READ_ONLY)
                    fids_vistos: dict[str, set] = {}
                    for rp in tp:
                        if dbf.is_deleted(rp): continue
                        if rp.procesado: continue
                        emp = str(rp.empresa).strip()
                        fid = str(rp.factura_id).strip()
                        if emp not in fids_vistos:
                            fids_vistos[emp] = set()
                        if fid not in fids_vistos[emp]:
                            fids_vistos[emp].add(fid)
                            pendientes[emp] = pendientes.get(emp, 0) + 1
                    tp.close()
                _dbg["pendientes"] = pendientes

                for emp, max_f in max_facts.items():
                    if pendientes.get(emp, 0) < max_f:
                        necesita_sync = True
                        break
            except Exception as e:
                necesita_sync = True  # ante la duda, sync
                _dbg["error"] = str(e)
            finally:
                _dbg["necesita_sync"] = necesita_sync
                try:
                    with open(r"C:\S.A.R\ciclo_debug.txt", "a", encoding="utf-8") as _f:
                        _f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {_dbg}\n")
                except Exception:
                    pass

            scripts = []
            if necesita_sync:
                scripts.append(("allegra_sync", _sync_py))
            scripts.append(("interfaz_allegra", _interfaz_py))

            _timeout_s = 3600
            for nombre, script in scripts:
                try:
                    r = subprocess.run(
                        [sys.executable, script],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=_timeout_s,
                    )
                    if r.returncode != 0:
                        errores.append(f"{nombre}: {(r.stdout + r.stderr).strip()[:200]}")
                except Exception as e:
                    errores.append(f"{nombre}: {e}")
            self.after(0, lambda: self._post_ciclo(errores))

        threading.Thread(target=_run, daemon=True).start()

    def _post_ciclo(self, errores):
        self.btn_un_ciclo.config(state="normal", text="▶ Un ciclo", bg="#1a6b2a", fg="white", command=self.correr_un_ciclo)
        self.lbl_daemon.config(text="Manual", fg="#1a6b2a")
        self._actualizar_lbl_modo()
        self._refresh()
        self._refrescar_facturas()
        self._refrescar_terceros()
        if errores:
            messagebox.showerror("Ciclo con errores", "\n".join(errores))

    def _post_reiniciar(self, errores, mins_por_empresa: dict):
        self.btn_reiniciar.config(state="normal", text="Reiniciar proceso", bg="#8b0000", fg="white", command=self.reiniciar_proceso)
        _actualizar_daemon_json()
        # Limpiar contadores del JSON
        try:
            import json as _json
            jp = os.path.join(os.path.dirname(__file__), "estado_proceso.json")
            if os.path.exists(jp):
                with open(jp, encoding="utf-8") as f:
                    j = _json.load(f)
                for emp in j.get("facturas", {}):
                    j["facturas"][emp] = {"pendientes": 0, "inconsistencias": 0, "procesadas": 0}
                j["ultimo_ciclo"] = {"fecha": "", "procesadas": 0}
                j["terceros"] = []
                j["ultimo_log"] = ""
                for cfg in j.get("allegra_config", []):
                    cfg["total_proc"] = 0
                with open(jp, "w", encoding="utf-8") as f:
                    _json.dump(j, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        if errores:
            messagebox.showerror("Reinicio con errores", "\n".join(errores))

        # Refrescar grillas inmediatamente tras el reinicio
        self._refresh()
        self._refrescar_facturas()
        self._refrescar_terceros()

        # ── Bloquear Reanudar y Un ciclo hasta confirmar num_inicio ──────────
        self.btn_pausa.config(state="disabled")
        self.btn_un_ciclo.config(state="normal", text="▶ Un ciclo", bg="#888", fg="white", command=lambda: None)

        self._dialogo_num_inicio_reinicio(mins_por_empresa)

    def _dialogo_num_inicio_reinicio(self, mins_por_empresa: dict):
        """
        Diálogo obligatorio post-reinicio.
        Muestra el MIN por empresa encontrado (- 1) como sugerido de nuevo num_inicio.
        El usuario confirma o corrige. Sin confirmar no puede reanudar ni correr ciclo.
        """
        dlg = tk.Toplevel(self)
        dlg.transient(self)
        dlg.title("Confirmar número de inicio")
        dlg.resizable(False, False)
        dlg.protocol("WM_DELETE_WINDOW", lambda: None)  # no se puede cerrar con X
        dlg.attributes("-topmost", True)

        tk.Label(dlg, text="El reinicio borró registros de Administrator.\n"
                            "Defina desde qué número de factura debe volver a procesar\n"
                            "cada empresa. Las facturas con número MAYOR a este se descargarán.",
                 font=("Arial", 9), justify="left", padx=16, pady=(12, 4)).grid(
                 row=0, column=0, columnspan=2, sticky="w")

        # Empresas conocidas: 02 y LP
        EMPRESAS_UI = [("02", "02 TV & Video"), ("LP", "LP J&P")]
        vars_ni = {}

        dlg_row = 1
        for emp, label in EMPRESAS_UI:
            prefix, min_n = mins_por_empresa.get(emp, ("", 0))
            sug_n = max(0, min_n - 1)
            sug = f"{prefix}{sug_n}" if prefix else ""

            tk.Label(dlg, text=f"{label}:", font=("Arial", 9, "bold"),
                     anchor="e", width=18).grid(row=dlg_row, column=0, padx=(16, 4), pady=(6,0), sticky="e")
            var = tk.StringVar(value=sug)
            vars_ni[emp] = var
            ent = tk.Entry(dlg, textvariable=var, width=18, font=("Arial", 9))
            ent.grid(row=dlg_row, column=1, padx=(0, 16), pady=(6,0), sticky="w")
            dlg_row += 1
            hint = f"sugerido: {prefix}{min_n}" if sug else "sin facturas borradas — ingresar manualmente"
            hint_color = "#27ae60" if sug else "#cc6600"
            tk.Label(dlg, text=hint, font=("Arial", 8), fg=hint_color).grid(
                     row=dlg_row, column=0, columnspan=2, padx=20, pady=(0,4), sticky="w")
            dlg_row += 1

        tk.Label(dlg, text="", height=1).grid(row=dlg_row, column=0)
        dlg_row += 1

        def _confirmar():
            ni_02 = vars_ni["02"].get().strip().upper()
            ni_lp = vars_ni["LP"].get().strip().upper()
            if not ni_02 or not ni_lp:
                messagebox.showwarning("Requerido",
                    "Debe ingresar el número de inicio para ambas empresas.",
                    parent=dlg)
                return
            # Guardar en allegra_config.dbf
            ruta_cfg = os.path.join(self.carpeta, "allegra_config.dbf")
            try:
                tc = dbf.Table(ruta_cfg, codepage="cp1252")
                tc.open(dbf.READ_WRITE)
                for rc in tc:
                    if dbf.is_deleted(rc): continue
                    emp = str(rc.empresa).strip().upper()
                    with rc:
                        rc.num_inicio = (ni_02 if emp == "02" else ni_lp)[:20]
                tc.close()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar num_inicio:\n{e}", parent=dlg)
                return
            dlg.destroy()
            # Actualizar entries del tab Configuracion
            if "02" in self._vars_num_ini:
                self._vars_num_ini["02"].set(ni_02)
            if "LP" in self._vars_num_ini:
                self._vars_num_ini["LP"].set(ni_lp)
            self._marcar_guardado()
            # Habilitar botones
            self.btn_pausa.config(state="normal")
            self.btn_un_ciclo.config(state="normal", text="▶ Un ciclo", bg="#1a6b2a", fg="white", command=self.correr_un_ciclo)
            messagebox.showinfo("Listo",
                f"Número de inicio actualizado.\n"
                f"02: {ni_02}   LP: {ni_lp}\n\n"
                "Puede reanudar o correr un ciclo.")
            self._refresh()
            self._refrescar_facturas()
            self._refrescar_terceros()

        tk.Button(dlg, text="Confirmar y continuar", bg="#1a7a1a", fg="white",
                  font=("Arial", 9, "bold"), command=_confirmar,
                  padx=12, pady=4).grid(row=dlg_row, column=0, columnspan=2, pady=(4, 14))

        dlg.update_idletasks()
        dw = dlg.winfo_reqwidth()
        dh = dlg.winfo_reqheight()
        px = self.winfo_rootx()
        py = self.winfo_rooty()
        pw = self.winfo_width()
        ph = self.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        dlg.geometry(f"{dw}x{dh}+{x}+{y}")
        dlg.update()
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()
        self.wait_window(dlg)

    def _vfp_delete_en_tabla(self, carpeta, tabla, campo, cods, errores, nombre):
        """
        Borra registros en tabla VFP usando VFP COM para mantener el CDX actualizado.
        VFP's DELETE actualiza el índice CDX; Python's dbf.delete() no lo hace.
        cods: set de strings en MAYÚSCULAS a comparar con campo.strip().upper()
        """
        import pythoncom
        import win32com.client as wc
        import tempfile

        if not cods:
            return
        ruta_tabla = os.path.join(carpeta, tabla)
        if not os.path.exists(ruta_tabla):
            return

        # Escribir códigos a temp file (uno por línea)
        txt_fd, txt_path = tempfile.mkstemp(suffix='.txt')
        prg_fd, prg_path = tempfile.mkstemp(suffix='.prg')
        try:
            with os.fdopen(txt_fd, 'w', encoding='ascii', errors='replace') as tf:
                for c in sorted(cods):
                    tf.write(str(c).strip().upper()[:20] + '\n')

            tabla_esc = ruta_tabla.replace("\\", "\\\\")
            txt_esc   = txt_path.replace("\\", "\\\\")

            prg = (
                "SET EXCLUSIVE OFF\n"
                "SET DELETED OFF\n"
                "LOCAL lnH, lcLine, lcCodes\n"
                "lcCodes = \"\"\n"
                f"lnH = FOPEN(\"{txt_esc}\")\n"
                "IF lnH >= 0\n"
                "    DO WHILE NOT FEOF(lnH)\n"
                "        lcLine = TRIM(FGETS(lnH))\n"
                "        IF NOT EMPTY(lcLine)\n"
                "            lcCodes = lcCodes + CHR(124) + lcLine + CHR(124)\n"
                "        ENDIF\n"
                "    ENDDO\n"
                "    = FCLOSE(lnH)\n"
                "ENDIF\n"
                "IF LEN(lcCodes) > 0\n"
                f"    USE \"{tabla_esc}\" SHARED\n"
                "    SCAN\n"
                f"        IF CHR(124) + UPPER(TRIM({campo})) + CHR(124) $ lcCodes\n"
                "            DELETE\n"
                "        ENDIF\n"
                "    ENDSCAN\n"
                "    USE\n"
                "ENDIF\n"
            )
            with os.fdopen(prg_fd, 'w', encoding='cp1252') as pf:
                pf.write(prg)

            pythoncom.CoInitialize()
            try:
                app = wc.Dispatch('VisualFoxPro.Application.7')
                prg_esc = prg_path.replace("\\", "\\\\")
                app.DoCmd(f'DO "{prg_esc}"')
                app.Quit()
            finally:
                pythoncom.CoUninitialize()

        except Exception as e:
            errores.append(f"{nombre} (VFP COM): {e}")
        finally:
            for p in [txt_path, prg_path]:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    def _reiniciar_trabajo(self):
        # 1. Pausar
        if not os.path.exists(PAUSA_FILE):
            open(PAUSA_FILE, "w").write("pausado")
            self.after(0, self._cancelar_refresh)
            _matar_daemons_viejos()
            self.after(0, lambda: self.lbl_daemon.config(text="Pausado", fg="#cc6600"))
            self.after(0, lambda: self.btn_pausa.config(text="Reanudar", bg="#cc6600"))

        errores = []

        # 2. Recoger num_doc de allegra_pendientes ANTES de borrar
        #    También calcular MIN por empresa para sugerir nuevo num_inicio
        ruta_pend = os.path.join(self.carpeta, "allegra_pendientes.dbf")
        cods_alegra = set()
        mins_por_empresa = {}  # {empresa: (prefijo, min_n)}
        if os.path.exists(ruta_pend):
            try:
                tp = dbf.Table(ruta_pend, codepage="cp1252")
                tp.open(dbf.READ_ONLY)
                for rec in tp:
                    nd  = str(rec.num_doc).strip().upper()
                    emp = str(rec.empresa).strip().upper()
                    cods_alegra.add(nd)
                    digits = ''.join(c for c in nd if c.isdigit())
                    prefix = ''.join(c for c in nd if not c.isdigit())
                    n = int(digits) if digits else 0
                    if emp not in mins_por_empresa or n < mins_por_empresa[emp][1]:
                        mins_por_empresa[emp] = (prefix, n)
                tp.close()
            except Exception as e:
                errores.append(f"allegra_pendientes (lectura): {e}")

        # 2b. Limpiar ultima_sin en allegra_config para que el próximo sync no filtre por fecha
        ruta_cfg = os.path.join(self.carpeta, "allegra_config.dbf")
        if os.path.exists(ruta_cfg):
            try:
                tc = dbf.Table(ruta_cfg, codepage="cp1252")
                tc.open(dbf.READ_WRITE)
                from datetime import datetime as _dt
                for rc in tc:
                    if dbf.is_deleted(rc): continue
                    with rc:
                        rc.ultima_sin = _dt(2000, 1, 1)  # fuerza sync sin filtro de fecha
                tc.close()
            except Exception as e:
                errores.append(f"allegra_config ultima_sin: {e}")

        # 3. Limpiar allegra_pendientes.dbf
        if os.path.exists(ruta_pend):
            try:
                t = dbf.Table(ruta_pend, codepage="cp1252")
                t.open(dbf.READ_WRITE)
                for rec in t:
                    if not dbf.is_deleted(rec):
                        dbf.delete(rec)
                t.close()
            except Exception as e:
                errores.append(f"allegra_pendientes: {e}")

        # 4. Limpiar alegra_nits_pend.dbf
        ruta_nits = os.path.join(self.carpeta, "alegra_nits_pend.dbf")
        if os.path.exists(ruta_nits):
            try:
                t = dbf.Table(ruta_nits, codepage="cp1252")
                t.open(dbf.READ_WRITE)
                for rec in t:
                    if not dbf.is_deleted(rec):
                        dbf.delete(rec)
                t.close()
            except Exception as e:
                errores.append(f"alegra_nits_pend: {e}")

        # Si allegra_pendientes ya estaba vacío (reinicio previo lo limpió),
        # reconstruir cods_alegra desde PROD_FACT1:
        # tip_fac configurado + cod_fac con letras + número > num_inicio configurado
        if not cods_alegra:
            try:
                # Leer tip_doc y num_inicio por empresa desde allegra_config
                cfg_empresas = {}  # {tip_doc: num_inicio_n}
                ruta_cfg = os.path.join(self.carpeta, "allegra_config.dbf")
                if os.path.exists(ruta_cfg):
                    tc = dbf.Table(ruta_cfg, codepage="cp1252")
                    tc.open(dbf.READ_ONLY)
                    for rc in tc:
                        if dbf.is_deleted(rc): continue
                        td = str(getattr(rc, "tip_doc", "") or "").strip().upper()
                        ni = str(getattr(rc, "num_inicio", "") or "").strip().upper()
                        if td:
                            digits = ''.join(c for c in ni if c.isdigit())
                            cfg_empresas[td] = int(digits) if digits else 0
                    tc.close()
                ruta_pf1_scan = os.path.join(self.carpeta, "PROD_FACT1.dbf")
                if cfg_empresas and os.path.exists(ruta_pf1_scan):
                    ts = dbf.Table(ruta_pf1_scan, codepage="cp1252")
                    ts.open(dbf.READ_ONLY)
                    for rs in ts:
                        if dbf.is_deleted(rs): continue
                        tip = str(rs.tip_fac).strip().upper()
                        if tip not in cfg_empresas: continue
                        cod = str(rs.cod_fac).strip().upper()
                        if not any(c.isalpha() for c in cod): continue
                        digits = ''.join(c for c in cod if c.isdigit())
                        n = int(digits) if digits else 0
                        if n > cfg_empresas[tip]:
                            cods_alegra.add(cod)
                    ts.close()
            except Exception as e:
                errores.append(f"reconstruccion cods_alegra: {e}")

        if cods_alegra:
            # 5-9: borrar via VFP COM para que DELETE actualice el CDX correctamente
            # (Python's dbf.delete() marca 0x2A pero NO actualiza el CDX estructural,
            #  lo que deja entradas obsoletas que VFP Rushmore usa devolviendo registros erróneos)

            # 5. PROD_FACT1
            self._vfp_delete_en_tabla(self.carpeta, "PROD_FACT1.dbf", "COD_FAC",
                                       cods_alegra, errores, "PROD_FACT1")

            # 6. REG_PROD (standar)
            self._vfp_delete_en_tabla(self.carpeta, "REG_PROD.dbf", "NUM_DOC",
                                       cods_alegra, errores, "REG_PROD")

            # 7. REG_CTAS (costos + contabilización)
            self._vfp_delete_en_tabla(self.carpeta, "REG_CTAS.dbf", "DOCUMENTO",
                                       cods_alegra, errores, "REG_CTAS")

            # 8. SAL_DOC
            self._vfp_delete_en_tabla(self.carpeta, "SAL_DOC.dbf", "NUM_DOC",
                                       cods_alegra, errores, "SAL_DOC")

            # 9. reg_ctas_notas_documentos — detectar campo dinámicamente
            ruta_notas = os.path.join(self.carpeta, "reg_ctas_notas_documentos.dbf")
            if os.path.exists(ruta_notas):
                try:
                    tn = dbf.Table(ruta_notas, codepage="cp1252")
                    tn.open(dbf.READ_ONLY)
                    campos_n = [f.lower() for f in tn.field_names]
                    tn.close()
                    campo_doc = "NUM_DOC" if "num_doc" in campos_n else ("DOCUMENTO" if "documento" in campos_n else None)
                except Exception as e:
                    campo_doc = None
                    errores.append(f"reg_ctas_notas_documentos (campo): {e}")
                if campo_doc:
                    self._vfp_delete_en_tabla(self.carpeta, "reg_ctas_notas_documentos.dbf",
                                               campo_doc, cods_alegra, errores,
                                               "reg_ctas_notas_documentos")

        # 4b. Limpiar tablas staging (stg_lotes y tablas de detalle)
        stg_tablas = [
            "stg_lotes", "stg_prod_fact1", "stg_reg_prod", "stg_reg_prod_sal",
            "stg_reg_ctas", "stg_sal_doc", "stg_nota", "stg_terceros",
        ]
        for nombre_stg in stg_tablas:
            ruta_stg = os.path.join(self.carpeta, f"{nombre_stg}.dbf")
            if os.path.exists(ruta_stg):
                try:
                    ts = dbf.Table(ruta_stg, codepage="cp1252")
                    ts.open(dbf.READ_WRITE)
                    for rs in ts:
                        if not dbf.is_deleted(rs):
                            dbf.delete(rs)
                    ts.close()
                except Exception as e:
                    errores.append(f"{nombre_stg}: {e}")

        self.after(0, lambda: self._post_reiniciar(errores, mins_por_empresa))

        # (fin del hilo — no tocar widgets desde aquí)

    def reiniciar_proceso(self):
        if not messagebox.askyesno("Reiniciar proceso",
                "Esto borrará TODOS los registros descargados de Alegra\n"
                "y los registros creados en Administrator por este proceso.\n\n"
                "¿Está seguro?", icon="warning"):
            return
        if not messagebox.askyesno("Confirmar reinicio",
                "Segunda confirmación requerida.\n\n"
                "Se eliminarán los registros de Alegra en:\n"
                "  • allegra_pendientes.dbf\n"
                "  • alegra_nits_pend.dbf\n"
                "  • PROD_FACT1.dbf\n"
                "  • REG_PROD.dbf\n"
                "  • REG_CTAS.dbf\n"
                "  • SAL_DOC.dbf\n"
                "  • reg_ctas_notas_documentos.dbf\n\n"
                "¿Continuar?", icon="warning"):
            return
        self.btn_reiniciar.config(state="normal", text="Reiniciando...", bg="#555", fg="white", command=lambda: None)
        self.update_idletasks()
        import threading
        threading.Thread(target=self._reiniciar_trabajo, daemon=True).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
