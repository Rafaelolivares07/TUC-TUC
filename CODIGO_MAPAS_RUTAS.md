# Código para Integrar Mapas y Rutas en TucTuc

Este documento contiene el código listo para copiar y adaptar a tu app Flask para la funcionalidad de servicios de transporte.

## 📦 Librerías necesarias

### HTML (agregar en el `<head>` del template)

```html
<!-- Leaflet CSS -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

<!-- Leaflet Routing Machine CSS -->
<link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />

<!-- Leaflet JavaScript -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<!-- Leaflet Routing Machine JavaScript -->
<script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
```

---

## 🗺️ 1. Mapa Básico con OpenStreetMap

### HTML
```html
<div id="map" style="width: 100%; height: 500px;"></div>
```

### JavaScript
```javascript
// Inicializar mapa centrado en Cali, Colombia
const map = L.map('map').setView([3.4516, -76.5320], 13);

// Agregar tiles de OpenStreetMap (GRATIS)
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19
}).addTo(map);

// Agregar marcador
const marker = L.marker([3.4516, -76.5320]).addTo(map);
marker.bindPopup("<b>Tu ubicación</b>").openPopup();
```

---

## 🛣️ 2. Calcular Ruta entre Dos Puntos

### JavaScript con Leaflet Routing Machine
```javascript
// Definir origen y destino
const origen = L.latLng(3.4516, -76.5320);  // Ejemplo: Centro de Cali
const destino = L.latLng(3.3950, -76.5197); // Ejemplo: Sur de Cali

// Crear control de rutas
const routeControl = L.Routing.control({
    waypoints: [origen, destino],
    routeWhileDragging: true,

    // Usar OSRM (Open Source Routing Machine) - GRATIS
    router: L.Routing.osrmv1({
        serviceUrl: 'https://router.project-osrm.org/route/v1'
    }),

    // Personalizar UI
    lineOptions: {
        styles: [{color: '#6FA1EC', weight: 6}]
    },

    createMarker: function(i, waypoint, n) {
        const marker = L.marker(waypoint.latLng, {
            draggable: true
        });

        if (i === 0) {
            marker.bindPopup("Origen");
        } else if (i === n - 1) {
            marker.bindPopup("Destino");
        }

        return marker;
    }
}).addTo(map);

// Obtener distancia y tiempo cuando la ruta esté lista
routeControl.on('routesfound', function(e) {
    const routes = e.routes;
    const summary = routes[0].summary;

    // Distancia en metros
    const distanciaMetros = summary.totalDistance;
    const distanciaKm = (distanciaMetros / 1000).toFixed(2);

    // Tiempo en segundos
    const tiempoSegundos = summary.totalTime;
    const tiempoMinutos = Math.round(tiempoSegundos / 60);

    console.log('Distancia:', distanciaKm, 'km');
    console.log('Tiempo estimado:', tiempoMinutos, 'minutos');

    // Calcular tarifa (ejemplo básico)
    const TARIFA_BASE = 5000;  // $5,000 COP
    const TARIFA_POR_KM = 2000; // $2,000 COP por km
    const tarifaEstimada = TARIFA_BASE + (distanciaKm * TARIFA_POR_KM);

    console.log('Tarifa estimada: $', tarifaEstimada.toLocaleString(), 'COP');

    // Mostrar en la UI
    document.getElementById('distancia').textContent = distanciaKm + ' km';
    document.getElementById('tiempo').textContent = tiempoMinutos + ' min';
    document.getElementById('tarifa').textContent = '$' + tarifaEstimada.toLocaleString();
});
```

---

## 📍 3. Obtener Ubicación Actual del Usuario

### JavaScript
```javascript
// Obtener geolocalización del usuario
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(function(position) {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;

        // Centrar mapa en ubicación actual
        map.setView([lat, lng], 15);

        // Agregar marcador
        L.marker([lat, lng]).addTo(map)
            .bindPopup("Tu ubicación actual")
            .openPopup();

        console.log('Ubicación:', lat, lng);
    }, function(error) {
        console.error('Error obteniendo ubicación:', error);
        alert('No se pudo obtener tu ubicación. Verifica permisos del navegador.');
    });
} else {
    alert('Tu navegador no soporta geolocalización');
}
```

---

## 🔍 4. Búsqueda de Direcciones (Geocoding)

Para convertir direcciones de texto a coordenadas, usa **Nominatim** (servicio gratuito de OpenStreetMap):

