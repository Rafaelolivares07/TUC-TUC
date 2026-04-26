# Tuc Tuc Rockola — Estado de Desarrollo
_Actualizado: 2026-04-22 10:30_

## Archivos

| Archivo | Descripción |
|---|---|
| `app/blueprints/rockola.py` | Backend — rutas, cola por sala, subida de archivos |
| `templates/rockola_cliente.html` | UI cliente restaurante — sube canciones, ve cola, drag&drop solo las suyas |
| `templates/rockola_reproductor.html` | UI reproductor restaurante — botón Activar, reproduce automático, ve cola |
| `templates/rockola_sync.html` | UI modo sync — todos son reproductores y clientes, drag&drop total |
| `static/rockola_tmp/<sala_id>/` | Archivos de audio temporales por sala |

---

## Arquitectura

- **Sin WebSocket** — polling HTTP cada 2 segundos (más robusto en Render free)
- **Sin almacenamiento permanente en servidor** — archivos en memoria/disco temporal
- **Cola por sala** — cada sala_id tiene su propia cola independiente
- **Owner tracking** — cada cliente tiene un ID en localStorage para controlar drag&drop

---

## URLs

### Modo restaurante
- Cliente: `/rockola/<sala_id>/cliente`
- Reproductor: `/rockola/<sala_id>/reproductor`

### Modo sync (todos reproductores)
- Todos: `/rockola/sync/<sala_id>`

### Rutas legacy (sala 'default')
- `/rockola/cliente` → `/rockola/default/cliente`
- `/rockola/reproductor` → `/rockola/default/reproductor`

---

## API

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/<sala_id>/subir` | Sube uno o varios archivos de audio |
| POST | `/<sala_id>/youtube` | Descarga audio de YouTube via cobalt.tools |
| GET | `/<sala_id>/cola` | Retorna la cola actual |
| POST | `/<sala_id>/siguiente` | Elimina primera canción (se llamó al terminar) |
| POST | `/<sala_id>/reordenar` | Reordena cola — en restaurante solo las propias |
| GET | `/<sala_id>/archivo/<id>` | Sirve el archivo de audio |

---

## Comportamiento por modo

| Característica | Restaurante | Sync |
|---|---|---|
| Reproductor | Solo el local (1 dispositivo) | Todos los que entran |
| Subir canciones | Clientes desde su celular | Todos |
| Drag & drop cola | Cada quien mueve solo la suya | Cualquiera mueve cualquiera |
| Sala | ID del negocio | Código compartido entre los dos |

---

## Flujo de reproducción

1. Cliente sube MP3 → POST `/subir` → servidor guarda en `static/rockola_tmp/<sala>/`
2. Reproductor polling cada 2s → GET `/cola` → ve canción nueva
3. Reproductor pone `player.src` → `player.play()` → suena
4. Al terminar → POST `/siguiente` → se elimina de cola
5. Polling detecta siguiente → reproduce sola

---

## Problema resuelto: autoplay en móvil

Los browsers bloquean autoplay hasta que el usuario haga un gesto. Solución: botón "Activar Rockola" / "Entrar a la sala" que hace `player.play().catch()` + `player.pause()` — esto desbloquea el autoplay para toda la sesión.

---

## YouTube → Cola (2026-04-23)

### Por qué no yt-dlp en Render
Las IPs de Render son datacenter conocidas — YouTube las bloquea con "Sign in to confirm you're not a bot" independientemente de cookies o `player_client`.

### Solución: cobalt.tools
`https://api.cobalt.tools/` es un servicio público que descarga audio de YouTube sin bot-check.

**Flujo en `rockola.py`:**
1. `POST /<sala_id>/youtube` recibe `{url, owner}`
2. Backend llama `POST api.cobalt.tools/` con `{url, downloadMode: 'audio', audioFormat: 'mp3'}`
3. cobalt devuelve `{status: 'tunnel'|'stream'|'redirect', url: '...', filename: '...'}`
4. Backend descarga el MP3 desde la URL de cobalt (stream de 65 KB)
5. Guarda en `static/rockola_tmp/<sala_id>/` y agrega a cola en BD

**Headers obligatorios para cobalt:**
```python
COBALT_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 ...',
    'Origin': 'https://cobalt.tools',
    'Referer': 'https://cobalt.tools/',
}
```

### Auto-paste clipboard en tab YouTube (cliente)
Cuando el usuario toca el tab "YouTube" en `rockola_cliente.html`, si el clipboard contiene una URL de YouTube, la pega automáticamente en el input.

```js
async function setTab(tab) {
    if (tab === 'youtube') {
        try {
            const txt = await navigator.clipboard.readText();
            if (txt.includes('youtube.com') || txt.includes('youtu.be'))
                document.getElementById('yt-url').value = txt;
        } catch {}
    }
}
```

---

## Pendientes próxima iteración

- Dashboard del dueño — activar rockola, precio por canción, duración máxima
- Integrar "Rockola" como ítem en carta del restaurante
- Créditos — cliente paga → obtiene derecho a subir canción
- QR propio por sala con afiche
- Código de reproductor (PIN) para autorizar dispositivo del local
- Limpieza de archivos temporales en servidor (cron)
- Biblioteca del dueño — canciones que van quedando en su dispositivo

---

## Pruebas realizadas (2026-04-22)

- ✅ Subida de MP3 desde PC → servidor (barra de progreso)
- ✅ Reproductor Android recibe y reproduce automático
- ✅ Canción completa sin interrupciones
- ⬜ Cola drag & drop
- ⬜ Multi-archivo
- ⬜ Modo sync con dos dispositivos
- ⬜ Salas independientes
