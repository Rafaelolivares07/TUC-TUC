with open('app/blueprints/compras.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """        tel_clean = "".join(filter(str.isdigit, telefono_prov))
        if tel_clean and len(tel_clean) == 10 and not tel_clean.startswith('57'):
            tel_clean = '57' + tel_clean
        wa_url = f"https://wa.me/{tel_clean}?text={urllib.parse.quote(texto_wa)}" if tel_clean else \"\""""

replacement = """        tel_clean = "".join(filter(str.isdigit, telefono_prov))
        if tel_clean and len(tel_clean) == 10 and not tel_clean.startswith('57'):
            tel_clean = '57' + tel_clean

        if tel_clean:
            wa_url = f"https://api.whatsapp.com/send?phone={tel_clean}&text={urllib.parse.quote(texto_wa)}"
        else:
            wa_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wa)}" """

assert target in text, "target not found in compras.py"
text = text.replace(target, replacement, 1)

with open('app/blueprints/compras.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("compras.py patched wa_url.")
