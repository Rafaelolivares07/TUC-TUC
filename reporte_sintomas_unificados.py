import sqlite3
from datetime import datetime
import os

DB_PATH = "medicamentos.db"
OUTPUT_HTML = f"reporte_sintomas_unificados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

def obtener_grupos_componentes(conn):
    query = """
        SELECT DISTINCT componente_activo_id
        FROM MEDICAMENTOS
        WHERE componente_activo_id IS NOT NULL
        ORDER BY componente_activo_id;
    """
    return [row[0] for row in conn.execute(query).fetchall()]

def obtener_medicamentos_por_componente(conn, componente_id):
    query = """
        SELECT id, nombre
        FROM MEDICAMENTOS
        WHERE componente_activo_id = ?;
    """
    return conn.execute(query, (componente_id,)).fetchall()

def obtener_sintomas_de_medicamento(conn, medicamento_id):
    query = """
        SELECT s.id, s.nombre
        FROM MEDICAMENTO_SINTOMA ms
        JOIN SINTOMAS s ON s.id = ms.sintoma_id
        WHERE ms.medicamento_id = ?;
    """
    return conn.execute(query, (medicamento_id,)).fetchall()

def generar_html(resultados, stats):
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte de Síntomas Unificados</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 30px;
                background: #f4f6f8;
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
                background-color: #f9f9f9;
            }}
            .faltantes {{
                color: #e74c3c;
                font-weight: bold;
            }}
            .todos {{
                color: #16a085;
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
            .card span {{
                font-size: 1.8em;
                font-weight: bold;
                color: #27ae60;
            }}
            button {{
                background: #2ecc71;
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                display: block;
                margin: 30px auto;
            }}
            button:hover {{
                background: #27ae60;
            }}
        </style>
    </head>
    <body>
        <h1>Reporte de Síntomas Unificados por Componente Activo</h1>
        <p style="text-align:center;">Este reporte muestra qué síntomas faltan a cada medicamento para igualar al resto de su grupo.</p>

        <button id="syncButton">🧩 Aplicar sincronización</button>

        <script>
            document.getElementById('syncButton').addEventListener('click', async () => {{
                if (confirm("¿Deseas aplicar la sincronización en la base de datos?")) {{
                    const resp = await fetch('http://127.0.0.1:5001/sincronizar', {{ method: 'POST' }});
                    const data = await resp.json();
                    alert(data.mensaje);
                    if (data.ok) location.reload();
                }}
            }});
        </script>
    """

    for grupo in resultados:
        html += f"""
        <h2>Componente Activo ID: {grupo['componente_id']}</h2>
        <p><strong>Total de síntomas únicos del grupo:</strong> {grupo['total_sintomas_grupo']}</p>
        <table>
            <thead>
                <tr>
                    <th>Medicamento</th>
                    <th>Síntomas actuales</th>
                    <th>Síntomas faltantes sugeridos</th>
                </tr>
            </thead>
            <tbody>
        """
        for med in grupo["medicamentos"]:
            html += f"""
            <tr>
                <td>{med['nombre']}</td>
                <td class="todos">{', '.join(med['actuales']) if med['actuales'] else '-'}</td>
                <td class="faltantes">{', '.join(med['faltantes']) if med['faltantes'] else '— Ninguno —'}</td>
            </tr>
            """
        html += "</tbody></table><br>"

    html += f"""
        <h2>Resumen Global</h2>
        <div class="stats">
            <div class="card"><h3>Componentes Analizados</h3><span>{stats['componentes']}</span></div>
            <div class="card"><h3>Medicamentos Revisados</h3><span>{stats['medicamentos']}</span></div>
            <div class="card"><h3>Síntomas Totales</h3><span>{stats['sintomas_totales']}</span></div>
            <div class="card"><h3>Faltantes Totales</h3><span>{stats['faltantes_totales']}</span></div>
        </div>
    </body>
    </html>
    """
    return html


def generar_reporte():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    componentes = obtener_grupos_componentes(conn)
    resultados = []
    total_meds = 0
    total_sintomas = 0
    total_faltantes = 0

    for componente_id in componentes:
        meds = obtener_medicamentos_por_componente(conn, componente_id)
        if not meds:
            continue

        sintomas_por_med = {}
        total_meds += len(meds)

        for m in meds:
            sintomas = obtener_sintomas_de_medicamento(conn, m["id"])
            sintomas_por_med[m["id"]] = {s["nombre"] for s in sintomas}

        sintomas_grupo = set().union(*sintomas_por_med.values())
        total_sintomas += len(sintomas_grupo)

        grupo_data = {
            "componente_id": componente_id,
            "total_sintomas_grupo": len(sintomas_grupo),
            "medicamentos": []
        }

        for m in meds:
            actuales = sorted(list(sintomas_por_med[m["id"]]))
            faltantes = sorted(list(sintomas_grupo - sintomas_por_med[m["id"]]))
            total_faltantes += len(faltantes)
            grupo_data["medicamentos"].append({
                "id": m["id"],
                "nombre": m["nombre"],
                "actuales": actuales,
                "faltantes": faltantes
            })

        resultados.append(grupo_data)

    stats = {
        "componentes": len(resultados),
        "medicamentos": total_meds,
        "sintomas_totales": total_sintomas,
        "faltantes_totales": total_faltantes
    }

    html = generar_html(resultados, stats)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    conn.close()
    print(f"✅ Reporte HTML generado: {os.path.abspath(OUTPUT_HTML)}")

if __name__ == "__main__":
    generar_reporte()
