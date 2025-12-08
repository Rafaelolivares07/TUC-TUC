from flask import Flask, jsonify
import sqlite3

DB_PATH = "medicamentos.db"

app = Flask(__name__)

def obtener_grupos(conn):
    q = "SELECT DISTINCT componente_activo_id FROM MEDICAMENTOS WHERE componente_activo_id IS NOT NULL"
    return [r[0] for r in conn.execute(q).fetchall()]

def obtener_meds(conn, comp):
    q = "SELECT id FROM MEDICAMENTOS WHERE componente_activo_id = ?"
    return [r[0] for r in conn.execute(q, (comp,)).fetchall()]

def obtener_sintomas(conn, med_id):
    q = "SELECT sintoma_id FROM MEDICAMENTO_SINTOMA WHERE medicamento_id = ?"
    return {r[0] for r in conn.execute(q, (med_id,)).fetchall()}

@app.route("/sincronizar", methods=["POST"])
def sincronizar():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    total_insertados = 0

    for comp_id in obtener_grupos(conn):
        meds = obtener_meds(conn, comp_id)
        todos_sintomas = set().union(*[obtener_sintomas(conn, m) for m in meds])

        for med in meds:
            actuales = obtener_sintomas(conn, med)
            faltantes = todos_sintomas - actuales
            for s_id in faltantes:
                cursor.execute("INSERT INTO MEDICAMENTO_SINTOMA (medicamento_id, sintoma_id) VALUES (?, ?)", (med, s_id))
                total_insertados += 1

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "mensaje": f"✅ Sincronización completada. {total_insertados} relaciones añadidas."
    })

if __name__ == "__main__":
    app.run(port=5001, debug=False)
