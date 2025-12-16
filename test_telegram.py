import requests

# Token y Chat ID
TOKEN = "8486881295:AAFjs-SU74er_shs4KnQYImMtyU5OTXycng"
CHAT_ID = "6055213826"

# Mensaje de prueba
mensaje = """PRUEBA DE NOTIFICACION

Nuevo Pedido #123

Cliente: Rafael Olivares
Telefono: 573175718658
Direccion: Calle 10 #5-20

Productos:
- Acetaminofen x2 = $10,000
- Ibuprofeno x1 = $8,000

Subtotal: $18,000
Domicilio: $5,000
TOTAL: $23,000

Metodo de pago: EFECTIVO

Ver ubicacion:
https://www.google.com/maps?q=4.7110,-74.0721

Tiempo estimado: 30 minutos"""

print("Enviando mensaje de prueba a Telegram...")

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {
    'chat_id': CHAT_ID,
    'text': mensaje,
    'parse_mode': 'HTML'
}

response = requests.post(url, json=data, timeout=10)

if response.status_code == 200:
    print("[OK] Mensaje enviado correctamente!")
    print(f"Response: {response.json()}")
else:
    print(f"[ERROR] No se pudo enviar: {response.status_code}")
    print(f"Response: {response.text}")
