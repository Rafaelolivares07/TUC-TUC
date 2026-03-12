"""
test_ble_scan.py
Escanea dispositivos BLE cercanos y busca el MOES BAT-80A.
Requiere: pip install bleak
"""
import asyncio
from bleak import BleakScanner

async def scan():
    print("Escaneando dispositivos BLE por 15 segundos...")
    print("(asegúrate que el MOES ATS esté encendido y cerca)\n")

    devices = await BleakScanner.discover(timeout=15.0)

    print(f"Encontrados {len(devices)} dispositivos:\n")
    for d in sorted(devices, key=lambda x: x.rssi, reverse=True):
        name = d.name or "(sin nombre)"
        print(f"  {d.address}  RSSI={d.rssi:>4}dBm  {name}")
        # Buscar candidatos del MOES/Tuya
        if any(k in (d.name or '').lower() for k in ['moes', 'tuya', 'bat', 'ats', 'transfer', 'nvat']):
            print(f"    *** POSIBLE CANDIDATO ***")

asyncio.run(scan())
