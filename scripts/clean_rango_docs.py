with open('app/blueprints/tiendas.py', 'r', encoding='utf-8') as f:
    code = f.read()

target = """        rango_docs = ''
        if docs_list:
            if len(docs_list) == 1:
                rango_docs = f"Factura {docs_list[0]}"
            else:
                rango_docs = f"De la {docs_list[0]} a la {docs_list[-1]}" """

target_clean = """        rango_docs = ''
        clean_docs = [str(d).replace('FACTURA_DE_VENTA-', '#').replace('FACTURA-', '#') for d in docs_list]
        if clean_docs:
            if len(clean_docs) == 1:
                rango_docs = f"Factura {clean_docs[0]}"
            else:
                rango_docs = f"De la {clean_docs[0]} a la {clean_docs[-1]}" """

# Let's check target
idx = code.find("rango_docs = ''")
print(repr(code[idx:idx+250]))

code = code.replace(
"""        rango_docs = ''
        if docs_list:
            if len(docs_list) == 1:
                rango_docs = f"Factura {docs_list[0]}"
            else:
                rango_docs = f"De la {docs_list[0]} a la {docs_list[-1]}" """.strip(),
"""        rango_docs = ''
        clean_docs = [str(d).replace('FACTURA_DE_VENTA-', '#').replace('FACTURA-', '#') for d in docs_list]
        if clean_docs:
            if len(clean_docs) == 1:
                rango_docs = f"Factura {clean_docs[0]}"
            else:
                rango_docs = f"De la {clean_docs[0]} a la {clean_docs[-1]}" """.strip(),
1
)

with open('app/blueprints/tiendas.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated clean_docs in tiendas.py")