### JavaScript
```javascript
async function buscarDireccion(direccion) {
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(direccion)}&countrycodes=co`;

    try {
        const response = await fetch(url);
        const data = await response.json();

        if (data.length > 0) {
            const resultado = data[0];
            const lat = parseFloat(resultado.lat);
            const lon = parseFloat(resultado.lon);

            console.log('Coordenadas encontradas:', lat, lon);
            console.log('Dirección completa:', resultado.display_name);

            return { lat, lon, nombre: resultado.display_name };
        } else {
            console.error('No se encontró la dirección');
            return null;
        }
    } catch (error) {
        console.error('Error en búsqueda:', error);
        return null;
    }
}

// Ejemplo de uso
buscarDireccion("Calle 5 Norte 23-45, Cali").then(coords => {
    if (coords) {
        // Agregar marcador en la ubicación encontrada
        L.marker([coords.lat, coords.lon]).addTo(map)
            .bindPopup(coords.nombre);

        // Centrar mapa
        map.setView([coords.lat, coords.lon], 15);
    }
});
```

---

## 💰 5. Cálculo de Tarifas

### Python (Backend Flask)
```python
def calcular_tarifa(distancia_km, tipo_servicio, horas_acompanamiento=None):
    """
    Calcula tarifa basada en distancia y tipo de servicio

    Args:
        distancia_km (float): Distancia en kilómetros
        tipo_servicio (str): 'transporte' o 'acompanamiento'
        horas_acompanamiento (int): Número de horas (solo para acompañamiento)

    Returns:
        dict: {'tarifa': int, 'desglose': dict}
    """

    if tipo_servicio == 'transporte':
        # Tarifa para transporte simple
        TARIFA_BASE = 5000  # Arranque
        TARIFA_POR_KM = 2000  # Por kilómetro

        tarifa = TARIFA_BASE + (distancia_km * TARIFA_POR_KM)

        desglose = {
            'base': TARIFA_BASE,
            'distancia': distancia_km * TARIFA_POR_KM,
            'total': tarifa
        }

    elif tipo_servicio == 'acompanamiento':
        # Tarifa para acompañamiento (incluye espera)
        TARIFA_POR_HORA = 15000  # $15,000 por hora
        TARIFA_MINIMA = 30000  # Mínimo 2 horas

        if not horas_acompanamiento:
            horas_acompanamiento = 2  # Mínimo 2 horas

        tarifa_tiempo = horas_acompanamiento * TARIFA_POR_HORA
        tarifa = max(tarifa_tiempo, TARIFA_MINIMA)

        desglose = {
            'horas': horas_acompanamiento,
            'tarifa_hora': TARIFA_POR_HORA,
            'subtotal': tarifa_tiempo,
            'minimo': TARIFA_MINIMA,
            'total': tarifa
        }

    else:
        raise ValueError(f"Tipo de servicio inválido: {tipo_servicio}")

    return {
        'tarifa': int(tarifa),
        'desglose': desglose
    }


# Ejemplo de endpoint Flask
@app.route('/api/calcular-tarifa', methods=['POST'])
def api_calcular_tarifa():
    data = request.get_json()

    distancia_km = data.get('distancia_km', 0)
    tipo_servicio = data.get('tipo_servicio')
    horas = data.get('horas_acompanamiento')

    try:
        resultado = calcular_tarifa(distancia_km, tipo_servicio, horas)
        return jsonify({'ok': True, **resultado})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
