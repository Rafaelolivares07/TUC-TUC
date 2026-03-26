# Módulo Mensajería TUC TUC
## Documento de Desarrollo

**Estado:** MVP funcional + integración vendedor + cards (2026-03-26)
**Concepto:** Red de comunicación propia, crecimiento viral por token. Canal de distribución del catálogo TUC TUC.

---

## 1. Visión estratégica

TUC TUC no es solo una app de transporte y comercio — es una red. El módulo de mensajería siembra esa red desde el día 1, antes de tener miles de usuarios.

**Mecánica viral:**
```
Rafael → María (Tinder)
         María → Juan (Tinder)
                  Juan → ...
```

Nadie "instala una app". Cada persona llega porque quiere escuchar un audio. El crecimiento no depende de marketing — depende de que el producto sea suficientemente bueno para que la gente quiera usarlo para comunicarse.

**Ventaja sobre WhatsApp/Tinder:** audios sin dar el número de teléfono.

---

## 2. Flujo de uso

### Rafael (creador)
1. Entra a `/chat` (requiere sesión)
2. Toca `+ Invitar` → escribe nombre de la persona → se abre el chat directo
3. Graba un audio (el "hook") — **ANTES de compartir el link**
4. Toca **Compartir** en el header → link copiado al clipboard
5. Pega el link en Tinder/WhatsApp

### La invitada (María)
1. Abre el link → ve `"Rafael te envió un audio exclusivo 🎵"`
2. Escucha el audio — **solo disponible en TUC TUC**
3. Puede responder con texto o audio sin registrarse
4. Si quiere invitar a alguien más → puede hacerlo igual de fácil

---

## 3. Arquitectura técnica

### BD — tablas y columnas nuevas

**Tabla `conversaciones`** (nueva):
```sql
id SERIAL PRIMARY KEY,
creador_id INTEGER NOT NULL,    -- Rafael
invitado_id INTEGER NOT NULL,   -- María (tercero tipo 'invitado')
token VARCHAR(64) UNIQUE NOT NULL,
nombre_invitado VARCHAR(200),   -- nombre que Rafael le puso
origen VARCHAR(100),            -- 'Tinder', 'WhatsApp', etc.
creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
activa BOOLEAN DEFAULT TRUE
```

**Columnas añadidas a `terceros`:**
- `token_chat VARCHAR(64)` — token único del invitado
- `tipo_tercero VARCHAR(20) DEFAULT 'registrado'` — 'registrado' | 'invitado'

**Columnas añadidas a `mensajes`:**
- `url_archivo TEXT` — URL Cloudinary para audios e imágenes
- `conversacion_id INTEGER` — FK a conversaciones
- `card_payload JSONB` — payload de tarjeta de producto/plato (tipo='card')

⚠️ Se eliminaron los check constraints de `mensajes.tipo` para permitir tipo='audio', 'imagen', 'card'.

**Garantía de esquema:** `_asegurar_schema_chat(conn)` — se llama al inicio de `api_chat_invitado_mensajes` y `api_chat_invitado_enviar`. Nunca requiere endpoint manual.

### Audio
- Grabación: `MediaRecorder API` (webm en browser)
- Storage: Cloudinary, carpeta `tuctuc_chat_audio`, convertido a mp3
- `resource_type='video'` en Cloudinary (así maneja audio)

### Open Graph (preview del link)
El servidor lee el nombre del creador desde BD y lo inyecta en meta tags:
```html
<meta property="og:title" content="Rafael te envió un audio 🎵">
<meta property="og:description" content="¡Escúchalo aquí! Solo disponible en TUC TUC">
```

---

