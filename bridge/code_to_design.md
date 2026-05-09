# Code → Design

## Pendiente
- Maqueta con rose-500 aplicado
- URL de maqueta mobile vertical-first cuando esté lista

## Resuelto
- Color primario confirmado
- Schema de tablas confirmado
- Contrato JSON del endpoint confirmado

---

## 2026-05-09 15:30 · Color + Schema + Contrato endpoint

**Color primario — IMPORTANTE:** TUC TUC usa rose-500, no azul.
- Primario: `#f43f5e` (rose-500)
- Hover: `#e11d48` (rose-600)
- Fondos suaves: `#fff1f2` (rose-50)
- Resto del lenguaje visual (cards, sombras, Inter, rounded-2xl) perfecto.

**Tablas:**
```sql
pautas (id, tienda_id, hook, producto_ids, plataformas[], scheduled_at, status, presupuesto)
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
