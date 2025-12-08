import sqlite3
import os
from datetime import datetime

DB_PATH = "medicamentos.db"

def formatear_precio(valor):
    if valor is None:
        return "-"
    try:
        return f"${valor:,.0f}".replace(",", ".")
    except Exception:
        return str(valor)

def obtener_datos_precios():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ✅ Traer los precios propios
    query_propios = """
        SELECT 
            p.id as precio_id,
            p.medicamento_id,
            m.nombre as medicamento_nombre,
            p.fabricante_id,
            f.nombre as fabricante,
            p.precio AS precio_propio,
            p.fecha_actualizacion,
            p.imagen
        FROM precios p
        LEFT JOIN medicamentos m ON p.medicamento_id = m.id
        LEFT JOIN fabricantes f ON p.fabricante_id = f.id
        -- incluir TODOS los registros de la tabla `precios`, incluso si la referencia al medicamento falta
        ORDER BY medicamento_nombre ASC;
    """
    cur.execute(query_propios)
    datos_propios = cur.fetchall()

    # ✅ Crear diccionario base con precios propios
    base = {}
    # Usar clave por `precio_id` para representar exactamente cada fila de la tabla `precios`
    for precio_id, med_id, med_nombre, fabricante_id, fabricante, precio, fecha, imagen in datos_propios:
        key = precio_id
        base[key] = {
            "precio_id": precio_id,
            "medicamento_id": med_id,
            "nombre": med_nombre if med_nombre else f"(medicamento #{med_id} no encontrado)",
            "fabricante_id": fabricante_id,
            "fabricante": fabricante if fabricante else f"(fabricante #{fabricante_id} no encontrado)",
            "propio": precio,
            "fecha": fecha,
            "imagen": imagen,
            "Locatel": None,
            "Farmatodo": None,
            "Cruz Verde": None,
            "La Rebaja": None,
        }

    # ✅ Traer los precios de competencia
    query_comp = """
        SELECT pc.medicamento_id, pc.fabricante_id, t.nombre as competidor, pc.precio
        FROM precios_competencia pc
        LEFT JOIN terceros t ON pc.competidor_id = t.id;
    """
    cur.execute(query_comp)
    comp_rows = cur.fetchall()
    # Asignar precios de competencia a todas las filas de `base` que coincidan en medicamento+fabricante
    for mid, fab_id, competidor, precio in comp_rows:
        for k, v in base.items():
            if v.get('medicamento_id') == mid and v.get('fabricante_id') == fab_id:
                if competidor in v:
                    v[competidor] = precio

    conn.close()
    return list(base.values())

def generar_html(datos):
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(datos)
    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Reporte de Precios</title>
        <style>
            body {{ font-family: Arial, sans-serif; background:#f8f9fa; padding:20px; }}
            h1 {{ text-align:center; color:#333; }}
            table {{ border-collapse: collapse; width:100%; background:white; }}
            th, td {{ border:1px solid #ddd; padding:8px; text-align:center; }}
            th {{ background:#007BFF; color:white; }}
            tr:nth-child(even) {{ background:#f2f2f2; }}
            .fabricante {{ font-size: 0.9em; color:#555; }}
            img {{ width:60px; height:60px; object-fit:cover; border-radius:8px; }}
        </style>
    </head>
    <body>
        <h1>📊 Reporte Comparativo de Precios</h1>
        <p>Generado el: {ahora}</p>
        <p><strong>Total productos en el reporte:</strong> {total}</p>
        <table>
            <tr>
                <th>Medicamento</th>
                <th>Fabricante</th>
                <th>Imagen</th>
                <th>Precio Propio</th>
                <th>Locatel</th>
                <th>Farmatodo</th>
                <th>Cruz Verde</th>
                <th>La Rebaja</th>
                <th>Última Actualización</th>
            </tr>
    """

    for fila in datos:
        html += f"""
        <tr>
            <td>{fila['nombre']}</td>
            <td class="fabricante">{fila['fabricante']}</td>
            <td>{f'<img src="{fila["imagen"]}">' if fila["imagen"] else "-"}</td>
            <td>{formatear_precio(fila['propio'])}</td>
            <td>{formatear_precio(fila['Locatel'])}</td>
            <td>{formatear_precio(fila['Farmatodo'])}</td>
            <td>{formatear_precio(fila['Cruz Verde'])}</td>
            <td>{formatear_precio(fila['La Rebaja'])}</td>
            <td>{fila['fecha']}</td>
        </tr>
        """

    html += """
        </table>
    </body>
    </html>
    """
    return html

def guardar_html(contenido):
    nombre = f"reporte_precios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    ruta = os.path.join(os.getcwd(), nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("Reporte HTML generado:", ruta)
    return ruta

if __name__ == "__main__":
    datos = obtener_datos_precios()
    html = generar_html(datos)
    guardar_html(html)
