# Módulo Contabilidad — Manual de Desarrollo

**Plataforma:** TUC TUC
**Archivo principal:** `1_medicamentos.py` (monolítico Flask + psycopg2)
**Última actualización:** 2026-03-12 (rev. métodos de pago)

---

## 1. Visión general

El módulo contabilidad de TUC TUC permite a cada negocio (tienda o restaurante) parametrizar sus propios asientos contables sin que el desarrollador tenga que intervenir. El motor genera comprobantes automáticamente cuando ocurren transacciones en los módulos operativos (ventas, compras, cobros).

El diseño es completamente **multi-tenant**: cada negocio tiene su propio plan de cuentas, sus propios tipos de documento y sus propias parametrizaciones. No hay datos contables compartidos entre negocios.

---

## 2. Esquema de base de datos

### 2.1 `cuentas_puc`
Plan Único de Cuentas colombiano. Pre-cargado en seed al primer arranque.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `codigo` | VARCHAR | Código PUC (ej: `1105`, `41`) |
| `nombre` | VARCHAR | Nombre de la cuenta |
| `nivel` | INT | 1=clase, 2=grupo, 3=cuenta, 4=subcuenta |
| `codigo_padre` | VARCHAR | Código del nivel superior |
| `naturaleza` | CHAR(1) | `D`=débito / `C`=crédito |
| `acepta_mov` | BOOLEAN | Solo las hojas aceptan movimientos |
| `terceros` | BOOLEAN | Requiere tercero en el movimiento |
| `documentos` | BOOLEAN | Requiere documento de soporte |

Función de seed: `_seed_puc(conn)` — solo carga si la tabla está vacía.

### 2.2 `cuentas_negocio`
Cuentas del PUC adoptadas por un negocio específico.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `negocio_id` | INT | FK al negocio |
| `tipo_negocio` | VARCHAR | `tienda` / `restaurante` |
| `puc_id` | INT | FK `cuentas_puc.id` |
| `alias` | VARCHAR | Nombre personalizado (opcional) |
| `activo` | BOOLEAN | |

### 2.3 `tipos_documento_negocio`
Tipos de documento contable que maneja un negocio. Los crea el usuario desde la UI.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `negocio_id` | INT | FK al negocio |
| `tipo_negocio` | VARCHAR | |
| `codigo` | VARCHAR | Código técnico (ej: `VENTA_POS`, `COMPRA`) |
| `nombre` | VARCHAR | Nombre descriptivo |
| `activo` | BOOLEAN | |

**UNIQUE:** `(negocio_id, codigo)`

**Códigos que usa el motor contable** (el negocio debe crearlos con exactamente estos códigos para que el motor los encuentre):

| Código | Módulo que lo dispara | Evento |
|---|---|---|
| `VENTA_POS` | Tienda — POS caja | Creación de pedido caja |
| `VENTA_DOM` | Tienda — domicilio/URL pública | Pedido marcado `estado='entregado'` |
| `COMPRA` | Tienda — inventario | Entrada de inventario guardada |
| `VENTA` | Restaurante | Cobro de mesa |

### 2.4 `parametros_contables_negocio`
Cabecera de parametrización: vincula un negocio con un tipo de documento.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `negocio_id` | INT | |
| `tipo_negocio` | VARCHAR | |
| `tipo_doc_id` | INT | FK `tipos_documento_negocio.id` |
| `descripcion_asiento` | VARCHAR | Texto que aparece en el comprobante |
| `activo` | BOOLEAN | Si está inactivo el motor lo ignora |

**UNIQUE:** `(negocio_id, tipo_doc_id)`

### 2.5 `parametros_lineas_contables`
Líneas de la parametrización. Cada línea define una cuenta + movimiento + cómo se obtiene el monto.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `parametro_id` | INT | FK cabecera |
| `cuenta_puc_id` | INT | Cuenta afectada |
| `tipo_mov` | CHAR(1) | `D`=Débito / `C`=Crédito |
| `origen` | CHAR(1) | `M` / `F` / `H` / `C` (ver abajo) |
| `valor_fijo` | NUMERIC(14,2) | Solo si `origen='F'` |
| `formula` | VARCHAR(100) | Solo si `origen='C'` (ej: `L1+L2`) |
| `variable_id` | INT | FK `modulo_variables_contables.id` — solo si `origen='H'` |
| `orden` | INT | Posición en el asiento (L1, L2, L3...) |
| `activo` | BOOLEAN | |

**Tipos de origen:**

