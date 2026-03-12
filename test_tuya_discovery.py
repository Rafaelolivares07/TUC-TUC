"""
test_tuya_discovery.py v4
Diagnóstico del switch de transferencia solar.
"""
import tinytuya, json

c = tinytuya.Cloud(
    apiRegion='us',
    apiKey='9p9nr8s3nv8sdth78v5u',
    apiSecret='644b3e3813c640bfb3aa3efe95437683',
    apiDeviceID='ebe4f458f0427bc8a08lgy'
)

SWITCH_ID = 'ebbb85zu5m9f4sic'

print("=" * 60)
print(f"SWITCH DE TRANSFERENCIA SOLAR: {SWITCH_ID}")
print("=" * 60)

# 1. Info básica del dispositivo
print("\n--- INFO DISPOSITIVO ---")
info = c.cloudrequest(f'/v1.0/iot-03/devices/{SWITCH_ID}')
print(json.dumps(info, indent=2))

# 2. Estado actual (valores en tiempo real)
print("\n--- ESTADO ACTUAL ---")
status = c.getstatus(SWITCH_ID)
print(json.dumps(status, indent=2))

# 3. Especificaciones (todos los DPs posibles)
print("\n--- ESPECIFICACIONES (DPs disponibles) ---")
spec = c.cloudrequest(f'/v1.0/iot-03/devices/{SWITCH_ID}/specification')
print(json.dumps(spec, indent=2))

# 4. Logs recientes del dispositivo
print("\n--- LOGS RECIENTES ---")
logs = c.cloudrequest(f'/v1.0/iot-03/devices/{SWITCH_ID}/logs?event_types=1,2,3&size=20')
print(json.dumps(logs, indent=2))
