import requests
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# URL de tu app en Render
BASE_URL = "https://tuc-tuc.onrender.com"

# Tu número de teléfono
tu_telefono = "3175718658"

print(f"\nEnviando codigo de verificacion a: {tu_telefono}")
print("Esto puede tardar unos segundos...")
print()

try:
    # Llamar al endpoint de enviar código
    response = requests.post(
        f"{BASE_URL}/api/enviar-codigo-whatsapp",
        json={"telefono": tu_telefono},
        timeout=30
    )

    data = response.json()

    if response.status_code == 200 and data.get('ok'):
        print("✅ EXITO: Codigo enviado por WhatsApp")
        print(f"   Mensaje: {data.get('mensaje')}")
        print()
        print("Revisa tu WhatsApp y deberas recibir un mensaje con el codigo de 6 digitos")
    else:
        print(f"❌ ERROR: {data.get('error', 'Error desconocido')}")
        print(f"   Status: {response.status_code}")

except requests.exceptions.Timeout:
    print("❌ ERROR: Timeout - El servidor tardo mucho en responder")
    print("   Esto puede pasar si el servidor esta 'dormido' en Render")
    print("   Intenta de nuevo en 1 minuto")

except Exception as e:
    print(f"❌ ERROR inesperado: {e}")
    import traceback
    traceback.print_exc()
