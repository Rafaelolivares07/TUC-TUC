# CRM Vendedor — Documento de Desarrollo
**Última actualización: 2026-03-20**

---

## 1. Estado actual implementado

### URL
`/vendedor` — dashboard público, sin login obligatorio. El vendedor se identifica por su teléfono (input en la página).

### Módulos activos
- **Agenda de citas** — crear, ver, marcar como completada
- **Contactos** — lista personal, importar desde CSV/texto, buscar
- **Demo launcher** — situaciones predefinidas + lanzar WhatsApp con rol asignado
- **Plantillas CRM** — mensajes pregrabados, pool compartido entre todos los vendedores
- **Envío por WhatsApp** — modal con plantillas, detección app nativa vs web fallback

### Tablas de BD involucradas
| Tabla | Qué guarda |
|---|---|
| `contactos` | Lista de prospectos por vendedor (`tercero_id` del vendedor, `negocio_id`) |
| `plantillas_crm` | Mensajes pregrabados — pool compartido (sin filtro por vendedor) |
| `plantillas_crm_envios` | Log: qué plantilla, a quién, quién envió, cuándo |
| `citas_vendedor` | Agenda de citas del vendedor |

---

## 2. Decisiones de arquitectura acordadas

### 2.1 Identificador universal de negocio = `terceros.id`

Tanto personas como negocios son `terceros` — cada entidad tiene su propio `tercero_id` independiente.

```
Persona "Don Carlos"          → terceros.id = 5
Negocio "Restaurante El Rincón" → terceros.id = 42  ← entidad propia, no el dueño
```

El parámetro `n` en la URL apunta al `tercero_id` del **negocio como entidad**, no al de su dueño.

```
/vendedor?n=42   ← id del negocio-entidad en terceros
```

- TUC TUC central → `n=X` (tercero_id de TUC TUC como entidad)
- Restaurante El Rincón → `n=42`
- Tienda La Esquina → `n=Z`

### 2.2 Multi-tenancy por URL

Cada negocio que quiera tener sus propios vendedores recibe un link:
```
https://tuctuc.app/vendedor?n=42
```
El JS lee `n`, lo guarda como variable global, y lo pasa en todas las llamadas a API.

**Esto NO está implementado aún** — pendiente codear.

### 2.3 Contactos pertenecen al negocio, no al vendedor individual

Hoy: `contactos.tercero_id` = id del vendedor que importó el contacto.
Futuro: `contactos.negocio_id` = `tercero_id` del negocio → lista compartida entre todos los vendedores de ese negocio.

### 2.4 Plantillas — pool global + futuro por negocio

Hoy: todas las plantillas son visibles para todos (sin filtro).
Futuro: agregar `negocio_id` a `plantillas_crm` → cada negocio tiene sus propias plantillas, más las globales (negocio_id=NULL).

---

## 3. Cambios pendientes de implementar (en orden)

### Fase 1 — `?n=` en la URL (sin migrar datos)
1. Leer `n` del query string al cargar `/vendedor`
2. Guardar como `let _negocioId = null` (JS global)
3. Pasar `negocio_id` en todas las APIs: contactos, plantillas, envíos
4. Agregar columna `negocio_id` a `plantillas_crm_envios`

### Fase 2 — Historial de envíos por contacto
Al seleccionar un contacto, mostrar panel lateral con:
- Qué plantilla se usó
- Quién la envió (`terceros.nombre` del vendedor)
- Desde qué negocio (`terceros.nombre` del negocio)
- Cuándo

Query:
```sql
SELECT p.titulo, tv.nombre AS vendedor, tn.nombre AS negocio, e.created_at
FROM plantillas_crm_envios e
JOIN plantillas_crm p ON p.id = e.plantilla_id
JOIN terceros tv ON tv.id = e.vendedor_id
LEFT JOIN terceros tn ON tn.id = e.negocio_id
WHERE e.contacto_id = %s
ORDER BY e.created_at DESC
```

### Fase 3 — Migrar contactos a negocio_id real
Actualizar `contactos.negocio_id` con el `tercero_id` del dueño del negocio (en vez del vendedor individual).

---

## 4. WhatsApp — comportamiento implementado

| Contexto | URL usada |
|---|---|
| Móvil (cualquier OS) | `wa.me/NUM?text=MSG` |
| Desktop con app instalada | `whatsapp://send?phone=NUM&text=MSG` |
| Desktop sin app | `https://web.whatsapp.com/send?phone=NUM&text=MSG` |

Detección de app nativa: `visibilitychange` — si la página pierde foco en <1.5s → app abierta. Si permanece visible → fallback a web.

El fallback web reutiliza pestaña (`_wappWin`) cuando es posible (limitado por COOP headers de WhatsApp).

---

## 5. Modelo de comisión (referencia)

Ver `docs/estrategia_comercial.md` para detalle.
- Vendedor externo: 20% de cada recaudo, sin salario
- Vendedor interno: $2.7M/mes fijo, sin comisión
