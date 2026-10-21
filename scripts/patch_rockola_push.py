import os

p = os.path.join(os.path.dirname(__file__), '..', 'app', 'blueprints', 'rockola.py')
with open(p, 'rb') as f:
    c = f.read()

target = b'        conn.commit()\r\n        return jsonify(ok=True, id=nuevo[\'id\'])'
repl = b'''        conn.commit()

        try:
            from .crm import _despachar_push_asincrono
            row_rem = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (remitente,)).fetchone()
            nom_rem = row_rem['nombre'] if row_rem and row_rem['nombre'] else 'Alguien'
            _despachar_push_asincrono(
                destinatario,
                f"\xf0\x9f\x8e\xb5 {nom_rem} en TUC TUC",
                f"Te ha compartido: {payload['nombre']}",
                token=conv['token'],
                url=f"/chat2?open_token={conv['token']}"
            )
        except Exception:
            pass

        return jsonify(ok=True, id=nuevo['id'])'''

if target in c:
    c = c.replace(target, repl, 1)
    with open(p, 'wb') as f:
        f.write(c)
    print('rockola.py patched successfully!')
else:
    print('target not found')
