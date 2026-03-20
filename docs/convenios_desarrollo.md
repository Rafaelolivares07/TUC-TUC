# Convenios de Desarrollo — TUC TUC
**Documento vivo | Última actualización: 2026-03-20**

Reglas de UX y arquitectura que aplican a **todos los módulos** de la plataforma.
Antes de construir cualquier formulario o componente nuevo, revisar este documento.

---

## 1. Autocomplete en inputs que afectan tablas existentes

### La regla
Cualquier campo de texto que pueda tocar registros ya existentes en la BD
**debe tener una cuadrícula de resultados debajo** mientras el usuario escribe.

Aplica siempre a:
- Nombre de persona (busca en `terceros`)
- Teléfono (busca en `terceros`)
- Nombre de negocio (busca en `restaurantes`, `tiendas`, `negocios`)
- Cualquier otro campo que sea clave en una tabla con datos preexistentes

### Comportamiento
1. El usuario escribe → búsqueda `LIKE '%texto%'` (cualquier parte del contenido)
2. Cuadrícula aparece debajo del input con los primeros 8-10 resultados
3. Mínimo 2 caracteres para disparar la búsqueda, debounce ~280ms

### Navegación — PC
| Tecla | Acción |
|---|---|
| `↓` | Entra a la cuadrícula, primera fila queda resaltada |
| `↓` / `↑` | Navega entre filas |
| `Enter` | Selecciona la fila resaltada |
| `Escape` | Cierra la cuadrícula, foco vuelve al input |

### Navegación — Mobile
| Gesto | Acción |
|---|---|
| Tap en una fila | Selecciona |
| Tap fuera de la cuadrícula | Cierra |

### Orden de campos cuando hay persona + negocio
1. **Teléfono primero** — al salir del campo (blur) busca en `terceros`.
   Si encuentra: badge verde "✓ Ya registrado: [nombre]" + pre-llena el nombre.
2. **Nombre del dueño** — autocomplete contra `terceros`.
3. **Nombre del negocio** — autocomplete contra `restaurantes` / `tiendas`.

### Implementación de referencia
El helper `montarAC(inputEl, fetchFn, onSelect)` está implementado en
`vendedor_dashboard()` dentro de `1_medicamentos.py`. Reusar ese helper.

Las APIs de búsqueda ya existen:
- `GET /api/vendedor/buscar-tercero?tel=xxx` — busca exacto por teléfono
- `GET /api/vendedor/buscar-terceros?q=xxx` — LIKE por nombre
- `GET /api/vendedor/buscar-negocios?q=xxx` — LIKE en restaurantes + tiendas

---

## 2. Teléfono como identificador universal

En toda la plataforma, el teléfono es la identidad. No se usan códigos inventados.

- Si el teléfono ya existe en `terceros` → bienvenido de vuelta, actualizar nombre si cambió
- Si no existe → crear registro nuevo
- El teléfono siempre es el primer campo a validar en formularios de persona

---

## 3. Tablas universales — no crear variantes

Ver `MEMORY.md` → sección "Arquitectura de datos — decisiones estratégicas".

**Regla corta:** antes de crear una tabla nueva, verificar si `terceros`, `pedidos`,
`solicitudes_transporte` o `negocios` pueden absorber el caso.

---

## 4. Patrón de respuesta de APIs

Todas las APIs del proyecto responden:
```json
{ "ok": true/false, "error": "mensaje si ok=false", ...datos }
```

---

*Agregar nuevas convenciones aquí cuando surjan en sesiones de desarrollo.*
