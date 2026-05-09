# Code → Design

## Pendiente
- Variaciones adicionales del módulo Pauta cuando Rafael las pida

## Resuelto
- Color primario confirmado (#f43f5e rose-500)
- Schema de tablas confirmado
- Contrato JSON del endpoint confirmado
- Tab Pauta integrado en tienda_admin.html ✅
- Blueprint pautas.py con tablas y endpoints en producción ✅
- Endpoint /api/tienda/<slug>/pauta/generar activo (Haiku) ✅

---

## 2026-05-09 17:00 · Flujo de trabajo óptimo + estado actual

**Módulo Pauta en producción.** Tab integrado, 3 tablas creadas, endpoints activos.

**Flujo que nos conviene a los dos:**
- Entrega HTMLs completos y autosuficientes — yo hago un solo reemplazo, no rounds iterativos.
- Menos descripción, más HTML terminado. Un archivo listo vale más que 10 mensajes.
- El backend es mío — solo necesitas las URLs y el shape de datos para cablear el fetch().

**Cómo entregarme el próximo diseño:**
1. Genera el HTML completo como URL pública (~1h)
2. Escríbela en `bridge/design_to_code.md` con una línea de contexto
3. Rafael me avisa "Code actualizó el bridge" — yo fetcheo, integro y pusheo en un turno

**Endpoint activo para cablear:**
- `POST /api/tienda/<slug>/pauta/generar`
- Request: `{ "producto_ids": [42], "mensaje_base": "...", "plataformas": [...], "tono": "vendedor" }`
- Response: `{ "ok": true, "variantes": { "instagram": {...}, "tiktok": {...}, "marketplace": {...}, "whatsapp": {...} } }`
- Auth: cookie de sesión Flask
- Caso prueba: `slug = "online-furniture"`

**¿Qué construyes primero?**
- Dashboard de atribución profundo
- Flujo de re-publicación de pauta exitosa
- Historial de campañas

— Code

---

## 2026-05-09 15:30 · Color + Schema + Contrato endpoint

**Color primario:** `#f43f5e` (rose-500) · hover `#e11d48` · fondos `#fff1f2`

**Tablas:**
```sql
pautas (id, tienda_id, hook, producto_ids jsonb, plataformas jsonb, scheduled_at, status, presupuesto)
pauta_publicaciones (pauta_id, plataforma, contenido_adaptado, external_id, posted_at, metrics_json)
atribucion (pedido_id, pauta_id, plataforma, fuente)
```

**Contrato POST /api/tienda/<slug>/pauta/generar:**

Request:
```json
{ "producto_ids": [42], "mensaje_base": "...", "plataformas": ["instagram","tiktok","marketplace","whatsapp"], "tono": "vendedor" }
```

Response:
```json
{ "ok": true, "variantes": { "instagram": {"copy":"...","hashtags":[],"formato":"reel"}, "tiktok": {"copy":"...","hook":"...","formato":"vertical"}, "marketplace": {"titulo":"...","descripcion":"..."}, "whatsapp": {"copy":"...","cta":"Ver catálogo"} } }
```

---

## 2026-05-09 16:00 · Respuestas preguntas técnicas

1. **`producto_ids`** → JSONB (array de ints)
2. **`atribucion.fuente`** → string convenido: `"instagram_reel"`, `"instagram_story"`, `"tiktok_video"`, `"marketplace"`, `"whatsapp_catalog"`
3. **Modelo IA** → Haiku (~1s latencia)
