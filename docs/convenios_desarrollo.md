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

**La regla en una línea:** ningún cambio de esquema puede requerir acción manual de Rafael.

---

### Por qué existe esta regla

El app corre en Render (Gunicorn). No hay `if __name__ == '__main__'` corriendo en producción.
No hay pipeline de migraciones (Alembic, Flyway, etc.). El único momento seguro para
aplicar un ALTER es **durante el request**, justo antes de usar la tabla.

---

### Patrón obligatorio: función `_asegurar_*` o `crear_tablas_*`

```python
def _asegurar_schema_chat(conn):
    """Garantiza columnas opcionales de mensajes. Llamar antes de cualquier
    operación sobre mensajes."""
    for sql in [
        "ALTER TABLE mensajes ADD COLUMN IF NOT EXISTS url_archivo TEXT",
        "ALTER TABLE mensajes ADD COLUMN IF NOT EXISTS conversacion_id INTEGER",
        "ALTER TABLE mensajes ADD COLUMN IF NOT EXISTS card_payload JSONB",
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass
```

**Reglas de la función:**
- Nombre: `_asegurar_schema_<modulo>(conn)` o `crear_tablas_<modulo>(conn)`
- Parámetro: siempre recibe `conn` (ya abierta por el endpoint)
- Cada ALTER en su propio try/except — un fallo no debe frenar los demás
- Usar siempre `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS`
- No lanzar excepciones hacia afuera — silenciar y seguir

**Llamarla siempre al inicio del endpoint, antes de cualquier query:**

```python
@app.route('/api/chat/invitado/mensajes/<token>')
def api_chat_invitado_mensajes(token):
    try:
        conn = get_db_connection()
        _asegurar_schema_chat(conn)   # ← PRIMERO, siempre
        # ... resto del endpoint
```

---

### Cuándo crear una función nueva vs. agregar a una existente

| Situación | Acción |
|---|---|
| Módulo nuevo con tabla propia | Crear `crear_tablas_<modulo>(conn)` |
| Columna nueva en tabla de módulo existente | Agregar el ALTER a la función existente del módulo |
| Columna en tabla compartida (`terceros`, `mensajes`, `pedidos`) | Agregar a `_asegurar_schema_<modulo>` del módulo que introduce el cambio |

---

### Funciones de aseguramiento existentes (referencia rápida)

| Función | Tabla(s) que cubre | Dónde se llama |
|---|---|---|
| `crear_tablas_contactos(conn)` | `contactos` | Todo endpoint `/api/vendedor/contactos/*` |
| `_asegurar_schema_chat(conn)` | `mensajes` (url_archivo, conversacion_id, card_payload) | `api_chat_invitado_mensajes`, `api_chat_invitado_enviar` |
| `_crear_tabla_citas_vendedor(conn)` | `citas_vendedor` | Todo endpoint `/api/vendedor/cita*` |
| `_crear_tabla_plantillas_crm(conn)` | `plantillas_crm`, `plantillas_crm_envios` | Todo endpoint `/api/vendedor/plantillas*` |

Cuando agregues una columna nueva, busca primero si ya existe la función del módulo
y agrega el ALTER ahí — no crees una función duplicada.

---

### Lo que NO hacer

```python
# ❌ MAL — endpoint manual que Rafael tiene que llamar
@app.route('/api/migrar-chat', methods=['GET'])
def migrar_chat():
    conn.execute("ALTER TABLE mensajes ADD COLUMN ...")

# ❌ MAL — comentario "acordarse de ejecutar"
# NOTA: antes de desplegar, correr ALTER TABLE mensajes ADD COLUMN card_payload JSONB

# ❌ MAL — dentro de if __name__ == '__main__' (no corre en Render/Gunicorn)
if __name__ == '__main__':
    conn.execute("ALTER TABLE ...")
    app.run(...)

# ❌ MAL — un solo try/except que engloba todos los ALTERs
# (si el primero falla, los demás no corren)
try:
    conn.execute("ALTER TABLE a ADD COLUMN x ...")
    conn.execute("ALTER TABLE b ADD COLUMN y ...")
except: pass
```

---

### Checklist al agregar cualquier columna o tabla nueva

- [ ] ¿Existe ya una función `_asegurar_*` / `crear_tablas_*` para este módulo?
  - Sí → agregar el ALTER ahí
  - No → crear la función con el patrón de arriba
- [ ] ¿La función se llama al inicio de **todos** los endpoints que usan esa tabla?
- [ ] ¿Cada ALTER tiene su propio try/except?
- [ ] ¿Se usó `IF NOT EXISTS`?
- [ ] ¿Se corrió `ast.parse` antes del push?

*Agregar nuevas convenciones aquí cuando surjan en sesiones de desarrollo.*
