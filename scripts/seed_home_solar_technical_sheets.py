"""
Carga fichas tecnicas solares estructuradas para productos de Home Solar Panel.

Los datos provienen de las fichas PDF locales disponibles para paneles y
baterias; algunos inversores quedan con datos basicos inferidos del nombre del
producto hasta completar sus fichas tecnicas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.db import get_db_connection  # noqa: E402
from app.blueprints.tiendas import _crear_tablas  # noqa: E402


FICHAS = {
    242: ("panel", {"potencia_w": 330, "eficiencia_pct": 17.01, "voc_v": 46.36, "isc_a": 9.30, "ancho_mm": 992, "alto_mm": 1956}),
    244: ("panel", {"potencia_w": 450, "eficiencia_pct": 20.67, "voc_v": 49.98, "isc_a": 11.54, "ancho_mm": 1039, "alto_mm": 2095}),
    243: ("panel", {"potencia_w": 550, "eficiencia_pct": 21.28, "voc_v": 50.32, "isc_a": 13.90, "ancho_mm": 1134, "alto_mm": 2279}),
    245: ("panel", {"potencia_w": 585, "eficiencia_pct": 22.65, "voc_v": 48.27, "isc_a": 15.33, "ancho_mm": 1134, "alto_mm": 2278}),
    246: ("panel", {"potencia_w": 630}),

    187: ("bateria", {"tipo_bateria": "Gel", "capacidad_nominal_kwh": 1.20, "capacidad_util_pct": 50, "voltaje_nominal_v": 12, "amperios_hora_ah": 100}),
    188: ("bateria", {"tipo_bateria": "Gel", "capacidad_nominal_kwh": 1.80, "capacidad_util_pct": 50, "voltaje_nominal_v": 12, "amperios_hora_ah": 150}),
    189: ("bateria", {"tipo_bateria": "Gel", "capacidad_nominal_kwh": 2.40, "capacidad_util_pct": 50, "voltaje_nominal_v": 12, "voltaje_min_descarga_v": 10.8, "voltaje_max_carga_v": 14.9, "voltaje_flotacion_v": 13.8, "amperios_hora_ah": 200, "potencia_max_descarga_w": 14400, "corriente_max_descarga_a": 1200, "ciclos_estimados": 1500, "peso_kg": 58.6}),
    190: ("bateria", {"tipo_bateria": "Gel", "capacidad_nominal_kwh": 3.00, "capacidad_util_pct": 50, "voltaje_nominal_v": 12, "voltaje_min_descarga_v": 10.8, "voltaje_max_carga_v": 14.9, "voltaje_flotacion_v": 13.8, "amperios_hora_ah": 250, "potencia_max_descarga_w": 17280, "corriente_max_descarga_a": 1440, "ciclos_estimados": 1500, "peso_kg": 71.3}),
    193: ("bateria", {"tipo_bateria": "LiFePO4", "capacidad_nominal_kwh": 1.28, "capacidad_util_pct": 80, "voltaje_nominal_v": 12.8, "voltaje_min_descarga_v": 10, "voltaje_max_carga_v": 14.6, "amperios_hora_ah": 100, "potencia_max_descarga_w": 1280, "corriente_max_descarga_a": 100, "ciclos_estimados": 6000, "peso_kg": 12}),
    194: ("bateria", {"tipo_bateria": "LiFePO4", "capacidad_nominal_kwh": 2.56, "capacidad_util_pct": 80, "voltaje_nominal_v": 12.8, "voltaje_min_descarga_v": 10, "voltaje_max_carga_v": 14.6, "amperios_hora_ah": 200, "potencia_max_descarga_w": 1280, "corriente_max_descarga_a": 100, "ciclos_estimados": 6000, "peso_kg": 21}),
    195: ("bateria", {"tipo_bateria": "LiFePO4", "capacidad_nominal_kwh": 3.20, "capacidad_util_pct": 80, "voltaje_nominal_v": 25.6, "voltaje_min_descarga_v": 20, "voltaje_max_carga_v": 29.2, "amperios_hora_ah": 125, "potencia_max_descarga_w": 2560, "corriente_max_descarga_a": 100, "ciclos_estimados": 6000, "peso_kg": 25}),
    196: ("bateria", {"tipo_bateria": "LiFePO4", "capacidad_nominal_kwh": 5.12, "capacidad_util_pct": 80, "voltaje_nominal_v": 51.2, "voltaje_min_descarga_v": 44, "voltaje_max_carga_v": 58.4, "amperios_hora_ah": 100, "potencia_max_descarga_w": 5000, "corriente_max_descarga_a": 100, "ciclos_estimados": 6000, "peso_kg": 45}),
    197: ("bateria", {"tipo_bateria": "LiFePO4", "capacidad_nominal_kwh": 10.24, "capacidad_util_pct": 80, "voltaje_nominal_v": 51.2, "voltaje_min_descarga_v": 44, "voltaje_max_carga_v": 58.4, "amperios_hora_ah": 200, "potencia_max_descarga_w": 7500, "corriente_max_descarga_a": 150, "ciclos_estimados": 6000, "peso_kg": 80}),

    206: ("inversor", {"tipo_inversor": "On-grid", "potencia_nominal_w": 6000, "voltaje_ac_salida_v": 220, "numero_mppt": 2}),
    207: ("inversor", {"tipo_inversor": "On-grid", "potencia_nominal_w": 10000, "voltaje_ac_salida_v": 220, "fases": "Trifasico", "numero_mppt": 2}),
    208: ("inversor", {"tipo_inversor": "On-grid", "potencia_nominal_w": 60000, "fases": "Trifasico"}),
    209: ("inversor", {"tipo_inversor": "On-grid", "potencia_nominal_w": 10000, "fases": "Trifasico"}),
    210: ("inversor", {"tipo_inversor": "On-grid", "potencia_nominal_w": 15000, "fases": "Trifasico"}),
    211: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 8000, "fases": "Split phase"}),
    212: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 12000, "fases": "Split phase"}),
    213: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 30000, "fases": "Trifasico"}),
    224: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 1000, "voltaje_banco_bateria_v": 12}),
    225: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 1500, "voltaje_banco_bateria_v": 24}),
    226: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 2000, "voltaje_banco_bateria_v": 24}),
    227: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 3000, "voltaje_ac_salida_v": 120, "corriente_max_fv_a": 80}),
    228: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 3000, "voltaje_banco_bateria_v": 24}),
    229: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 6000, "voltaje_banco_bateria_v": 48, "fases": "Split phase"}),
    230: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 8000, "voltaje_banco_bateria_v": 48, "fases": "Split phase"}),
    231: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 12000, "voltaje_banco_bateria_v": 48, "fases": "Split phase"}),
    232: ("inversor", {"tipo_inversor": "Hibrido", "potencia_nominal_w": 12000, "voltaje_banco_bateria_v": 48, "corriente_max_fv_a": 200}),
    233: ("inversor", {"tipo_inversor": "On-grid", "potencia_nominal_w": 6000, "voltaje_ac_salida_v": 220, "fases": "Trifasico"}),
}


def seed() -> None:
    create_app()
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        for producto_id, (tipo, datos) in FICHAS.items():
            conn.execute(
                """
                INSERT INTO producto_fichas_solares (producto_id, tipo, datos, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (producto_id) DO UPDATE
                SET tipo = EXCLUDED.tipo, datos = EXCLUDED.datos, updated_at = NOW()
                """,
                (producto_id, tipo, json.dumps(datos)),
            )
        conn.commit()
        print(f"Fichas solares cargadas: {len(FICHAS)}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
