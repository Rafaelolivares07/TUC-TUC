# Módulo Mensajería TUC TUC
## Documento de Desarrollo

**Estado:** MVP funcional (2026-03-24)
**Concepto:** Red de comunicación propia, crecimiento viral por token

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
- `url_archivo TEXT` — URL Cloudinary para audios
- `conversacion_id INTEGER` — FK a conversaciones

⚠️ Se eliminaron 8 check constraints de `mensajes.tipo` para permitir tipo='audio'.

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
| `POST` | `/api/chat/migrar-mensajeria` | Crea tabla conversaciones + columnas (auth) |
| `POST` | `/api/chat/invitar` | Crea tercero invitado + conversación, devuelve token/link |
| `GET` | `/api/chat/invitado/mensajes/<token>` | Mensajes de una conv por token (público) |
| `POST` | `/api/chat/invitado/enviar` | Enviar mensaje (público o auth con `es_creador:true`) |
| `POST` | `/api/chat/invitado/audio` | Upload audio → Cloudinary, devuelve URL |
| `GET` | `/api/chat/mis-conversaciones` | Panel Rafael — todas sus convs con no_leidos (auth) |
| `POST` | `/api/chat/fix-tipo-audio` | Drop check constraints en mensajes.tipo (auth, one-time) |
| `GET` | `/chat` | Panel Rafael (requiere sesión) |
| `GET` | `/chat/<token>` | Página pública invitado (sin sesión) |

---

## 5. Templates

### `chat_mensajeria.html` — panel de Rafael
- Sidebar izquierdo: lista conversaciones con badge no-leídos
- Panel derecho: chat activo con polling cada 3s
- `md:!flex` en sidebar — nunca se oculta en desktop (importante override CSS)
- Botón **Compartir** en header del chat (no modal — flujo correcto: audio primero)
- `idsRenderizados` Set — evita mensajes duplicados por race condition en polling
- Audio: MediaRecorder → upload Cloudinary → enviar como mensaje tipo 'audio'

### `chat_invitado.html` — página pública
- Mobile-first, full screen con `100dvh` (dynamic viewport height)
- `env(safe-area-inset-bottom)` para iOS
- Hook especial: primer audio del creador → card prominente "exclusivo"
- Nombre editable por el invitado (localStorage)
- Speech-to-text dictado: Web Speech API, `lang='es-CO'`, continuo
- Audio recording: MediaRecorder → Cloudinary → mensaje

---

## 6. Deduplicación de mensajes

Race condition entre `poll()` inmediato post-envío y el intervalo de 3s.
Solución: `const idsRenderizados = new Set()` — si un ID ya fue renderizado, se ignora.
Se limpia al abrir nueva conversación con `idsRenderizados.clear()`.

---

## 7. Próximos pasos

- [ ] Notificación push/Telegram a Rafael cuando invitado responde
- [ ] El invitado puede crear su propio canal y atraer personas (expansión viral)
- [ ] Perfil TUC TUC propio del invitado — onboarding natural dentro del chat
- [ ] Integración con módulo de conductores / negocios (comunicación interna)
- [ ] Voz de Claude como respuesta en el chat de desarrollo (req #19)
