# Estado de Sesión Activa
_Actualizado: 2026-03-26_

## Módulo en trabajo
**Chat + CRM Vendedor** — integración chat ↔ contactos + cards de productos

## Commits de esta sesión — pusheados

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
- Probar en producción: abrir `/vendedor`, identificarse, buscar un contacto → botón burbuja → verificar que abre el chat
- Probar card: en `/chat` modo creador, tocar botón carrito → seleccionar negocio → enviar card → verificar render en `chat_invitado.html`
- Streaming de audio (commit `5a8f2d4` sesión anterior): pendiente verificar que los chunks se limpian correctamente en producción

## Contexto técnico
- bypassPermissions activo en `~/.claude/settings.json` ✓
- Rafael trabaja en Cali, Colombia — timezone America/Bogota
- App en producción: `tuc-tuc.onrender.com`
- Todas las migraciones de BD son automáticas vía `_asegurar_*` / `crear_tablas_*` — no se requiere llamar endpoints manuales
