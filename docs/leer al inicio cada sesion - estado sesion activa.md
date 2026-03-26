# Estado de Sesión Activa
_Actualizado: 2026-03-26_

## Módulo en trabajo
**Chat — refactor arquitectura unificada terceros_id**

## Commits de esta sesión — pusheados

### Commit `c2d5abb` — refactor(chat): arquitectura unificada — todos son terceros_id
- Elimina distinción `modo='creador'/'invitado'` del template y del backend
- `get_chat_tercero_id()` — helper que resuelve identidad desde `session['usuario_id']` o `session['chat_tercero_id']`
- `/chat/<token>` establece `session['chat_tercero_id']` — invitados tienen sesión real, no solo token
- `mis-conversaciones` — query unificada: convs donde el tercero es `creador_id` OR `invitado_id`
- `esMio` en JS: `remitente_id === MI_TERCERO_ID` (antes comparaba `remitente_tipo`)
- `es_creador` calculado en JS: `convData[tok]?.creador_id === MI_TERCERO_ID`
- `POST /api/chat/registrar-telefono` — flujo de upgrade: Caso A (asignar tel) + Caso B (merge a tercero existente con ese tel)
- Sidebar y panel funcionales para cualquier tercero autenticado (registrado o por token)
- `TOKEN_INICIAL` Jinja var — auto-abre la conversación correcta al cargar para visitantes por link
- `enviarCard`, `enviarImagenFile`, `toggleGrabacion`, `enviarTexto`, `abrirSelectorCard` — todos usan `tokenActivo` sin `MODO`

## Commits previos — pusheados

### Commit `ea8dfd1` — feat(merlin): Merlin como contacto en el chat TUC TUC
- `chat_merlin_bridge.py` — daemon local: detecta mensajes a Merlin, llama `claude --print`, responde
- `start_merlin_bridge.bat` — auto-restart loop para el bridge
- `POST /api/chat/merlin/iniciar` — crea/recupera conv con Merlin para usuario autenticado
- `chat.html`: botón "Merlin" (índigo) en sidebar header, avatar especial índigo + badge "IA" en lista convs
- `tipo_tercero='merlin'` — tercero se crea automáticamente en primera llamada al endpoint
- **Para activar localmente**: ejecutar `start_merlin_bridge.bat`

### Commit `606bb0f` — feat(vendedor+chat): integrar contactos con chat TUC TUC
- `contactos.chat_token TEXT` — nueva columna (se crea automáticamente vía `crear_tablas_contactos`)
- `GET /api/vendedor/contactos` ahora devuelve `chat_token` por contacto: primero busca en `contactos.chat_token`, si no existe busca por teléfono cruzando `conversaciones + terceros`
- `POST /api/vendedor/contactos/<cid>/chat` — crea o recupera conversación para un contacto sin requerir sesión admin. Usa `vendedor_tid` como `creador_id`. Guarda `chat_token` en el contacto para próximos accesos
- `renderContactos`: punto verde en avatar si tiene chat activo + etiqueta "Chat TUC TUC activo"
- Botón burbuja en cada contacto: abre conv existente (nueva pestaña) o crea nueva vía API
- `abrirChatContacto()`: spinner, llamada POST, actualiza lista en memoria sin recargar

### Commit `8df42c9` — feat(chat): tipo 'card' y selector de productos/platos
- `mensajes.card_payload JSONB` — nuevo tipo de mensaje `tipo='card'`
- `_asegurar_schema_chat(conn)` — garantiza las 3 columnas de mensajes automáticamente (url_archivo, conversacion_id, card_payload) — se llama en `api_chat_invitado_mensajes` y `api_chat_invitado_enviar`
- `POST /api/chat/invitado/enviar` acepta `card_payload` (dict JSON)
- `GET /api/chat/cards/negocios?token_chat=` — restaurantes y tiendas del creador
- `GET /api/chat/cards/items?tipo=&slug=` — platos (opciones_menu) o productos (productos_tienda) con imagen/precio
- `GET /api/chat/mi-perfil` ahora devuelve `token_chat` del tercero
- Render de card en `chat.html` y `chat_invitado.html`: imagen, negocio, título, precio, botón acción. Click abre la URL del negocio en nueva pestaña
- Botón carrito (ícono bolsa) en barra de botones del creador
- Modal selector: lista negocios del creador (chips) → lista ítems → click envía la card
- Filtro de búsqueda en tiempo real dentro del modal

### Commit `4fce639` — fix(chat): migración card_payload via _asegurar_schema_chat
- Eliminada dependencia del endpoint manual `/api/chat/migrar-mensajeria`
- `_asegurar_schema_chat(conn)` corre automáticamente en cada request

### Commit `ec85ff6` — docs: ampliar convenio §6 migraciones BD
- `docs/convenios_desarrollo.md` §6 ampliado con checklist, tabla de funciones existentes, antipatrones

## Próximos pasos sugeridos
- Probar en producción: usuario registrado abre `/chat` → sidebar con sus convs (como creador E invitado)
- Probar acceso por token `/chat/<token>` → sidebar + panel → registro de teléfono desde el banner
- Verificar Caso B del registro: teléfono ya existe → merge de tercero → session promovida a `usuario_id`
- Merlin: verificar que `abrirChatMerlin()` funciona para cualquier tercero autenticado
- Streaming de audio (commit `5a8f2d4`): pendiente verificar limpieza de chunks en producción

## Contexto técnico
- bypassPermissions activo en `~/.claude/settings.json` ✓
- Rafael trabaja en Cali, Colombia — timezone America/Bogota
- App en producción: `tuc-tuc.onrender.com`
- Todas las migraciones de BD son automáticas vía `_asegurar_*` / `crear_tablas_*` — no se requiere llamar endpoints manuales
