"""Condiciones comerciales, enlaces y comisiones de pedidos del Marketplace."""
import json
import re
from decimal import Decimal
from secrets import token_urlsafe

from .asegurar import asegurar_una_vez
from .db import get_db_connection

COOKIE_CAMPANA = "__Host-tuctuc_campana"
VIGENCIA_CAMPANA = 7 * 86400
COMISION_MINIMA_PCT = Decimal("10")
PARTE_PROMOTOR_PREDETERMINADA = Decimal("80")
CANALES = {
    "tuctuc": "Promoción de Tuc-Tuc",
    "promotor": "Promoción del promotor",
    "pauta_promotor": "Pauta financiada por el promotor",
}


def porcentaje(valor):
    texto = str(valor if valor is not None else "").strip().replace(",", ".")
    if not re.fullmatch(r"[0-9]{1,2}(\.[0-9]{1,2})?", texto) or not Decimal(texto):
        raise ValueError("Indica un porcentaje mayor a 0 y menor a 100.")
    return Decimal(texto)


def porcentaje_comision(valor):
    comision = porcentaje(valor)
    if comision < COMISION_MINIMA_PCT:
        raise ValueError(f"La comisión mínima es del {COMISION_MINIMA_PCT}%.")
    return comision


def _crear_tablas():
    with get_db_connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("marketplace.comisiones.schema",))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS marketplace_condiciones (
                producto_id integer PRIMARY KEY REFERENCES productos(id) ON DELETE CASCADE,
                negocio_id integer NOT NULL REFERENCES terceros(id),
                comision_pct numeric(4,2) NOT NULL CHECK (comision_pct > 0 AND comision_pct < 100),
                parte_promotor_pct numeric(4,2) NOT NULL CHECK (parte_promotor_pct > 50 AND parte_promotor_pct < 100),
                activa boolean NOT NULL DEFAULT TRUE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS marketplace_campanas (
                codigo text PRIMARY KEY,
                producto_id integer NOT NULL REFERENCES marketplace_condiciones(producto_id) ON DELETE CASCADE,
                negocio_id integer NOT NULL REFERENCES terceros(id),
                canal text NOT NULL CHECK (canal IN ('tuctuc','promotor','pauta_promotor')),
                promotor_id integer REFERENCES terceros(id),
                activa boolean NOT NULL DEFAULT TRUE,
                creada_en timestamptz NOT NULL DEFAULT now(),
                CHECK ((canal = 'tuctuc') = (promotor_id IS NULL)),
                CHECK (promotor_id IS DISTINCT FROM negocio_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS marketplace_comisiones_pedido (
                pedido_id integer NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                producto_id integer NOT NULL,
                negocio_id integer NOT NULL REFERENCES terceros(id),
                canal text NOT NULL CHECK (canal IN ('organico','tuctuc','promotor','pauta_promotor')),
                codigo_campana text,
                promotor_id integer REFERENCES terceros(id),
                base_cop numeric(14,2) NOT NULL,
                comision_pct numeric(4,2) NOT NULL,
                promotor_cop numeric(14,2) NOT NULL,
                tuctuc_cop numeric(14,2) NOT NULL,
                PRIMARY KEY (pedido_id, producto_id)
            )
        """)
        conn.commit()


def asegurar_comisiones():
    asegurar_una_vez("marketplace.comisiones", _crear_tablas)


def activar_condiciones(conn, producto_id, negocio_id, comision, parte_promotor=None):
    conn.execute("""
        INSERT INTO marketplace_condiciones (producto_id, negocio_id, comision_pct, parte_promotor_pct)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (producto_id) DO UPDATE
            SET negocio_id=excluded.negocio_id, comision_pct=excluded.comision_pct,
                parte_promotor_pct=CASE WHEN marketplace_condiciones.negocio_id=excluded.negocio_id
                    THEN COALESCE(%s, marketplace_condiciones.parte_promotor_pct)
                    ELSE excluded.parte_promotor_pct END, activa=TRUE
    """, (producto_id, negocio_id, comision,
          parte_promotor or PARTE_PROMOTOR_PREDETERMINADA, parte_promotor))


def crear_campana(conn, producto_id, negocio_id, canal, promotor_id):
    codigo = token_urlsafe(18)
    conn.execute("""
        INSERT INTO marketplace_campanas (codigo, producto_id, negocio_id, canal, promotor_id)
        VALUES (%s,%s,%s,%s,%s)
    """, (codigo, producto_id, negocio_id, canal, promotor_id))
    return codigo


def buscar_campana(conn, codigo):
    if not isinstance(codigo, str) or not re.fullmatch(r"[A-Za-z0-9_-]{24}", codigo):
        return None
    return conn.execute("""
        SELECT c.* FROM marketplace_campanas c
         JOIN marketplace_condiciones t ON t.producto_id=c.producto_id AND t.negocio_id=c.negocio_id
         WHERE c.codigo=%s AND c.activa AND t.activa
    """, (codigo,)).fetchone()


def registrar_comisiones(conn, pedido_id, origenes):
    # Usa el precio guardado por el motor de pedidos, sin domicilio ni montos del navegador.
    conn.execute("""
        WITH base AS (
            SELECT i.producto_id, p.negocio_id, SUM(i.precio_unitario::numeric * i.cantidad) AS base_cop,
                   t.comision_pct, t.parte_promotor_pct,
                   c.codigo, COALESCE(c.canal,'organico') AS canal, c.promotor_id
              FROM pedido_items i
              JOIN pedidos p ON p.id=i.pedido_id
              JOIN marketplace_condiciones t ON t.producto_id=i.producto_id AND t.negocio_id=p.negocio_id AND t.activa
              LEFT JOIN marketplace_campanas c ON c.codigo=(%s::jsonb ->> i.producto_id::text) AND c.producto_id=t.producto_id
                   AND c.negocio_id=t.negocio_id AND c.activa
                   AND (c.promotor_id IS NULL OR c.promotor_id IS DISTINCT FROM p.cliente_id)
             WHERE p.id=%s
             GROUP BY i.producto_id,p.negocio_id,t.comision_pct,t.parte_promotor_pct,c.codigo,c.canal,c.promotor_id
            HAVING SUM(i.precio_unitario::numeric * i.cantidad)>0
        ), importes AS (
            SELECT base.*, ROUND(base_cop * comision_pct / 100, 2) AS total_comision
              FROM base
        ), reparto AS (
            SELECT importes.*, CASE WHEN promotor_id IS NOT NULL
                 THEN ROUND(total_comision * parte_promotor_pct / 100, 2) ELSE 0 END AS parte_promotor
              FROM importes
        )
        INSERT INTO marketplace_comisiones_pedido
            (pedido_id,producto_id,negocio_id,canal,codigo_campana,promotor_id,base_cop,comision_pct,promotor_cop,tuctuc_cop)
        SELECT %s,producto_id,negocio_id,canal,codigo,promotor_id,base_cop,comision_pct,parte_promotor,
               total_comision-parte_promotor
          FROM reparto
        ON CONFLICT (pedido_id,producto_id) DO NOTHING
    """, (json.dumps(origenes), pedido_id, pedido_id))
