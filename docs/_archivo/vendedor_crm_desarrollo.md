# CRM Vendedor — Documento de Desarrollo
**Última actualización: 2026-03-26 (rev. integración chat TUC TUC + cards)**

---

## 1. Estado actual implementado

### URL
`/vendedor` — dashboard público, sin login obligatorio. El vendedor se identifica por su teléfono (input en la página).

### Módulos activos
- **Selector de negocio activo** — en el header, visible después de identificarse. Auto-asigna TUC TUC si no hay asignación previa. Permite cambiar entre negocios representados.
- **Agenda de citas** — crear, ver, marcar como completada. Guarda `negocio_id` (contexto del negocio para el que se vende)
- **Contactos** — lista personal del vendedor (colapsable), importar desde CSV/texto, buscar. **Los contactos son del vendedor, no del negocio.**
- **Demo launcher** — situaciones predefinidas + lanzar WhatsApp con rol asignado
- **Plantillas CRM** — mensajes pregrabados, pool compartido entre TODOS los usuarios de la plataforma (sin `negocio_id`). Soporta crear, editar (botón ✏) y eliminar.
- **Modal unificado de comunicación** — historial del contacto + selector de canal (WA/Telegram) + compose + envío
- **Log de envíos** — general (mis envíos recientes) + por contacto. Guarda `mensaje_enviado` (texto real enviado) + `negocio_id`

### Layout del dashboard (orden actual)
1. Header con selector de negocio activo
2. Demo launcher / situaciones
3. Comisión
4. Mis envíos recientes (colapsable)
5. Mis contactos (colapsable, cerrado por defecto)
6. Objeciones frecuentes (colapsable)
7. Antes de entrar al local / checklist (colapsable)

### Tablas de BD involucradas
| Tabla | Qué guarda | `negocio_id` |
|---|---|---|
| `contactos` | Lista de prospectos — del vendedor, no del negocio | ❌ NO |
| `plantillas_crm` | Mensajes pregrabados — pool global de la plataforma | ❌ NO |
| `plantillas_crm_envios` | Log de envíos: `plantilla_id` (nullable), `contacto_id`, `vendedor_id`, `medio`, `mensaje_enviado`, `negocio_id` | ✅ SÍ |
| `citas_vendedor` | Agenda de citas del vendedor | ✅ SÍ |
| `vendedor_negocios` | Relación vendedor ↔ negocios que representa | tabla de relación |

### Columnas migradas (historial)
- `plantillas_crm_envios.plantilla_id` → nullable
- `plantillas_crm_envios.medio` → `VARCHAR(20) DEFAULT 'whatsapp'`
- `plantillas_crm_envios.mensaje_enviado` → `TEXT` (texto real enviado, no el de la plantilla)
- `plantillas_crm_envios.negocio_id` → `INTEGER` (contexto del negocio para el que se vendió)
- `citas_vendedor.negocio_id` → `INTEGER`
- `contactos.chat_token TEXT` → token de la conversación de chat TUC TUC del contacto (2026-03-26)

---

## 2. Decisiones de arquitectura acordadas

### 2.1 Identificador universal de negocio = `terceros.id`

Tanto personas como negocios son `terceros`. TUC TUC mismo tiene su propio `tercero_id` como entidad.

```
TUC TUC (plataforma)              → terceros donde nombre='TUC TUC' y telefono IS NULL
Restaurante El Rincón (negocio)   → terceros.id = 42
Don Carlos (persona/vendedor)     → terceros.id = 5
```

### 2.2 Contactos son del vendedor, NO del negocio

Un vendedor puede representar múltiples negocios, pero su base de contactos es personal — la construyó él. Los mismos contactos sirven para cualquier negocio que represente. La tabla `contactos` NO tiene `negocio_id`.

### 2.3 Plantillas son globales de la plataforma

Las plantillas en `plantillas_crm` son herramientas genéricas de comunicación. Todos los vendedores de todos los negocios las ven y pueden usarlas. **NO tienen `negocio_id`.**

### 2.4 Multi-negocio — implementado (2026-03-23)

Dos tablas cubren los negocios de un vendedor:
- `vendedor_negocios(vendedor_id, negocio_id, activo)` — negocios genéricos (terceros directos)
- `tienda_vendedores(tienda_id, vendedor_id, activo)` — tiendas del módulo tienda

`GET /api/vendedor/mis-negocios?tel=...` consulta ambas y devuelve la lista unificada con `id = terceros.id` del negocio como entidad.

Flujo:
1. Vendedor se identifica por teléfono
2. Sistema llama `GET /api/vendedor/mis-negocios?tel=...`
3. Combina `vendedor_negocios` + `tienda_vendedores`
4. Si tiene varios → selector dropdown en header del dashboard
5. El negocio seleccionado (`_negocioActivo.id`) se pasa en citas y envíos — siempre es `tercero_id`

**Bug conocido / resuelto (2026-03-23)**: `tiendas.tercero_id` se guardaba con el `admin_id` del creador, no con el id del negocio como entidad. El API ahora lo detecta y auto-crea el tercero del negocio si falta, actualizando `tiendas.tercero_id` al vuelo.

IDs conocidos:
- TUC TUC entidad → `terceros.id = 101` (nombre='TUC TUC', telefono IS NULL)
- Tang Solar entidad → tercero creado en deploy 2026-03-23