## 4. Endpoints Flask

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/chat/migrar-mensajeria` | Crea tabla conversaciones + columnas (auth, legado) |
| `POST` | `/api/chat/invitar` | Crea tercero invitado + conversación, devuelve token/link (requiere sesión) |
| `GET` | `/api/chat/invitado/mensajes/<token>` | Mensajes de una conv por token (público) |
| `POST` | `/api/chat/invitado/enviar` | Enviar mensaje texto/audio/imagen/card (público o auth con `es_creador:true`) |
| `POST` | `/api/chat/invitado/audio` | Upload audio → Cloudinary, devuelve URL |
| `POST` | `/api/chat/audio/chunk` | Acumula chunk de audio en `/tmp/` durante grabación streaming |
| `POST` | `/api/chat/audio/finalizar` | Sube chunks a Cloudinary, limpia temp, devuelve URL |
| `POST` | `/api/chat/invitado/imagen` | Upload imagen → Cloudinary (resize 1200px), devuelve URL |
| `GET` | `/api/chat/mis-conversaciones` | Panel Rafael — todas sus convs con no_leidos (auth) |
| `GET` | `/api/chat/mi-perfil` | Nombre, foto y `token_chat` del tercero autenticado |
| `GET` | `/api/chat/cards/negocios` | Restaurantes y tiendas del creador (por token_chat o sesión) |
| `GET` | `/api/chat/cards/items` | Platos u productos de un negocio (`?tipo=restaurante&slug=...`) |
| `POST` | `/api/chat/reclamar/<token>` | Marca token como usado en primera visita |
| `GET` | `/chat` | Panel Rafael (requiere sesión) |
| `GET` | `/chat/<token>` | Página pública invitado (sin sesión) |

---

## 5. Tipos de mensaje soportados

| `tipo` | Campo extra | Descripción |
|---|---|---|
| `texto` | — | Texto plano |
| `audio` | `url_archivo` | Audio Cloudinary (mp3), streaming de chunks durante grabación |
| `imagen` | `url_archivo` | Imagen Cloudinary (jpg resize 1200px), drag&drop + Ctrl+V |
| `card` | `card_payload` | Tarjeta de producto/plato (ver §5.1) |

### 5.1 Payload de card (`card_payload` JSONB)

```json
{
  "tipo_card": "plato" | "producto",
  "titulo":    "Bandeja paisa",
  "descripcion": "...",
  "precio":    18000,
  "imagen":    "https://res.cloudinary.com/...",
  "negocio":   "Restaurante El Fogón",
  "url":       "https://tuc-tuc.onrender.com/r/slug",
  "accion":    "Ver menú" | "Ver tienda"
}
```

Render en ambos templates: imagen full-width + nombre negocio (azul) + título + descripción + precio (verde) + botón acción. Click abre `url` en nueva pestaña.

---

## 6. Templates

### `chat.html` — template unificado (desde 2026-03-24)

Un único template reemplaza `chat_mensajeria.html` y `chat_invitado.html`. El modo se detecta via variable Jinja2:

```python
# Panel Rafael
render_template('chat.html', modo='creador', token='', nombre_creador='', foto_creador='', tercero_creador_id=0)

# Invitado
render_template('chat.html', modo='invitado', token=token, nombre_creador=..., foto_creador=..., tercero_creador_id=...)
```

Bloques Jinja2: `{% if modo == 'creador' %}` oculta/muestra sidebar, botones de invitar, etc.

**Layout (crítico):**
- `body { display: flex; flex-direction: row; height: 100dvh; overflow: hidden }` — sidebar y panel lado a lado
- Panel: `min-width: 0; min-height: 0` — permite scroll interno sin desbordarse
- `abrirConv()` / `volverSidebar()` usan `style.display` (no classList) para evitar conflicto con Tailwind `!important`

**Token de un solo uso (desde 2026-03-24):**
- BD: columnas `invitacion_usada BOOLEAN DEFAULT FALSE` + `invitacion_usada_en TIMESTAMP` en `conversaciones`
- Endpoint: `POST /api/chat/reclamar/<token>` — marca el token en la primera visita, devuelve `{error: 'ya_usado'}` si ya fue reclamado
- JS en `initInvitado()`: verifica `localStorage.getItem('claimed_TOKEN')` para distinguir dueño vs intrusos
- Primera visita: llama a `/reclamar`, guarda en localStorage; visitas posteriores del mismo device → pasan directo
- Si token ya usado por otro device: muestra pantalla 🔒 "Este enlace ya fue usado"

---

## 7. Deduplicación de mensajes

Race condition entre `poll()` inmediato post-envío y el intervalo de 3s.
Solución: `const idsRenderizados = new Set()` — si un ID ya fue renderizado, se ignora.
Se limpia al abrir nueva conversación con `idsRenderizados.clear()`.

---

## 8. Próximos pasos

- [ ] Notificación push/Telegram a Rafael cuando invitado responde
- [ ] El invitado puede crear su propio canal y atraer personas (expansión viral)
- [ ] Perfil TUC TUC propio del invitado — onboarding natural dentro del chat
- [ ] Integración con módulo de conductores / negocios (comunicación interna)
- [ ] Voz de Claude como respuesta en el chat de desarrollo (req #19)
- [x] ~~Cards de productos/platos (2026-03-26)~~
- [x] ~~Integración contactos vendedor ↔ chat (2026-03-26)~~