| Código | Nombre | Cómo se resuelve el monto |
|---|---|---|
| `M` | Manual | No se genera automáticamente. El usuario lo completa a mano post-asiento. |
| `F` | Fijo | Usa el valor de `valor_fijo` directamente. |
| `H` | Heredado de fuente | Toma el valor del dict `variables` que el módulo pasó al motor, usando `variable_id` para saber cuál. |
| `C` | Calculado | Evalúa `formula` reemplazando `L1`, `L2`... por los montos ya resueltos en las posiciones anteriores. Ejemplo: `L1*0.19` calcula el 19% de la línea 1. |

### 2.6 `modulo_variables_contables`
Catálogo de variables disponibles por fuente. Pre-cargado en seed, gestionable desde `/admin/contabilidad/variables-modulos`.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `modulo` | VARCHAR | Nombre de la fuente (ej: `ventas_pos`) |
| `codigo` | VARCHAR | Identificador técnico (ej: `subtotal_venta`) |
| `descripcion` | VARCHAR | Texto legible para el usuario |
| `orden` | INT | Orden visual en la UI |
| `activo` | BOOLEAN | |

**UNIQUE:** `(modulo, codigo)`

**Fuentes pre-cargadas en seed:**

| Fuente (`modulo`) | Variables que expone |
|---|---|
| `ventas_pos` | `subtotal_venta`, `iva_venta`, `total_venta` + **variables de métodos de pago** (dinámicas) |
| `ventas_domicilio` | `subtotal_venta`, `iva_venta`, `total_venta` + **variables de métodos de pago** (dinámicas) |
| `compras_tienda` | `subtotal_compra`, `iva_compra`, `total_compra` |
| `ventas_restaurante` | `subtotal_venta`, `iva_venta`, `total_venta` |

**Variables de métodos de pago:** cuando un admin crea un método de pago en `metodos_pago_tienda`, la función `_upsert_var_metodo_pago(conn, codigo, nombre)` inserta automáticamente la variable en `modulo_variables_contables` bajo las fuentes `ventas_pos` y `ventas_domicilio`. Esto hace que aparezca disponible en el selector de variables de la parametrización sin acción adicional del desarrollador.

**Migración automática:** `_seed_variables_contables()` hace `DELETE WHERE modulo IN ('tienda','restaurante')` antes de insertar para limpiar los nombres genéricos anteriores.

### 2.7 `metodos_pago_tienda`
Métodos de pago configurados por el admin de una tienda.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `tienda_id` | INT | FK `tiendas.id` |
| `nombre` | VARCHAR(100) | Nombre visible al cajero (ej: `Nequi`) |
| `codigo` | VARCHAR(50) | Código técnico snake_case (ej: `nequi`) — es el nombre de la variable contable |
| `activo` | BOOLEAN | Solo los activos aparecen en el POS |
| `orden` | INT | Orden visual en el POS |

**UNIQUE:** `(tienda_id, codigo)`

> **Relación con contabilidad:** al crear un método, `_upsert_var_metodo_pago()` inserta su `codigo` como variable en `modulo_variables_contables` (fuentes `ventas_pos` y `ventas_domicilio`). Así el admin puede crear líneas de débito por método de pago en la parametrización.

### 2.8 `pedido_pagos_tienda`
Detalle de pagos de una venta POS. Un pedido puede tener N filas (pago mixto).

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `pedido_id` | INT | FK `pedidos_tienda.id` |
| `metodo_codigo` | VARCHAR(50) | Código del método (ej: `efectivo`) |
| `metodo_nombre` | VARCHAR(100) | Nombre legible |
| `monto` | NUMERIC(12,2) | Monto parcial pagado con este método |

Solo se insertan filas con `monto > 0`. El motor contable itera esta tabla para construir el dict `variables` con los montos por método.

### 2.9 `comprobantes_contables`
Cabecera de un comprobante generado (manual o automático).

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `negocio_id` | INT | |
| `numero_comprobante` | VARCHAR | Auto: `AUTO-VENTA_POS-0001` |
| `tipo` | VARCHAR | Código del tipo_doc |
| `fecha` | DATE | |
| `descripcion` | VARCHAR | |
| `total_debitos` | NUMERIC(14,2) | |
| `total_creditos` | NUMERIC(14,2) | |
| `registrado_por` | INT | tercero_id del usuario |
| `creado_en` | TIMESTAMP | |

