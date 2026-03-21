"""
telegram_contactos.py — Convierte el export HTML de Telegram a JSON para TUC TUC
Uso: py telegram_contactos.py
Genera: contactos_telegram.json (en el mismo directorio)
"""
import json
import re
from pathlib import Path

HTML = Path(r"C:\Users\RAFAEL OLIVARES\Downloads\Telegram Desktop\DataExport_2026-03-16\lists\contacts.html")
SALIDA = Path(r"C:\Users\RAFAEL OLIVARES\Downloads\contactos_telegram.json")

texto = HTML.read_text(encoding='utf-8')

# Extraer bloques de cada contacto
bloques = re.findall(
    r'<div class="name bold">(.*?)</div>.*?<div class="details_entry details">(.*?)</div>',
    texto, re.DOTALL
)

contactos = []
for nombre, telefono in bloques:
    nombre   = nombre.strip()
    telefono = re.sub(r'\s+', '', telefono.strip())
    # Saltar "Deleted Account" sin teléfono útil
    if nombre == 'Deleted Account' and not telefono:
        continue
    contactos.append({"first_name": nombre, "last_name": "", "phone_number": telefono})

resultado = {"contacts": {"list": contactos}}
SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"OK: {len(contactos)} contactos exportados -> {SALIDA}")
