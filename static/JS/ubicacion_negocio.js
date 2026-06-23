(function () {
    'use strict';

    const cfg = window.TUC_TUC_UBICACION;
    if (!cfg) return;

    const REGIONES = {
        cali: {
            nombre: 'Cali y alrededores',
            center: [-76.5320, 3.4516],
            tiles: '/static/maps/cali.pmtiles'
        },
        medellin: {
            nombre: 'Medellin y area metropolitana',
            center: [-75.5800, 6.2450],
            tiles: '/static/maps/medellin.pmtiles'
        }
    };

    let _mapaUbic = null;
    let _markerUbic = null;
    let _latUbic = cfg.lat;
    let _lonUbic = cfg.lon;
    let _mapaRegion = 'cali';
    let _modoCobertura = false;
    let _coberturaPuntos = [];
    let _configNegocioUbic = null;
    let _protocoloRegistrado = false;

    function notificar(mensaje, error) {
        if (typeof cfg.notify === 'function') cfg.notify(mensaje, Boolean(error));
    }

    function regionPorCoordenadas(lat, lon) {
        lat = Number(lat);
        lon = Number(lon);
        if (lat >= 5.9 && lat <= 6.7 && lon >= -76.0 && lon <= -75.2) return 'medellin';
        return 'cali';
    }

    function estiloMapa(region) {
        return {
            version: 8,
            glyphs: 'https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf',
            sprite: 'https://protomaps.github.io/basemaps-assets/sprites/v4/light',
            sources: {
                protomaps: {
                    type: 'vector',
                    url: `pmtiles://${REGIONES[region].tiles}`,
                    attribution: '&copy; OpenStreetMap'
                }
            },
            layers: basemaps.layers('protomaps', basemaps.namedFlavor('light'), {lang: 'es'})
        };
    }

    async function cargarConfiguracionUbicacion() {
        if (!cfg.terceroId) return;
        try {
            const response = await fetch(`/api/negocio/${cfg.terceroId}/config`);
            const data = await response.json();
            if (!data.ok) return;
            _configNegocioUbic = data.config || {};
            _coberturaPuntos = Array.isArray(_configNegocioUbic.domicilio_zona)
                ? _configNegocioUbic.domicilio_zona
                : [];
            _mapaRegion = REGIONES[_configNegocioUbic.mapa_region]
                ? _configNegocioUbic.mapa_region
                : regionPorCoordenadas(_latUbic, _lonUbic);
            const selector = document.getElementById('mapa-region');
            if (selector) selector.value = _mapaRegion;
        } catch (error) {
            notificar('No se pudo cargar la configuracion del mapa', true);
        }
    }

    async function iniciarMapaUbicacion() {
        if (_mapaUbic) {
            _mapaUbic.resize();
            dibujarCobertura();
            return;
        }
        if (!_configNegocioUbic) await cargarConfiguracionUbicacion();
        crearMapa(false);
    }

    function crearMapa(forzarCentroRegion) {
        if (!_protocoloRegistrado) {
            const protocol = new pmtiles.Protocol();
            maplibregl.addProtocol('pmtiles', protocol.tile);
            _protocoloRegistrado = true;
        }
        const region = REGIONES[_mapaRegion] || REGIONES.cali;
        const tieneUbicacion = Number.isFinite(Number(_latUbic)) && Number.isFinite(Number(_lonUbic));
        const center = tieneUbicacion && !forzarCentroRegion
            ? [Number(_lonUbic), Number(_latUbic)]
            : region.center;

        _mapaUbic = new maplibregl.Map({
            container: 'mapa-ubicacion',
            style: estiloMapa(_mapaRegion),
            center,
            zoom: tieneUbicacion && !forzarCentroRegion ? 17 : 13,
            attributionControl: false
        });
        _mapaUbic.addControl(new maplibregl.NavigationControl({showCompass: false}), 'top-right');
        _mapaUbic.on('load', () => {
            if (tieneUbicacion) colocarMarker(Number(_lonUbic), Number(_latUbic));
            dibujarCobertura();
        });
        _mapaUbic.on('click', event => {
            if (_modoCobertura) agregarPuntoCobertura(event.lngLat.lng, event.lngLat.lat);
            else colocarMarker(event.lngLat.lng, event.lngLat.lat);
        });
    }

    async function cambiarRegionMapa(region) {
        if (!REGIONES[region]) return;
        _mapaRegion = region;
        if (cfg.terceroId) {
            try {
                const response = await fetch(`/api/negocio/${cfg.terceroId}/ubicacion-config`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mapa_region: region})
                });
                const data = await response.json();
                if (!data.ok) throw new Error(data.error || 'Error guardando ciudad');
            } catch (error) {
                notificar(error.message || 'No se pudo guardar la ciudad', true);
                return;
            }
        }
        if (_mapaUbic) {
            _mapaUbic.remove();
            _mapaUbic = null;
            _markerUbic = null;
            crearMapa(true);
        }
        notificar(`Mapa cambiado a ${REGIONES[region].nombre}`, false);
    }

    function colocarMarker(lon, lat) {
        if (_markerUbic) _markerUbic.remove();
        const element = document.createElement('div');
        element.innerHTML = `<svg width="32" height="40" viewBox="0 0 32 40" fill="none"><path d="M16 0C9.37 0 4 5.37 4 12c0 9 12 28 12 28S28 21 28 12C28 5.37 22.63 0 16 0Z" fill="${cfg.markerColor}"/><circle cx="16" cy="12" r="5" fill="white"/></svg>`;
        _markerUbic = new maplibregl.Marker({element, anchor: 'bottom'})
            .setLngLat([lon, lat])
            .addTo(_mapaUbic);
        _latUbic = Number(lat);
        _lonUbic = Number(lon);
        document.getElementById('txt-coords-ub').textContent = `${_latUbic.toFixed(5)}, ${_lonUbic.toFixed(5)}`;
    }

    function gpsUbicacion() {
        if (!navigator.geolocation) return notificar('GPS no disponible', true);
        activarModoUbicacion();
        notificar('Localizando...', false);
        navigator.geolocation.getCurrentPosition(
            position => {
                if (!_mapaUbic) return;
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                _mapaUbic.flyTo({center: [lon, lat], zoom: 17});
                colocarMarker(lon, lat);
            },
            () => notificar('No se pudo obtener GPS', true),
            {enableHighAccuracy: true, timeout: 10000}
        );
    }

    async function guardarUbicacion() {
        if (!Number.isFinite(Number(_latUbic)) || !Number.isFinite(Number(_lonUbic))) {
            return notificar('Toca el mapa para marcar tu ubicacion', true);
        }
        try {
            const response = await fetch(`/api/${cfg.tipo}/${cfg.slug}/admin/ubicacion`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({lat: _latUbic, lon: _lonUbic})
            });
            const data = await response.json();
            if (!data.ok) throw new Error(data.error || 'Error guardando ubicacion');
            document.getElementById('coords-guardadas').classList.remove('hidden');
            notificar('Ubicacion guardada', false);
        } catch (error) {
            notificar(error.message || 'Error de conexion', true);
        }
    }

    function activarDibujoCobertura() {
        _modoCobertura = true;
        actualizarModoMapaTexto();
    }

    function activarModoUbicacion() {
        _modoCobertura = false;
        actualizarModoMapaTexto();
    }

    function actualizarModoMapaTexto() {
        const buttonLocation = document.getElementById('btn-modo-ubicacion');
        const buttonCoverage = document.getElementById('btn-modo-cobertura');
        const active = cfg.activeClasses;
        const inactive = cfg.inactiveClasses;
        if (buttonLocation) buttonLocation.className = _modoCobertura ? inactive : active;
        if (buttonCoverage) buttonCoverage.className = _modoCobertura ? active : inactive;
        const text = document.getElementById('txt-cobertura');
        if (text) {
            text.textContent = _modoCobertura
                ? `${_coberturaPuntos.length} punto(s). Toca el mapa para agregar puntos al perimetro.`
                : `${_coberturaPuntos.length} punto(s) de cobertura. Modo mover negocio activo.`;
        }
    }

    function agregarPuntoCobertura(lon, lat) {
        _coberturaPuntos.push({lat: Number(lat), lon: Number(lon)});
        dibujarCobertura();
    }

    function limpiarCobertura() {
        _coberturaPuntos = [];
        dibujarCobertura();
    }

    function dibujarCobertura() {
        if (!_mapaUbic || !_mapaUbic.isStyleLoaded()) return;
        const coordinates = _coberturaPuntos.map(point => [Number(point.lon), Number(point.lat)]);
        const closed = coordinates.length >= 3 ? [...coordinates, coordinates[0]] : coordinates;
        const data = {
            type: 'FeatureCollection',
            features: coordinates.length >= 3
                ? [{type: 'Feature', geometry: {type: 'Polygon', coordinates: [closed]}, properties: {}}]
                : []
        };
        if (!_mapaUbic.getSource('cobertura-domicilio')) {
            _mapaUbic.addSource('cobertura-domicilio', {type: 'geojson', data});
            _mapaUbic.addLayer({
                id: 'cobertura-fill', type: 'fill', source: 'cobertura-domicilio',
                paint: {'fill-color': cfg.coverageColor, 'fill-opacity': 0.15}
            });
            _mapaUbic.addLayer({
                id: 'cobertura-line', type: 'line', source: 'cobertura-domicilio',
                paint: {'line-color': cfg.coverageColor, 'line-width': 2}
            });
        } else {
            _mapaUbic.getSource('cobertura-domicilio').setData(data);
        }
        actualizarModoMapaTexto();
    }

    async function guardarCobertura() {
        if (!cfg.terceroId) return notificar('Este negocio no tiene tercero asociado', true);
        try {
            const response = await fetch(`/api/negocio/${cfg.terceroId}/ubicacion-config`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({domicilio_zona: _coberturaPuntos})
            });
            const data = await response.json();
            if (!data.ok) throw new Error(data.error || 'Error guardando cobertura');
            _modoCobertura = false;
            actualizarModoMapaTexto();
            notificar('Cobertura guardada', false);
        } catch (error) {
            notificar(error.message || 'Error de conexion', true);
        }
    }

    window.iniciarMapaUbicacion = iniciarMapaUbicacion;
    window.cambiarRegionMapa = cambiarRegionMapa;
    window.gpsUbicacion = gpsUbicacion;
    window.guardarUbicacion = guardarUbicacion;
    window.activarDibujoCobertura = activarDibujoCobertura;
    window.activarModoUbicacion = activarModoUbicacion;
    window.limpiarCobertura = limpiarCobertura;
    window.guardarCobertura = guardarCobertura;
})();