### 2.10 `movimientos_contables`
Líneas del comprobante generado.

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | SERIAL PK | |
| `comprobante_id` | INT | FK cabecera |
| `cuenta_puc_id` | INT | |
| `tipo_mov` | VARCHAR | `debito` / `credito` |
| `monto` | NUMERIC(14,2) | Siempre positivo |
| `concepto` | VARCHAR | Nombre de la cuenta |
| `tercero_id` | INT | Opcional |

---

## 3. Motor contable: `_ejecutar_asiento_automatico()`

### Firma

```python
def _ejecutar_asiento_automatico(
    conn,
    negocio_id,
    tipo_negocio,
    tipo_doc_codigo,
    variables,
    registrado_por=None,
    fecha=None,
    descripcion_override=None
)
```

### Parámetros

| Parámetro | Tipo | Descripción |
|---|---|---|
| `conn` | psycopg2 connection | Conexión abierta. El motor NO hace commit ni cierra — responsabilidad del llamador. |
| `negocio_id` | int | ID del negocio |
| `tipo_negocio` | str | `'tienda'` / `'restaurante'` |
| `tipo_doc_codigo` | str | Código del tipo de documento (ej: `'VENTA_POS'`) |
| `variables` | dict | `{codigo_variable: valor_numerico}` expuesto por la fuente |
| `registrado_por` | int\|None | tercero_id del usuario que genera (opcional) |
| `fecha` | date\|None | Fecha del asiento (default: hoy) |
| `descripcion_override` | str\|None | Sobreescribe la descripción del parámetro |

### Retorna

`int` (comprobante_id) si se generó el asiento, `None` si no había parametrización activa o no se resolvió ningún monto.

### Algoritmo paso a paso

```
1. Busca tipos_documento_negocio WHERE negocio_id + codigo = tipo_doc_codigo
   → Si no existe: return None (negocio no configuró ese tipo)

2. Busca parametros_contables_negocio WHERE negocio_id + tipo_doc_id + activo=TRUE
   → Si no existe: return None (no hay parametrización activa)

3. Carga parametros_lineas_contables WHERE parametro_id + activo=TRUE ORDER BY orden

4. Itera líneas resolviendo monto por origen:
   - F → valor_fijo
   - H → variables[var_codigo]
   - C → eval(formula, sustituyendo L1..Ln por montos ya resueltos)
   - M → monto = 0, NO se agrega a movimientos

5. Filtra: solo líneas con monto != 0 y origen != 'M'

6. Si no quedan líneas: return None

7. Genera numero = AUTO-{tipo_doc_codigo}-{secuencial:04d}

8. INSERT comprobantes_contables RETURNING id

9. INSERT movimientos_contables (una fila por línea)

10. Retorna comprobante_id
```

### Seguridad del motor (best-effort)

**El motor NUNCA debe interrumpir la transacción principal.** Todo llamado se envuelve en `try/except Exception: pass`:

```python
if tipo_entrega == 'caja':
    try:
        _ejecutar_asiento_automatico(conn, tienda['id'], 'tienda', 'VENTA_POS', {...})
    except Exception:
        pass
```

Si el negocio no tiene parametrización, el motor retorna `None` silenciosamente. La venta/compra se registra igual.

---

## 4. Hooks del motor por módulo

### 4.1 Tienda — Venta POS (caja)

**Archivo:** `1_medicamentos.py` → función `api_tienda_pedido_crear`
**Condición:** `tipo_entrega == 'caja'`
**Momento:** Inmediatamente después del INSERT del pedido e INSERT de `pedido_pagos_tienda`, dentro del mismo bloque de conexión.

```python
# El POS envía pagos: [{codigo, nombre, monto}] — solo métodos con monto > 0
pagos_validos = [p for p in pagos if float(p.get('monto') or 0) > 0]

# Guardar detalle de pagos
for p in pagos_validos:
    conn.execute("""
        INSERT INTO pedido_pagos_tienda (pedido_id, metodo_codigo, metodo_nombre, monto)
        VALUES (%s, %s, %s, %s)
    """, (pedido_id, p['codigo'], p.get('nombre', p['codigo']), float(p['monto'])))

# Motor contable con variables de pago
if tipo_entrega == 'caja':
    try:
        vars_motor = {'subtotal_venta': subtotal_venta, 'iva_venta': iva_venta, 'total_venta': total}
        for p in pagos_validos:
            vars_motor[p['codigo']] = float(p['monto'])   # ej: vars_motor['efectivo'] = 60000
        _ejecutar_asiento_automatico(
            conn, tienda['id'], 'tienda', 'VENTA_POS',
            vars_motor,
            registrado_por=id_tercero_cajero or session.get('usuario_id'),
            descripcion_override=f'Venta caja #{pedido_id}'
        )
    except Exception:
        pass
```

