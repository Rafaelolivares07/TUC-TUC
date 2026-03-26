# Convenios de Desarrollo — TUC TUC
**Documento vivo | Última actualización: 2026-03-20 (rev. bugs JS)**

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

## 5. JavaScript en templates Python — reglas de escritura

### El problema
El HTML del proyecto se genera con `render_template_string` en Python. El código JS
queda dentro de un string Python (`"""..."""`). Python interpreta las secuencias de
escape, lo que puede romper silenciosamente el JS renderizado.

### Reglas

**5.1 — Backticks en template literals JS**

Nunca escribir `\`` en el string Python. El backtick no necesita escape en Python.

```python
# MAL — Python renderiza \` (2 chars), JS falla con "Invalid or unexpected token"
div.innerHTML = \`...contenido...\`;

# BIEN — backtick directo
div.innerHTML = `...contenido...`;
```

**5.2 — Expresiones `${}` dentro de template literals JS**

Dentro de un template literal, `\${...}` escapa la interpolación (la convierte en
texto literal). En Python string, `\$` no es una secuencia reconocida, pero Python
mantiene ambos caracteres (`\$`), lo que en JS dentro del template literal ES válido.

```python
# Esto sí funciona (dentro de un template literal activo):
div.innerHTML = `<span onclick="fn(\${JSON.stringify(obj)})">${nombre}</span>`;
```

**5.3 — Validar antes de hacer push**

Después de cualquier modificación al template del vendedor (o cualquier otro
`render_template_string`), correr:

```bash
python -W error -c "import ast; ast.parse(open('1_medicamentos.py').read())"
```

Si hay escapes inválidos, falla con `SyntaxWarning` antes de llegar a Render.

---

## 6. Migraciones de BD — patrón obligatorio

Nunca depender de que el usuario llame un endpoint manualmente para aplicar un cambio en esquema.

### Regla
Toda columna o tabla nueva debe garantizarse automáticamente mediante una función
`_asegurar_*` o `crear_tablas_*` que use `ADD COLUMN IF NOT EXISTS` y sea llamada
**al inicio de cada endpoint que usa esa tabla**.

### Ejemplo de referencia
```python
def _asegurar_schema_chat(conn):
    for sql in [
        "ALTER TABLE mensajes ADD COLUMN IF NOT EXISTS card_payload JSONB",
    ]:
        try:
            conn.execute(sql); conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass

def api_chat_invitado_mensajes(token):
    conn = get_db_connection()
    _asegurar_schema_chat(conn)   # ← siempre primero
    ...
```

### Lo que NO hacer
- Endpoint `GET /api/migrar-algo` que Rafael tiene que llamar manualmente
- Comentario "ejecutar antes de desplegar"
- Migración dentro de `if __name__ == '__main__'` (no corre en Render/Gunicorn)

*Agregar nuevas convenciones aquí cuando surjan en sesiones de desarrollo.*
