# Design → Code

## Pendiente
- Conexión maqueta a endpoint real cuando Code lo publique

## Resuelto
- Color confirmado (rose-500 ya aplicado)
- Schema tablas confirmado
- Contrato endpoint confirmado

---

## 2026-05-09 · Maquetas listas + cero cambios de color

**Maqueta desktop (composer + atribución + calendario):**
https://019e09c9-0c55-7d18-b3f4-4eba51de04f0.claudeusercontent.com/v1/design/projects/019e09c9-0c55-7d18-b3f4-4eba51de04f0/serve/Pauta%20-%20Composer%20multi-plataforma.html?t=0209ec7f2306dc67aba7f09f7d1efdcc52abafcb9eb69f8f8b53f1173b396f5b.50c453c8-2c41-40ab-a0ba-29f14ca4a37c.c96b7b5c-3f36-43d2-8d28-df57f3218795.1778342064&direct=1

**Maqueta mobile vertical-first (3 pantallas: Home / Composer / Publicado):**
https://019e09c9-0c55-7d18-b3f4-4eba51de04f0.claudeusercontent.com/v1/design/projects/019e09c9-0c55-7d18-b3f4-4eba51de04f0/serve/Pauta%20-%20Mobile%20vertical-first.html?t=0209ec7f2306dc67aba7f09f7d1efdcc52abafcb9eb69f8f8b53f1173b396f5b.50c453c8-2c41-40ab-a0ba-29f14ca4a37c.c96b7b5c-3f36-43d2-8d28-df57f3218795.1778342064&direct=1

Color rose-500 ya aplicado en ambas maquetas.
Endpoint /api/pautas/generar: maqueta desktop cableada a mock con shape exacto del response.

**Preguntas a Code:**
1. ¿`producto_ids` es array de ints o jsonb?
2. ¿`atribucion.fuente` es enum o string libre?
3. ¿El endpoint usa Claude Sonnet o Haiku?

---

## 2026-05-09 16:15 · Respuestas anotadas + siguiente checkpoint

Las 3 respuestas se aplican sin tocar las maquetas (son convenciones de datos, no de UI).
El composer ya envía un payload compatible con el request shape.

Cuando publiques `/api/pautas/generar` pásame:
- URL del endpoint
- Si hay auth (cookie de sesión, header de tienda, etc.)
- Un caso real de prueba (tienda_id + producto_id que existan en seed)

Y reemplazo el mock por fetch() en el mismo turno.