**IVA:** Back-calculado desde `iva_pct` de cada producto. Los precios en BD se almacenan **con IVA incluido**, por tanto: `iva = precio × iva_pct / (100 + iva_pct)`.

**Pagos mixtos:** si la venta se paga con Efectivo $60.000 + Nequi $40.000, el motor recibe `{'total_venta': 100000, ..., 'efectivo': 60000, 'nequi': 40000}`. El admin puede crear una línea de débito `H → efectivo` (débito a Caja) y otra `H → nequi` (débito a Bancos). Solo se genera la línea si el monto es > 0 (regla del motor: líneas con `monto == 0` no se agregan al comprobante).

### 4.2 Tienda — Venta domicilio / URL pública

**Archivo:** `1_medicamentos.py` → función `api_tienda_pedido_estado`
**Condición:** `estado == 'entregado'` AND `pedido['tipo_entrega'] != 'caja'`
**Momento:** Cuando el admin marca el pedido como entregado.

```python
if estado == 'entregado':
    try:
        pedido = conn.execute(
            "SELECT total, tipo_entrega FROM pedidos_tienda WHERE id=%s AND tienda_id=%s",
            (pedido_id, tienda['id'])
        ).fetchone()
        if pedido and pedido['tipo_entrega'] != 'caja':
            items = conn.execute("""
                SELECT i.cantidad, i.precio_unitario, COALESCE(p.iva_pct, 0) AS iva_pct
                FROM items_pedido_tienda i
                LEFT JOIN productos_tienda p ON p.id = i.producto_id
                WHERE i.pedido_id = %s
            """, (pedido_id,)).fetchall()
            iva_ent = sum(
                r['precio_unitario'] * r['cantidad'] * r['iva_pct'] / (100 + r['iva_pct'])
                for r in items if r['iva_pct'] > 0
            )
            total_ent = float(pedido['total'] or 0)
            _ejecutar_asiento_automatico(
                conn, tienda['id'], 'tienda', 'VENTA_DOM',
                {'subtotal_venta': total_ent - iva_ent, 'iva_venta': iva_ent, 'total_venta': total_ent},
                descripcion_override=f'Entrega pedido #{pedido_id}'
            )
    except Exception:
        pass
```

### 4.3 Tienda — Compra / entrada de inventario

**Archivo:** `1_medicamentos.py` → función `api_tienda_entrada_inventario`
**tipo_doc_codigo:** `'COMPRA'`
**Variables:** `subtotal_compra`, `iva_compra`, `total_compra`

### 4.4 Restaurante — Cobro de mesa

**Archivo:** `1_medicamentos.py` → función de cobro de mesa
**tipo_doc_codigo:** `'VENTA'`
**Variables:** `subtotal_venta`, `iva_venta`, `total_venta`
**Nota:** actualmente `iva_venta=0` — pendiente calcular IVA desde `opciones_menu.iva_pct`.

---

## 5. Pantallas de administración

### 5.1 Panel de contabilidad del negocio — `/admin/contabilidad/<tipo>/<slug>`

Pantalla principal del módulo para el usuario con acceso al negocio. Contiene 4 pestañas:

**Pestaña: Plan de Cuentas**
- Muestra árbol del PUC colombiano adoptado por el negocio
- Acción: buscar cuentas del PUC y adoptarlas con un alias
- Backend: `GET /api/contabilidad/<tipo>/<slug>/cuentas` (cuentas adoptadas) + `GET /api/contabilidad/puc/buscar?q=` (buscador PUC)
- El buscador filtra solo `acepta_mov=TRUE`

**Pestaña: Tipos de Documento**
- Lista de tipos de documento del negocio (VENTA_POS, VENTA_DOM, COMPRA, VENTA, etc.)
- Acción: crear nuevo tipo con código + nombre; activar/inactivar
- Backend: `GET/POST /api/contabilidad/<tipo>/<slug>/tipos-documento`
- **El código que el usuario ingresa aquí DEBE coincidir con el que el motor busca.** Documentar esto al usuario.

