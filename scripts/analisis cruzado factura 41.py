#!/usr/bin/env python3
from collections import defaultdict

kardex = [
    {'nombre': 'BOLSA PAPEL KRAF UNIDAD', 'padre_id': 249, 'cantidad': 20, 'total': 1775.1943},
    {'nombre': 'BOLSA PAPEL KRAF UNIDAD', 'padre_id': 251, 'cantidad': 20, 'total': 1775.1943},
    {'nombre': 'CARNE DE CERDO PREPARADA GRS', 'padre_id': 249, 'cantidad': 1000, 'total': 25166.271},
    {'nombre': 'CEBOLLA BLANCA CARAMELIZADA GRS', 'padre_id': 249, 'cantidad': 700, 'total': 5431.7491},
    {'nombre': 'HOJA PAPEL PARAFINADO 30X30 CMS UNIDAD', 'padre_id': 249, 'cantidad': 20, 'total': 3744.616},
    {'nombre': 'HOJA PAPEL PARAFINADO 30X30 CMS UNIDAD', 'padre_id': 251, 'cantidad': 20, 'total': 3744.616},
    {'nombre': 'LECHUGA X GRS', 'padre_id': 251, 'cantidad': 600, 'total': 2132.0868},
    {'nombre': 'LECHUGA X GRS', 'padre_id': 249, 'cantidad': 600, 'total': 2132.0868},
    {'nombre': 'MAYONESA X GRS', 'padre_id': 251, 'cantidad': 700, 'total': 11892.2634},
    {'nombre': 'MAYONESA X GRS', 'padre_id': 249, 'cantidad': 700, 'total': 11892.2634},
    {'nombre': 'PAN TIPO ARABE PERMAN UNID', 'padre_id': 251, 'cantidad': 20, 'total': 24818.5096},
    {'nombre': 'PAN TIPO ARABE PERMAN UNID', 'padre_id': 249, 'cantidad': 20, 'total': 24818.5096},
    {'nombre': 'PECHUGA POLLO PREPARADO GRS', 'padre_id': 251, 'cantidad': 1000, 'total': 29233.9037},
    {'nombre': 'QUESO MOZZARELLA GRS', 'padre_id': 249, 'cantidad': 240, 'total': 5815.1911},
    {'nombre': 'QUESO MOZZARELLA GRS', 'padre_id': 251, 'cantidad': 240, 'total': 5815.1911},
    {'nombre': 'STICKER PITT UNID', 'padre_id': 251, 'cantidad': 20, 'total': 6125.0},
    {'nombre': 'STICKER PITT UNID', 'padre_id': 249, 'cantidad': 20, 'total': 6125.0},
    {'nombre': 'TOMATE GRS', 'padre_id': 251, 'cantidad': 720, 'total': 4092.9908},
    {'nombre': 'TOMATE GRS', 'padre_id': 249, 'cantidad': 600, 'total': 3410.8257},
]

baja_inv = [
    {'nombre': 'BOLSA PAPEL KRAF UNIDAD', 'monto': 1774.60},
    {'nombre': 'BOLSA PAPEL KRAF UNIDAD', 'monto': 1774.60},
    {'nombre': 'CARNE DE CERDO PREPARADA GRS', 'monto': 24706.45},
    {'nombre': 'CEBOLLA BLANCA CARAMELIZADA GRS', 'monto': 5537.98},
    {'nombre': 'HOJA PAPEL PARAFINADO 30X30 CMS UNIDAD', 'monto': 3844.39},
    {'nombre': 'HOJA PAPEL PARAFINADO 30X30 CMS UNIDAD', 'monto': 3844.39},
    {'nombre': 'LECHUGA X GRS', 'monto': 2157.11},
    {'nombre': 'LECHUGA X GRS', 'monto': 2157.11},
    {'nombre': 'MAYONESA X GRS', 'monto': 24531.38},
    {'nombre': 'MAYONESA X GRS', 'monto': 24531.38},
    {'nombre': 'PAN TIPO ARABE PERMAN UNID', 'monto': 24811.86},
    {'nombre': 'PAN TIPO ARABE PERMAN UNID', 'monto': 24811.86},
    {'nombre': 'PECHUGA POLLO PREPARADO GRS', 'monto': 28896.58},
    {'nombre': 'QUESO MOZZARELLA GRS', 'monto': 5802.23},
    {'nombre': 'QUESO MOZZARELLA GRS', 'monto': 5802.23},
    {'nombre': 'STICKER PITT UNID', 'monto': 6125.00},
    {'nombre': 'STICKER PITT UNID', 'monto': 6125.00},
    {'nombre': 'TOMATE GRS', 'monto': 4163.17},
    {'nombre': 'TOMATE GRS', 'monto': 3469.31},
]

k_por_nombre = defaultdict(list)
for k in kardex:
    k_por_nombre[k['nombre']].append(k)

c_por_nombre = defaultdict(list)
for c in baja_inv:
    c_por_nombre[c['nombre']].append(c)

header = f"{'Componente':<42} {'K#':<4} {'K Total':>14} {'C#':<4} {'C Total':>14} {'Dif':>12} {'Match':>6}"
print(header)
print("-" * len(header))

grand_k = 0
grand_c = 0
for nombre in sorted(k_por_nombre.keys()):
    k_regs = k_por_nombre[nombre]
    c_regs = c_por_nombre.get(nombre, [])
    k_total = sum(r['total'] for r in k_regs)
    c_total = sum(r['monto'] for r in c_regs)
    dif = k_total - c_total
    n_match = "OK" if len(k_regs) == len(c_regs) else f"{len(k_regs)}vs{len(c_regs)}"
    flag = " ***" if abs(dif) > 1 or len(k_regs) != len(c_regs) else ""
    print(f"{nombre:<42} {len(k_regs):<4} ${k_total:>12,.2f} {len(c_regs):<4} ${c_total:>12,.2f} ${dif:>10,.2f} {n_match}{flag}")
    grand_k += k_total
    grand_c += c_total

print("-" * len(header))
print(f"{'TOTAL':<42} {len(kardex):<4} ${grand_k:>12,.2f} {len(baja_inv):<4} ${grand_c:>12,.2f} ${grand_k - grand_c:>10,.2f}")
print()
print("Kardex: producto_id y producto_padre_id POBLADOS")
print("Contab: producto_id = NULL, producto_padre_id = NULL")
