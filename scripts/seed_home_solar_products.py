import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env_file():
    env_path = ROOT / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

from app import create_app  # noqa: E402
from app.db import get_db_connection  # noqa: E402


SLUG = 'home-solar-panel'


CATEGORIAS_PUBLICAS = {
    'DISENO Y COTIZACION': '01. Empieza aqui',
    'KITS SOLARES': '02. Kits solares',
    'INSTALACION': '03. Instalacion',
    'PANEL SOLAR': '04. Paneles solares',
    'INVERSOR': '05. Inversores solares',
    'BATERIA': '06. Baterias solares',
    'BMS': '07. Monitoreo y control',
    'CT': '07. Monitoreo y control',
    'DTU': '07. Monitoreo y control',
    'METER': '07. Monitoreo y control',
    'MPPT': '07. Monitoreo y control',
    'WIFI': '07. Monitoreo y control',
    'ACCESORIO': '08. Accesorios y protecciones',
}


def categoria_publica(categoria):
    return CATEGORIAS_PUBLICAS.get(categoria, categoria)


def desc_generica(categoria, nombre, marca):
    marca_txt = f" {marca}" if marca else ""
    if categoria == 'PANEL SOLAR':
        return f"Panel solar{marca_txt} para sistemas residenciales, fincas y pequenos negocios. Lo seleccionamos segun espacio, consumo y objetivo del proyecto."
    if categoria == 'INVERSOR':
        return f"Inversor solar{marca_txt} para convertir y gestionar la energia del sistema. La referencia final depende del consumo, tension y tipo de respaldo requerido."
    if categoria == 'BATERIA':
        return f"Bateria solar{marca_txt} para respaldo de energia. Se recomienda segun autonomia esperada, consumo critico y tipo de inversor."
    if categoria == 'ACCESORIO':
        return f"Accesorio tecnico{marca_txt} para montaje, conexion o proteccion del sistema solar. Se incluye cuando el diseno lo requiere."
    if categoria in ('METER', 'CT', 'DTU', 'WIFI', 'BMS', 'MPPT'):
        return f"Componente de comunicacion, medicion o control{marca_txt} para monitoreo y operacion del sistema solar."
    return f"Equipo solar{marca_txt} para proyectos de energia solar. Te ayudamos a escoger la opcion correcta."


SERVICIOS = [
    {
        'marca': 'HOME SOLAR PANEL',
        'categoria': categoria_publica('DISENO Y COTIZACION'),
        'nombre': 'Cotizacion solar inicial',
        'precio': 120000,
        'costo': 0,
        'descripcion': 'Revisamos tu consumo, ubicacion y necesidad para estimar una solucion solar inicial sin regalar el diseno tecnico completo.',
    },
    {
        'marca': 'HOME SOLAR PANEL',
        'categoria': categoria_publica('DISENO Y COTIZACION'),
        'nombre': 'Diseno tecnico solar completo',
        'precio': 250000,
        'costo': 0,
        'descripcion': 'Calculo detallado de paneles, inversor, baterias si aplica, protecciones, equipos recomendados y presupuesto tecnico. Este valor puede descontarse si compras el sistema con nosotros.',
    },
    {
        'marca': 'HOME SOLAR PANEL',
        'categoria': categoria_publica('KITS SOLARES'),
        'nombre': 'Kit solar a la medida',
        'precio': 0,
        'costo': 0,
        'descripcion': 'Sistema solar configurado segun tu consumo, ubicacion y objetivo: ahorro, respaldo o independencia parcial. No compres paneles a ciegas: lo escogemos por ti.',
    },
    {
        'marca': 'HOME SOLAR PANEL',
        'categoria': categoria_publica('INSTALACION'),
        'nombre': 'Instalacion de sistema solar',
        'precio': 0,
        'costo': 0,
        'descripcion': 'Instalacion profesional de paneles, inversor, protecciones y puesta en marcha del sistema solar.',
    },
]