**Deuda técnica pendiente**: al crear una tienda, debería crearse automáticamente su tercero como entidad y asignarse a `tiendas.tercero_id`. Hoy el fix es reactivo (se corrige al primer acceso del vendedor).

---

## 3. APIs del módulo CRM

### Identidad
- `POST /api/vendedor/identificar` — busca/crea tercero por teléfono

### Negocios
- `GET /api/vendedor/mis-negocios?tel=...` — negocios que representa el vendedor (auto-asigna TUC TUC si ninguno)

### Citas
- `GET /api/vendedor/citas?cod=<tel>` — lista citas próximas
- `POST /api/vendedor/cita` — crea cita + pre-crea negocio en plataforma. Acepta `negocio_id`
- `POST /api/vendedor/cita/<id>/estado` — actualiza estado

### Contactos
- `GET /api/vendedor/contactos?tel=...` — lista contactos del vendedor, incluye `chat_token` (directo o cruzado por teléfono)
- `POST /api/vendedor/contacto` — crea o actualiza contacto
- `GET /api/vendedor/buscar-terceros?q=...` — autocomplete terceros
- `POST /api/vendedor/contactos/<cid>/chat` — crea o recupera conversación de chat para el contacto (body: `{tel}`)
  - Usa `vendedor_tid` como `creador_id` en `conversaciones` (sin requerir sesión)
  - Si el contacto tiene teléfono: busca tercero existente; si no: crea uno con `tipo_tercero='invitado'`
  - Guarda `chat_token` en `contactos` para accesos futuros
  - Responde `{ok, token, link, nuevo}`

### Plantillas
- `GET /api/vendedor/plantillas?tel=...` — lista todas las plantillas (pool global)
- `POST /api/vendedor/plantillas` — crea nueva plantilla
- `PUT /api/vendedor/plantillas/<pid>` — edita plantilla existente
- `DELETE /api/vendedor/plantillas/<pid>` — elimina

### Envíos
- `POST /api/vendedor/plantillas/envio` — registra envío (WA o Telegram). Guarda `mensaje_enviado` + `negocio_id`
- `GET /api/vendedor/envios?tel=...` — mis envíos recientes (últimos 100)
- `GET /api/vendedor/envios/contacto/<cid>` — historial de envíos a un contacto

---

## 4. Canales de comunicación — comportamiento

### Modal unificado (`modal-wa-contacto`)
1. Nombre del contacto (cabecera)
2. Historial de mensajes previos (texto real, medio, fecha)
3. Selector de canal: [💬 WhatsApp] [✈️ Telegram]
4. Zona compose (plantillas editables + textarea)
5. Botón enviar

### WhatsApp
| Contexto | URL usada |
|---|---|
| Móvil | `wa.me/NUM?text=MSG` |
| Desktop con app | `whatsapp://send?phone=NUM&text=MSG` |
| Desktop sin app | `https://web.whatsapp.com/send?phone=NUM&text=MSG` |

Detección app nativa: `visibilitychange` — si la página pierde foco en <1.5s → app abierta.

### Historial de envíos recientes
Muestra: ícono canal + nombre contacto + título plantilla + texto enviado (2 líneas) + fecha + botón 💬 verde para retomar contacto.

---

## 5. Integración Chat TUC TUC (2026-03-26)

### Concepto
El chat es el canal de mayor cercanía con el contacto. Desde el panel del vendedor se puede abrir o crear una conversación de chat para cualquier contacto, y desde ese chat compartir productos/platos como cards interactivas.

### Flujo completo
1. Vendedor ve su lista de contactos en `/vendedor`
2. Contactos con chat activo muestran punto verde + etiqueta "Chat TUC TUC activo"
3. Botón burbuja (verde = ya tiene chat, gris = no tiene):
   - Si tiene → abre `/chat/<token>` en nueva pestaña
   - Si no tiene → `POST /api/vendedor/contactos/<cid>/chat` → crea conv → abre en nueva pestaña
4. Dentro del chat (modo creador), botón carrito → modal selector de negocios → ítems → envía card al contacto
5. El contacto (en su pestaña de invitado) ve la card con imagen, precio y botón para ver el menú/tienda

### Cómo se vinculan los mundos

```
contactos.tercero_id  →  terceros.id (vendedor = dueño de la lista)
contactos.chat_token  →  conversaciones.token
conversaciones.creador_id  →  terceros.id (vendedor)
conversaciones.invitado_id →  terceros.id (contacto, tipo='invitado' o 'registrado')
```

**Nota:** `contactos.tercero_id` identifica al VENDEDOR (dueño de la lista), no al contacto. El contacto se identifica por su `telefono` o por `chat_token`.

### UI en renderContactos
```
[avatar + punto verde]  Nombre del contacto
                        Número de teléfono
                        Chat TUC TUC activo  ← si tiene chat
  [📞] [💬 WA] [🟢burbuja] [📅] [✕]
```

---

## 6. Modelo de comisión (referencia)
Ver `docs/estrategia_comercial.md` para detalle.
- Vendedor externo: 20% de cada recaudo, sin salario
- Vendedor interno: $2.7M/mes fijo, sin comisión
