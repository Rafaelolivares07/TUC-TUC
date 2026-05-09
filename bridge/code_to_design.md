# Code → Design

## Pendiente
- Publicar endpoint /api/pautas/generar real
- Crear tablas en BD

## Resuelto
- Color primario confirmado
- Schema de tablas confirmado
- Contrato JSON del endpoint confirmado
- Respuestas a preguntas técnicas (ver abajo)

---

## 2026-05-09 15:30 · Color + Schema + Contrato endpoint

**Color primario:** `#f43f5e` (rose-500) · hover `#e11d48` · fondos `#fff1f2`

**Tablas:**
```sql
pautas (id, tienda_id, hook, producto_ids jsonb, plataformas jsonb, scheduled_at, status, presupuesto)
pauta_publicaciones (pauta_id, plataforma, contenido_adaptado, external_id, posted_at, metrics_json)
atribucion (pedido_id, pauta_id, plataforma, fuente)
```

**Contrato POST /api/pautas/generar:**

Request:
```json
{ "tienda_id": 1, "producto_ids": [42], "mensaje_base": "...", "plataformas": ["instagram","tiktok","marketplace","whatsapp"], "tono": "vendedor" }
```

Response:
```json
{ "ok": true, "variantes": { "instagram": {"copy":"...","hashtags":[],"formato":"reel"}, "tiktok": {"copy":"...","hook":"...","formato":"vertical"}, "marketplace": {"titulo":"...","descripcion":"..."}, "whatsapp": {"copy":"...","cta":"Ver catálogo"} } }
```

---

## 2026-05-09 16:00 · Respuestas preguntas técnicas

1. **`producto_ids`** → JSONB (array de ints). Patrón estándar TUC TUC para arrays en PostgreSQL.

2. **`atribucion.fuente`** → string libre con valores convenidos, no enum. Valores: `"instagram_reel"`, `"instagram_story"`, `"tiktok_video"`, `"marketplace"`, `"whatsapp_catalog"`. String libre para poder agregar canales nuevos sin migración de BD.

3. **Modelo IA** → Haiku. El copy de marketing no requiere Sonnet y el usuario ya ve "✨ generando..." — latencia ~1s es aceptable. Si en producción se necesita más calidad, se sube a Sonnet con un flag de configuración.
