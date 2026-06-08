import os
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env_file():
    env_path = ROOT / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

from app import create_app  # noqa: E402
from app.db import get_db_connection  # noqa: E402
from app.blueprints.compras import _asegurar_tablas  # noqa: E402


SLUG = 'home-solar-panel'
PROVEEDOR = 'Fibrandina'
CONTACTO = 'Cristian'
NUMERO_COTIZACION = 'FIBRANDINA-CATALOGO-SOLAR'


def seed():
    create_app()
    conn = get_db_connection()
    try:
        _asegurar_tablas(conn)
        tienda = conn.execute(
            "SELECT tercero_id, nombre FROM tiendas WHERE slug = %s AND activo = TRUE",
            (SLUG,),
        ).fetchone()
        if not tienda or not tienda['tercero_id']:
            raise RuntimeError(f"No existe tienda activa con slug {SLUG} o no tiene tercero_id")

        proveedor = conn.execute(
            "SELECT id FROM terceros WHERE LOWER(nombre) = LOWER(%s) LIMIT 1",
            (PROVEEDOR,),
        ).fetchone()
        if proveedor:
            proveedor_id = proveedor['id']
        else:
            proveedor = conn.execute(
                "INSERT INTO terceros (nombre) VALUES (%s) RETURNING id",
                (PROVEEDOR,),
            ).fetchone()
            proveedor_id = proveedor['id']

        productos = conn.execute(
            """
            SELECT id, nombre, categoria, costo
            FROM productos
            WHERE negocio_id = %s
              AND COALESCE(costo, 0) > 0
            ORDER BY categoria, orden, nombre
            """,
            (tienda['tercero_id'],),
        ).fetchall()

        fecha_cotizacion = date.today()
        fecha_vencimiento = fecha_cotizacion + timedelta(days=180)
        creadas = 0
        actualizadas = 0
        for producto in productos:
            existente = conn.execute(
                """
                SELECT id
                FROM cotizaciones_compras
                WHERE negocio_id = %s
                  AND tercero_id = %s
                  AND item_id = %s
                  AND numero_cotizacion = %s
                LIMIT 1
                """,
                (tienda['tercero_id'], proveedor_id, producto['id'], NUMERO_COTIZACION),
            ).fetchone()
            params = (
                fecha_cotizacion,
                fecha_vencimiento,
                'Unidad',
                1,
                float(producto['costo']),
                'catalogo_proveedor',
                True,
                f'Proveedor: {PROVEEDOR}. Contacto: {CONTACTO}.',
            )
            if existente:
                conn.execute(
                    """
                    UPDATE cotizaciones_compras
                    SET fecha_cotizacion=%s, fecha_vencimiento=%s,
                        descripcion_presentacion=%s, unidades_item=%s,
                        precio=%s, origen=%s, validada_proveedor=%s,
                        observaciones=%s, updated_at=NOW()
                    WHERE id=%s
                    """,
                    params + (existente['id'],),
                )
                actualizadas += 1
            else:
                conn.execute(
                    """
                    INSERT INTO cotizaciones_compras
                        (negocio_id, numero_cotizacion, tercero_id, item_id,
                         fecha_cotizacion, fecha_vencimiento, descripcion_presentacion,
                         unidades_item, precio, origen, validada_proveedor, observaciones,
                         updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    """,
                    (
                        tienda['tercero_id'], NUMERO_COTIZACION, proveedor_id, producto['id'],
                    ) + params,
                )
                creadas += 1

        conn.commit()
        print(f"Tienda: {tienda['nombre']} ({SLUG})")
        print(f"Proveedor: {PROVEEDOR} | Contacto: {CONTACTO} | tercero_id={proveedor_id}")
        print(f"Cotizaciones creadas: {creadas}")
        print(f"Cotizaciones actualizadas: {actualizadas}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    seed()