```

---

## 🎯 6. Template HTML Completo para `/servicios`

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Servicios de Transporte - TucTuc</title>

    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

    <!-- Leaflet Routing Machine CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
</head>
<body class="bg-gray-50">

    <div class="max-w-4xl mx-auto p-6">

        <!-- Header -->
        <div class="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Servicios de Transporte</h1>
            <p class="text-gray-600 mt-2">Solicita tu servicio de forma rápida y segura</p>
        </div>

        <!-- Botones de Tipo de Servicio -->
        <div class="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">¿Qué servicio necesitas?</h2>

            <div class="grid grid-cols-2 gap-4">
                <button id="btn-transporte" class="p-6 border-2 border-blue-500 rounded-lg hover:bg-blue-50 transition">
                    <div class="text-4xl mb-2">🚗</div>
                    <div class="font-semibold text-lg">Transporte</div>
                    <div class="text-sm text-gray-600">De un punto a otro</div>
                </button>

                <button id="btn-acompanamiento" class="p-6 border-2 border-gray-300 rounded-lg hover:bg-gray-50 transition">
                    <div class="text-4xl mb-2">🤝</div>
                    <div class="font-semibold text-lg">Acompañamiento</div>
                    <div class="text-sm text-gray-600">Con espera incluida</div>
                </button>
            </div>
        </div>

        <!-- Formulario de Transporte -->
        <div id="form-transporte" class="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">Detalles del viaje</h2>

            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Origen</label>
                    <input type="text" id="input-origen" class="w-full p-3 border rounded-lg"
                           placeholder="Ej: Calle 5 Norte 23-45, Cali">
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Destino</label>
                    <input type="text" id="input-destino" class="w-full p-3 border rounded-lg"
                           placeholder="Ej: Avenida 6 Norte 28-50, Cali">
                </div>

                <button id="btn-calcular-ruta" class="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition">
                    Calcular ruta y tarifa
                </button>
            </div>
        </div>

        <!-- Formulario de Acompañamiento -->
        <div id="form-acompanamiento" class="bg-white rounded-lg shadow-lg p-6 mb-6 hidden">
            <h2 class="text-xl font-semibold mb-4">Servicio de acompañamiento</h2>

            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">¿Cuántas horas necesitas?</label>
                    <input type="number" id="input-horas" class="w-full p-3 border rounded-lg"
                           placeholder="Ej: 3" min="2" value="2">
                    <p class="text-sm text-gray-500 mt-1">Mínimo 2 horas</p>
                </div>

                <button id="btn-calcular-acompanamiento" class="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition">
                    Calcular tarifa
                </button>
            </div>
        </div>

        <!-- Mapa -->
        <div class="bg-white rounded-lg shadow-lg p-6 mb-6">
            <div id="map" style="width: 100%; height: 400px; border-radius: 8px;"></div>
        </div>

        <!-- Resumen -->
        <div id="resumen" class="bg-white rounded-lg shadow-lg p-6 hidden">
            <h2 class="text-xl font-semibold mb-4">Resumen del servicio</h2>

            <div class="space-y-3">
                <div class="flex justify-between">
                    <span class="text-gray-600">Distancia:</span>
                    <span id="distancia" class="font-semibold">-</span>
                </div>

                <div class="flex justify-between">
                    <span class="text-gray-600">Tiempo estimado:</span>
                    <span id="tiempo" class="font-semibold">-</span>
                </div>

                <div class="flex justify-between text-xl font-bold border-t pt-3">
                    <span>Tarifa:</span>
                    <span id="tarifa" class="text-green-600">$0</span>
                </div>
            </div>

            <button id="btn-confirmar" class="w-full bg-green-600 text-white py-3 rounded-lg font-semibold hover:bg-green-700 transition mt-6">
                Confirmar solicitud
            </button>
        </div>

    </div>

    <!-- Leaflet JavaScript -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <!-- Leaflet Routing Machine JavaScript -->
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>

    <script>
        // TODO: Agregar aquí el código JavaScript de mapas y rutas
        // (Usar los ejemplos anteriores de este documento)
    </script>
</body>
</html>
```

---

## 📚 Referencias

- [Leaflet Routing Machine](https://www.liedman.net/leaflet-routing-machine/)
- [Leaflet Routing Machine API](https://www.liedman.net/leaflet-routing-machine/api/)
- [Leaflet Routing Machine Basic Tutorial](https://www.liedman.net/leaflet-routing-machine/tutorials/basic-usage/)
- [Distance calculation in Leaflet](https://medium.com/@nargessmi87/how-to-calculate-distance-between-two-points-in-leaflet-js-38b9c24e4c6d)
- [MucahidAydin/OpenStreetMap-flask-example](https://github.com/MucahidAydin/OpenStreetMap-flask-example)

---

## ✅ Próximos Pasos

1. ✅ Crear tabla `solicitudes_transporte` en la BD
2. ✅ Crear ruta `/servicios` en Flask
3. ✅ Adaptar el template HTML con el código de mapas
4. ✅ Implementar endpoint `/api/calcular-tarifa`
5. ✅ Implementar endpoint `/api/solicitar-servicio` (guardar en BD)
6. ✅ Crear notificación Telegram cuando llegue solicitud
7. ✅ Panel admin para ver y gestionar solicitudes