**Pestaña: Parametrización**
- Lista de parametros (cabecera): tipo_doc + descripción_asiento + activo
- Al hacer clic en "Editar líneas" se abre un modal lateral con las líneas del asiento
- Dentro del modal se agregan líneas con: cuenta PUC, movimiento (D/C), origen, valor/fórmula/variable
- Backend:
  - `GET /api/contabilidad/<tipo>/<slug>/parametros` — cabeceras
  - `POST /api/contabilidad/<tipo>/<slug>/parametros` — crear cabecera
  - `GET /api/contabilidad/<tipo>/<slug>/parametros/<pid>/lineas` — líneas
  - `POST /api/contabilidad/<tipo>/<slug>/parametros/<pid>/lineas` — agregar línea
  - `DELETE /api/contabilidad/<tipo>/<slug>/parametros/<pid>/lineas/<lid>` — eliminar línea
  - `PATCH /api/contabilidad/<tipo>/<slug>/parametros/<pid>` — activar/inactivar cabecera

**Pestaña: Comprobantes**
- Lista de comprobantes generados (manuales y automáticos)
- Filtro por fecha y tipo

### 5.2 Métodos de Pago — `/admin/tienda/<slug>/metodos-pago`

Pantalla del admin para gestionar los métodos de pago de una tienda. Accesible desde el tab **"💳 Métodos de Pago"** en `tienda_admin.html`.

**Campos al crear:**
- `nombre` — texto visible al cajero (ej: `Nequi`)
- `codigo` — código técnico snake_case (ej: `nequi`) — se convierte automáticamente a minúsculas y reemplaza espacios por `_`
- `orden` — posición en el POS (0 = primero)

**Al guardar:** `_upsert_var_metodo_pago(conn, codigo, nombre)` registra la variable en `modulo_variables_contables` para fuentes `ventas_pos` y `ventas_domicilio`.

**Helper:**
```python
def _upsert_var_metodo_pago(conn, codigo, nombre):
    for modulo in ('ventas_pos', 'ventas_domicilio'):
        conn.execute("""
            INSERT INTO modulo_variables_contables (modulo, codigo, descripcion, orden, activo)
            VALUES (%s, %s, %s, 99, TRUE)
            ON CONFLICT (modulo, codigo) DO UPDATE SET descripcion = EXCLUDED.descripcion
        """, (modulo, codigo, f'Pago con {nombre}'))
```

**API:**
- `GET /api/admin/tienda/<slug>/metodos-pago` — lista
- `POST /api/admin/tienda/<slug>/metodos-pago` — crear
- `PATCH /api/admin/tienda/<slug>/metodos-pago/<id>` — actualizar `activo`, `orden`, `nombre`
- `DELETE /api/admin/tienda/<slug>/metodos-pago/<id>` — eliminar
- `GET /api/tienda/<slug>/metodos-pago` — **público**, usa el POS al autenticar el cajero

### 5.3 Variables de fuentes — `/admin/contabilidad/variables-modulos`

Pantalla exclusiva del **admin TUC TUC** (no del usuario del negocio).

- Lista todas las variables registradas, agrupadas por fuente
- Muestra: fuente (badge indigo), código técnico, descripción, estado activo/inactivo
- Acciones: agregar variable manual, activar/inactivar, eliminar
- **Las variables del sistema están pre-cargadas** en seed — el admin TUC TUC solo necesita verificarlas, no crearlas desde cero
- Backend: `GET/POST /api/admin/contabilidad/variables-modulos`; `PATCH/DELETE /api/admin/contabilidad/variables-modulos/<id>`

---

## 6. Validación de fuente única por parámetro (module locking)

### Regla de negocio
Dentro de un parámetro contable, todas las líneas de tipo `H` (Heredado de fuente) deben usar variables de **la misma fuente**. No se puede mezclar `ventas_pos` con `ventas_domicilio` en el mismo parámetro.

**Razón:** un parámetro lo dispara un único evento. Si se mezclan fuentes, el motor solo recibiría las variables de una de ellas al momento de ejecutarse, dejando las otras en cero y generando un asiento incorrecto.

### Implementación doble (frontend + backend)

**Frontend** (`contabilidad_admin.html`):
```javascript
let paramModuloLocked = null;  // fuente bloqueada para el param activo

// Al abrir el modal de edición de líneas:
paramModuloLocked = null;

// Al cargar líneas existentes:
const lineaH = lineas.find(l => l.origen === 'H' && l.variable_modulo);
paramModuloLocked = lineaH ? lineaH.variable_modulo : null;

// Al renderizar el dropdown de variables:
const variablesDisp = paramModuloLocked
    ? variablesData.filter(v => v.modulo === paramModuloLocked)
    : variablesData;
```