EQUIPOS = [
    ('HOYMILES', 'ACCESORIO', 'DIS-Tool AC Trunk Port Disconnect Tool', 23000, 12588),
    ('HOYMILES', 'ACCESORIO', 'AC-END - AC END CAP', 23000, 12687),
    ('HOYMILES', 'ACCESORIO', 'AC TRUNK END CAP', 31000, 16842),
    ('HOYMILES', 'ACCESORIO', 'Unlock-Tool AC Trunk Connector Unlock Tool', 32000, 17777),
    ('HOYMILES', 'ACCESORIO', 'DC-CABLE-1M DC Extension Cable 1m', 51000, 28409),
    ('HOYMILES', 'ACCESORIO', 'AC-CONN - AC CONNECTOR', 59000, 32862),
    ('HOYMILES', 'ACCESORIO', 'AC Trunk Connector', 76000, 42538),
    ('HOYMILES', 'ACCESORIO', 'AC Trunk Cable_1T_1L_10AWG - 2m', 157000, 87549),
    ('MUST', 'ACCESORIO', 'Parallel kits for PV18-3048LHM', 120000, 67005),
    ('CS BATTERY', 'BATERIA', 'HTB12-100 bateria gel ciclo profundo 12V 100Ah', 981000, 549125),
    ('CS BATTERY', 'BATERIA', 'HTB12-150 bateria gel ciclo profundo 12V 150Ah', 1540000, 862568),
    ('CS BATTERY', 'BATERIA', 'HTB12-200 bateria gel ciclo profundo 12V 200Ah', 1979000, 1108147),
    ('CS BATTERY', 'BATERIA', 'HTB12-250 bateria gel ciclo profundo 12V 250Ah', 2362000, 1323096),
    ('DEYE', 'BATERIA', 'High voltage battery cluster control box + battery module base', 5046000, 2826625),
    ('DEYE', 'BATERIA', '4.09 kWh battery module High Voltage', 7486000, 4193753),
    ('MUST', 'BATERIA', 'LP15-12100 LiFePO4 lithium battery 100Ah 12.8V Bluetooth', 1683000, 942857),
    ('MUST', 'BATERIA', 'LP15-12200 LiFePO4 lithium battery 200Ah 12.8V Bluetooth', 2933000, 1642857),
    ('MUST', 'BATERIA', 'LP15-24125 LiFePO4 lithium battery 125Ah 25.6V Bluetooth', 3647000, 2042857),
    ('MUST', 'BATERIA', 'LP16-48100 LiFePO4 lithium battery 100Ah 51.2V WiFi BMS', 7070000, 3960714),
    ('MUST', 'BATERIA', 'LiFePO4 lithium battery 200Ah 51.2V WiFi BMS', 12113000, 6785714),
    ('SOLUNA', 'BATERIA', 'EOS-5K bateria SOLUNA', 8987000, 5034649),
    ('SOLUNA', 'BATERIA', 'EOS-5K BATTERY MODULE 51.2V 100Ah + WIFI + BRAKET', 9649000, 5405405),
    ('MUST', 'BMS', 'MUST-BMS-COMM BMS Communication kit para PV3500 TLV', 199000, 111052),
    ('HOYMILES', 'CT', 'CT-300A', 208000, 116161),
    ('HOYMILES', 'DTU', 'DTU-Lite-S DTU-Lite S WiFi', 877000, 491250),
    ('HOYMILES', 'DTU', 'DTU-W-100', 887000, 496815),
    ('HOYMILES', 'DTU', 'DTU-PRO-MI-1500 DTU-PRO WiFi para MI-1500', 1602000, 897473),
    ('HOYMILES', 'DTU', 'DTU-PRO-C DTU-PRO S WiFi', 1619000, 906593),
    ('AFORE', 'INVERSOR', 'Inversor on-grid 6.0kW monofasico 220V WiFi', 3533000, 2354903),
    ('AFORE', 'INVERSOR', 'Inversor on-grid 10.0kW trifasico 220V WiFi', 5125000, 3416063),
    ('AFORE', 'INVERSOR', 'Inversor on-grid 60.0kW trifasico 220V AFCI', 23171000, 15446689),
    ('DEYE', 'INVERSOR', 'SUN-10K-G05-LV inversor on-grid trifasico 10kW', 5915000, 3942760),
    ('DEYE', 'INVERSOR', 'SUN-15K-G05-LV inversor string trifasico 15kW', 6965000, 4642720),
    ('DEYE', 'INVERSOR', 'SUN-8K-SG01LP1-US inversor hibrido split phase 8kW', 11394000, 7595850),
    ('DEYE', 'INVERSOR', 'SUN-12K-SG02LP2-US-AM3 inversor hibrido split phase 12kW', 14353000, 9568636),
    ('DEYE', 'INVERSOR', 'SUN-30K-SG01HP3-US-BM4 inversor hibrido trifasico 30kW', 33551000, 22366689),
    ('HOYMILES', 'INVERSOR', 'HMS-800-2T-LV micro inversor HMS-800', 963000, 641784),
    ('HOYMILES', 'INVERSOR', 'MI-1500 micro inversor 1500W', 968000, 645250),
    ('HOYMILES', 'INVERSOR', 'Micro inversor HMS-1800', 1412000, 941176),
    ('HOYMILES', 'INVERSOR', 'HMS-2000 micro inversor', 1603000, 1068478),
    ('LIVOLTEK', 'INVERSOR', 'GT1-3K3S1 inversor on-grid 3.3kW 220Vac WiFi', 2344000, 1562500),
    ('LIVOLTEK', 'INVERSOR', 'Inversor on-grid 6.0kW 220Vac WiFi', 3563000, 2375000),
    ('LIVOLTEK', 'INVERSOR', 'GT1-10KT2 inversor on-grid trifasico 10kW WiFi', 5199000, 3465841),
    ('LIVOLTEK', 'INVERSOR', 'GT3-20KL-T inversor on-grid trifasico 20kW', 10862000, 7241232),
    ('LIVOLTEK', 'INVERSOR', 'GT3-25KL-T inversor on-grid trifasico 25kW', 13361000, 8906722),
    ('LIVOLTEK', 'INVERSOR', 'GT3-30KL-Q inversor on-grid trifasico 30kW', 13703000, 9135105),
    ('MUST', 'INVERSOR', 'PV18-1012-V inversor off-grid 1000W DC12V', 1243000, 828005),
    ('MUST', 'INVERSOR', 'PV30-1524 LVM inversor solar 1.5kW DC24V', 1725000, 1150000),
    ('MUST', 'INVERSOR', 'PV18-2024 LV inversor off-grid 2000W DC24V', 1776000, 1183750),
    ('MUST', 'INVERSOR', 'Inversor cargador baja frecuencia 3kW AC120V MPPT 80A', 2452000, 1634343),
    ('MUST', 'INVERSOR', 'Inversor off-grid 3000W DC24V MPPT USB', 2504000, 1668750),
    ('MUST', 'INVERSOR', 'PV33-6048 TLV inversor split phase off-grid 6kW 48V', 3337000, 2224439),
    ('MUST', 'INVERSOR', 'PV36-8048 TLV inversor split phase off-grid 8kW 48V', 6677000, 4451250),
    ('MUST', 'INVERSOR', 'PV36-12048 TLV inversor split phase off-grid 12kW 48V', 8555000, 5702924),
    ('MUST', 'INVERSOR', 'Inversor solar off-grid 12kW PV250V MPPT 200A', 10115000, 6743294),
    ('SOLIS', 'INVERSOR', 'Solis-3P6K-4G-LV on-grid 6kW bajo voltaje 220V trifasico', 3487000, 2324435),
    ('DEYE', 'METER', 'SDM630MCT-E11 meter DEYE', 1053000, 589792),
    ('HOYMILES', 'METER', 'DTSU 666 SP 100A split phase 120/240V CT 100A/40mA', 1162000, 650820),
    ('HOYMILES', 'METER', 'DTSU 666 SP 250A split phase 120/240V CT 250A/50mA', 1226000, 686643),
    ('HOYMILES', 'METER', 'DTSU 666 TP 250A three phase 230/400V CT 250A/50mA', 1512000, 847058),
    ('LIVOLTEK', 'METER', 'LHE34DRR12 Smart Meter 4 cables hasta 120A incluye CTs', 985000, 656257),
    ('SOLIS', 'METER', 'DTSD1352 Solis-Meter trifasico ACREL', 1098000, 614970),
    ('MUST', 'MPPT', 'PC18-8025F controlador solar MPPT 80A fan cooling', 848000, 564763),
    ('MUST', 'MPPT', 'PC18-10015F controlador solar MPPT 100A fan cooling', 901000, 600591),
    ('LUXEN', 'PANEL SOLAR', 'LNSF-330P panel solar policristalino 330W RETIE', 387000, 257653),
    ('LUXEN', 'PANEL SOLAR', 'LNVU-550M panel solar mono half-cut 550W RETIE', 472000, 314513),
    ('LUXEN', 'PANEL SOLAR', '450W mono half-cut solar panel RETIE', 494000, 329049),
    ('LUXEN', 'PANEL SOLAR', 'LNCT-585ND panel bifacial N-type 585W', 504000, 335446),
    ('LUXEN', 'PANEL SOLAR', 'LNCT-630ND panel bifacial N-type 630W', 537000, 357446),
    ('MUST', 'WIFI', 'MUST-WIFI-PLUG New version WiFi Plug', 226000, 126177),
    ('SOLIS', 'WIFI', 'S2-WL-ST Solis S2 LAN & WiFi Stick', 352000, 197029),
]


