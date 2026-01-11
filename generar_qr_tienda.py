#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Genera código QR para la tienda TUC-TUC
"""

import qrcode

# URL de la tienda
url = "https://tuc-tuc.onrender.com/tienda"

# Crear objeto QR
qr = qrcode.QRCode(
    version=1,  # Tamaño del QR (1 es el más pequeño)
    error_correction=qrcode.constants.ERROR_CORRECT_H,  # Alta corrección de errores
    box_size=10,  # Tamaño de cada cuadro en píxeles
    border=4,  # Borde alrededor del QR
)

# Agregar datos
qr.add_data(url)
qr.make(fit=True)

# Crear imagen
img = qr.make_image(fill_color="black", back_color="white")

# Guardar imagen
img.save("qr_tienda_tuc_tuc.png")

print(f"Codigo QR generado exitosamente!")
print(f"URL: {url}")
print(f"Archivo: qr_tienda_tuc_tuc.png")
print(f"Tamaño: {img.size[0]}x{img.size[1]} pixeles")