**Backend** (`api_contabilidad_parametro_lineas_post`):
```python
if origen == 'H' and variable_id:
    nueva_var = conn.execute(
        "SELECT modulo FROM modulo_variables_contables WHERE id=%s", (variable_id,)
    ).fetchone()
    if nueva_var:
        conflicto = conn.execute("""
            SELECT v.modulo FROM parametros_lineas_contables l
            JOIN modulo_variables_contables v ON v.id = l.variable_id
            WHERE l.parametro_id=%s AND l.origen='H' AND l.activo=TRUE AND v.modulo!=%s
            LIMIT 1
        """, (pid, nueva_var['modulo'])).fetchone()
        if conflicto:
            return jsonify({'ok': False, 'error': f"Este parámetro ya usa variables de '{conflicto['modulo']}'..."}), 400
```

---

## 7. IVA por producto — módulo Tienda

### Campo en BD
`productos_tienda.iva_pct` — `NUMERIC(5,2)` — porcentaje de IVA incluido en el precio (0, 5, 19, o cualquier valor).

### Cálculo back-calculation
Los precios en BD se almacenan **con IVA incluido**. Para extraer el IVA:

```
iva = precio_con_iva × iva_pct / (100 + iva_pct)
subtotal = precio_con_iva - iva
```

Ejemplo: precio $11.900, IVA 19% → iva = $11.900 × 19 / 119 = $1.900 → subtotal = $10.000

### API de productos
`GET /api/tienda/<slug>/productos` — ahora incluye `iva_pct` en cada producto del JSON de respuesta.

### POS caja (`tienda_caja.html`)
- `carrito` almacena `iva_pct` por item
- `renderCarrito()` muestra "IVA incluido: $X" cuando aplica
- `cobrar()` calcula `iva` y `subtotal` en `ultimoRecibo`
- `mostrarRecibo()` muestra subtotal + IVA + total
- `imprimirTicket()` incluye líneas Subtotal/IVA antes de TOTAL
- `compartirWhatsApp()` incluye desglose de IVA en el texto

### Admin tienda (`tienda_admin.html`)
- Selector IVA con opciones fijas (0%, 5%, 19%) + "Otro %" (input libre)
- Funciones JS: `toggleIvaCustom()`, `getIvaPct()`
- Al editar un producto, restaura el selector al valor guardado (o "Otro" si no es 0/5/19)

---

## 8. Inicialización del módulo

La función `crear_tablas_contabilidad(conn)` crea todas las tablas, índices y constraints del módulo. Se llama automáticamente en la primera solicitud que llegue a cualquier ruta del módulo, protegida por la variable global `_contabilidad_tablas_listas`.

Al finalizar la creación de tablas:
1. Llama `_seed_puc(conn)` — carga PUC colombiano si la tabla está vacía
2. Llama `_seed_variables_contables(conn)` — migra y re-carga variables de fuentes

La ejecución posterior al primer arranque es `O(1)`: el flag `_contabilidad_tablas_listas = True` evita re-ejecutar la función.

---

## 9. Decisiones de diseño

| Decisión | Razón |
|---|---|
| Motor best-effort (`try/except pass`) | Un error en la parametrización nunca debe bloquear una venta real. |
| UNIQUE(negocio_id, tipo_doc_id) en parametros | Un evento → un asiento → una parametrización. Sin ambigüedad. |
| POS dispara en creación, domicilio en entrega | En caja el dinero entra al instante. En domicilio la venta solo se confirma al entregar. |
| Fuentes separadas por canal | Permite parametrizaciones diferentes para POS y domicilio del mismo negocio, y evita mezclar variables de eventos distintos. |
| `DELETE` al seed de variables (no DO NOTHING puro) | Permite renombrar fuentes en el código sin dejar entradas huérfanas en BD. |
| `eval()` para fórmulas contables | Las fórmulas son strings simples del tipo `L1+L2` o `L1*0.19`. Se evalúan con `__builtins__: {}` para bloquear ejecución arbitraria. |

---

## 10. Pendientes de desarrollo

- [ ] IVA restaurante: calcular `iva_venta` real desde `opciones_menu.iva_pct` al cobrar mesa (actualmente se pasa `iva_venta=0`)
- [ ] Libro diario: vista resumen por rango de fechas para el dueño/contador
- [ ] Balance: activos vs pasivos calculados desde `movimientos_contables`
- [ ] Selector IVA en `restaurante_admin.html` — items de carta (mismo patrón que tienda_admin)
- [ ] Métodos de pago para domicilio y restaurante — hoy implementado solo en POS caja; los otros canales reciben `metodo_pago` como string simple sin desglose multi-pago