def _productos():
    productos = list(SERVICIOS)
    for marca, categoria, nombre, precio, costo in EQUIPOS:
        productos.append({
            'marca': marca,
            'categoria': categoria_publica(categoria),
            'nombre': f"{marca} - {nombre}",
            'precio': precio,
            'costo': costo,
            'descripcion': desc_generica(categoria, nombre, marca),
        })
    return productos


def seed():
    create_app()
    conn = get_db_connection()
    try:
        tienda = conn.execute(
            "SELECT id, tercero_id, nombre FROM tiendas WHERE slug = %s AND activo = TRUE",
            (SLUG,),
        ).fetchone()
        if not tienda or not tienda['tercero_id']:
            raise RuntimeError(f"No existe tienda activa con slug {SLUG} o no tiene tercero_id")

        negocio_id = tienda['tercero_id']
        creados = 0
        actualizados = 0
        for orden, p in enumerate(_productos(), start=1):
            existente = conn.execute(
                "SELECT id FROM productos WHERE negocio_id = %s AND LOWER(nombre) = LOWER(%s) LIMIT 1",
                (negocio_id, p['nombre']),
            ).fetchone()
            params = (
                p['categoria'], p['precio'], p['costo'], p['descripcion'], orden,
                p['marca'], 0, True,
            )
            if existente:
                conn.execute(
                    """
                    UPDATE productos
                    SET categoria=%s, precio=%s, costo=%s, descripcion=%s,
                        orden=%s, codigo_barra=%s, iva_pct=%s, disponible=%s
                    WHERE id=%s
                    """,
                    params + (existente['id'],),
                )
                actualizados += 1
            else:
                conn.execute(
                    """
                    INSERT INTO productos
                        (negocio_id, nombre, categoria, precio, costo, descripcion,
                         orden, codigo_barra, iva_pct, disponible)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        negocio_id, p['nombre'], p['categoria'], p['precio'], p['costo'],
                        p['descripcion'], orden, p['marca'], 0, True,
                    ),
                )
                creados += 1
        conn.commit()
        print(f"Tienda: {tienda['nombre']} ({SLUG})")
        print(f"Productos creados: {creados}")
        print(f"Productos actualizados: {actualizados}")
        print(f"Total catalogo: {creados + actualizados}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    seed()
