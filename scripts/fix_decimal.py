with open('app/blueprints/tiendas.py', 'r', encoding='utf-8') as f:
    code = f.read()

target = "prods_dict[nom]['total'] += (cant * (it['precio_unitario'] or 0))"
replacement = "prods_dict[nom]['total'] += float(cant * float(it['precio_unitario'] or 0))"

assert target in code, "Target 1 not found"
code = code.replace(target, replacement, 1)

target2 = "vd = dict(v)"
replacement2 = "vd = dict(v)\n            vd['total'] = float(vd.get('total') or 0)"
assert target2 in code, "Target 2 not found"
code = code.replace(target2, replacement2, 1)

with open('app/blueprints/tiendas.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed decimal in tiendas.py")
