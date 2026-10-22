path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\orden_compra_publica.html'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# Replace any lingering None in Jinja tests
c = c.replace('is not None', 'is not none')
c = c.replace('is None', 'is none')

# Guard format calls against None
c = c.replace('"{:,.0f}".format(it.precio_unitario)', '"{:,.0f}".format((it.precio_unitario or 0)|float)')
c = c.replace('"{:,.0f}".format(it.total_confirmado if it.total_confirmado is not none else it.total_solicitado)', '"{:,.0f}".format(((it.total_confirmado if it.total_confirmado is not none else it.total_solicitado) or 0)|float)')
c = c.replace('"{:,.0f}".format(orden.total_confirmado if orden.total_confirmado is not none else orden.total_estimado)', '"{:,.0f}".format(((orden.total_confirmado if orden.total_confirmado is not none else orden.total_estimado) or 0)|float)')

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated successfully')
