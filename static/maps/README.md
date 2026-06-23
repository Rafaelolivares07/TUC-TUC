# Mapas locales PMTiles

Los mapas administrativos de ubicacion se sirven localmente para evitar depender de una API cartografica por cada visualizacion.

## Regiones disponibles

| Region | Archivo | Centro | Cobertura aproximada | Zoom maximo |
|---|---|---|---|---:|
| Cali | `cali.pmtiles` | `-76.5320, 3.4516` | `-76.62,3.32,-76.44,3.52` | 15 |
| Medellin | `medellin.pmtiles` | `-75.5800, 6.2450` | `-75.66,6.14,-75.50,6.35` | 15 |

## Fuente

Protomaps Basemap, derivado de OpenStreetMap y Natural Earth. El extracto de Medellin fue generado el 23 de junio de 2026 desde:

`https://build.protomaps.com/20260623.pmtiles`

Comando reproducible con `go-pmtiles`:

```powershell
pmtiles extract https://build.protomaps.com/20260623.pmtiles static/maps/medellin.pmtiles `
  --bbox=-75.66,6.14,-75.50,6.35 --minzoom=0 --maxzoom=15
```

La configuracion de cada region vive en `static/JS/ubicacion_negocio.js`. Para agregar una ciudad se debe crear el extracto, registrar su centro/archivo y habilitarla en la validacion de `mapa_region`.
