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
| `POST` | `/api/chat/reclamar/<token>` | Marca token como usado en primera visita; devuelve `ya_usado` si ya fue reclamado por otro device |
| `GET` | `/chat` | Panel Rafael (requiere sesión) |
| `GET` | `/chat/<token>` | Página pública invitado (sin sesión) |

---

## 5. Templates

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
