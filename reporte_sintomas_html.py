import sqlite3
from datetime import datetime
import os

DB_PATH = "medicamentos.db"
OUTPUT_HTML = f"reporte_sintomas_sugeridos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

def obtener_medicamentos_sin_sintomas(conn):
    query = """
        SELECT m.id, m.nombre, m.componente_activo_id
        FROM MEDICAMENTOS m
        LEFT JOIN MEDICAMENTO_SINTOMA ms ON m.id = ms.medicamento_id
        WHERE ms.medicamento_id IS NULL
        ORDER BY m.componente_activo_id;
    """
    return conn.execute(query).fetchall()

def obtener_sintomas_por_componente(conn, componente_id):
    query = """
        SELECT DISTINCT s.id, s.nombre
        FROM MEDICAMENTOS m
        JOIN MEDICAMENTO_SINTOMA ms ON m.id = ms.medicamento_id
        JOIN SINTOMAS s ON s.id = ms.sintoma_id
        WHERE m.componente_activo_id = ?;
    """
    return conn.execute(query, (componente_id,)).fetchall()

def obtener_medicamentos_fuente(conn, componente_id):
    query = """
        SELECT DISTINCT m.id, m.nombre
        FROM MEDICAMENTOS m
        JOIN MEDICAMENTO_SINTOMA ms ON m.id = ms.medicamento_id
        WHERE m.componente_activo_id = ?;
    """
    return conn.execute(query, (componente_id,)).fetchall()

def generar_html(resultados, stats):
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte de Síntomas Sugeridos</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 30px;
                background: #f5f6fa;
                color: #333;
            }}
            h1, h2 {{
                text-align: center;
                color: #2c3e50;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                margin-bottom: 40px;
            }}
            th, td {{
                padding: 10px 15px;
                border-bottom: 1px solid #ddd;
                vertical-align: top;
            }}
            th {{
                background-color: #34495e;
                color: white;
                text-align: left;
            }}
            tr:hover {{
                background-color: #f1f1f1;
            }}
            .sin-sintomas {{
                color: #e74c3c;
                font-weight: bold;
            }}
            .sintomas {{
                color: #16a085;
            }}
            .fuentes {{
                color: #2980b9;
            }}
            .stats {{
                display: flex;
                flex-wrap: wrap;
                justify-content: center;
                gap: 20px;
            }}
            .card {{
                background: white;
                border-radius: 10px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                padding: 20px;
                width: 220px;
                text-align: center;
            }}
            .card h3 {{
                margin: 10px 0;
                color: #2c3e50;
            }}
            .card span {{
                font-size: 1.8em;
                font-weight: bold;
                color: #27ae60;
            }}
            footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 0.9em;
                color: #777;
            }}
        </style>
    </head>
    <body>
        <h1>Reporte de Síntomas Sugeridos por Componente Activo</h1>
        <h2>Vista Detallada</h2>
        <p>Total de medicamentos con sugerencias: <strong>{len(resultados)}</strong></p>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Medicamento sin síntomas</th>
                    <th>ID Componente Activo</th>
                    <th>Medicamentos fuente</th>
                    <th>Síntomas sugeridos</th>
                </tr>
            </thead>
            <tbody>
    """

    for i, r in enumerate(resultados, start=1):
        html += f"""
        <tr>
            <td>{i}</td>
            <td class="sin-sintomas">{r['medicamento_sin_sintomas']}</td>
            <td>{r['componente_activo_id']}</td>
            <td class="fuentes">{r['medicamentos_fuente']}</td>
            <td class="sintomas">{r['sintomas_sugeridos']}</td>
        </tr>
        """

    html += f"""
            </tbody>
        </table>

        <h2>Resumen Estadístico</h2>
        <div class="stats">
            <div class="card"><h3>Medicamentos analizados</h3><span>{stats['total_analizados']}</span></div>
            <div class="card"><h3>Sin componente activo</h3><span>{stats['sin_componente']}</span></div>
            <div class="card"><h3>Con sugerencias</h3><span>{stats['con_sugerencias']}</span></div>
            <div class="card"><h3>Sin sugerencias</h3><span>{stats['sin_sugerencias']}</span></div>
            <div class="card"><h3>Total síntomas sugeridos</h3><span>{stats['total_sintomas']}</span></div>
        </div>

        <footer>
            Generado automáticamente por <b>reporte_sintomas_html.py</b><br>
            {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </footer>
    </body>
    </html>
    """
    return html


def generar_reporte():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    medicamentos_sin = obtener_medicamentos_sin_sintomas(conn)

    total_analizados = len(medicamentos_sin)
    sin_componente = 0
    sin_sugerencias = 0
    total_sintomas = 0

    resultados = []

    for med in medicamentos_sin:
        componente_id = med["componente_activo_id"]
        if not componente_id:
            sin_componente += 1
            continue

        sintomas = obtener_sintomas_por_componente(conn, componente_id)
        meds_fuente = obtener_medicamentos_fuente(conn, componente_id)

        if not sintomas:
            sin_sugerencias += 1
            continue

        total_sintomas += len(sintomas)

        resultados.append({
            "medicamento_sin_sintomas": med["nombre"],
            "componente_activo_id": componente_id,
            "medicamentos_fuente": ", ".join(m["nombre"] for m in meds_fuente),
            "sintomas_sugeridos": ", ".join(s["nombre"] for s in sintomas)
        })

    stats = {
        "total_analizados": total_analizados,
        "sin_componente": sin_componente,
        "con_sugerencias": len(resultados),
        "sin_sugerencias": sin_sugerencias,
        "total_sintomas": total_sintomas
    }

    if not resultados:
        print("✅ No se encontraron medicamentos para sugerir síntomas.")
    else:
        html_content = generar_html(resultados, stats)
        with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"📄 Reporte HTML generado correctamente: {os.path.abspath(OUTPUT_HTML)}")

    conn.close()


if __name__ == "__main__":
    generar_reporte()
