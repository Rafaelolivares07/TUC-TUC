# Sistema de Recordatorios de Medicamentos

Este documento explica cómo funciona el sistema completo de recordatorios de medicamentos vía Telegram.

## Arquitectura General

El sistema consta de 4 componentes principales:

1. **Base de datos** - Almacena configuración de recordatorios
2. **Frontend (UI)** - Interfaz para activar/desactivar recordatorios
3. **Backend (API)** - Endpoints para gestionar recordatorios
4. **Bot de Telegram** - Envía recordatorios y recibe confirmaciones

---

## 1. Base de Datos

### Tabla: `terceros`
- **Campo nuevo**: `telegram_chat_id` (TEXT)
- **Propósito**: Vincular cada usuario con su chat de Telegram

### Tabla: `pastillero_usuarios`
- **Campo nuevo**: `horas_entre_tomas` (INTEGER)
  - Cada cuántas horas debe tomar el medicamento (4, 6, 8, 12, 24)
- **Campo nuevo**: `proxima_toma` (TIMESTAMP)
  - Fecha y hora de la próxima toma programada
- **Campo nuevo**: `recordatorio_activo` (BOOLEAN)
  - Si el recordatorio está activo para este medicamento

### Índices creados
- `idx_terceros_telegram_chat_id` - Para búsquedas rápidas por chat_id
- `idx_pastillero_recordatorio_activo` - Para filtrar recordatorios activos
- `idx_pastillero_proxima_toma` - Para ordenar por próxima toma

---

## 2. Frontend (UI)

### Ubicación
- **Archivo**: `templates/tienda_home.html`
- **Sección**: Modal de Pastillero

### Elementos UI

#### Botón de Recordatorio
```html
<button class="btn-recordatorio ${activo ? 'activo' : ''}">
    ${activo ? '⏰ ON' : '⏰'}
</button>
```

- **Estado inactivo**: Botón gris con ícono ⏰
- **Estado activo**: Botón verde con texto "⏰ ON" y animación de pulso

#### Modal de Configuración
Cuando el usuario presiona el botón ⏰, se abre un modal con:

1. **Selector de frecuencia** - Botones para elegir cada cuántas horas (4h, 6h, 8h, 12h, 24h)
2. **Selector de próxima toma** - Campo `datetime-local` para elegir fecha/hora
3. **Alerta de vinculación** - Instrucciones para vincular Telegram si no está vinculado
4. **Botones de acción** - "Activar Recordatorio" o "Cancelar"

### Flujo del Usuario

1. Usuario presiona botón ⏰ en un medicamento
2. Se abre modal de configuración
3. Usuario selecciona frecuencia (ej: cada 8 horas)
4. Usuario elige próxima toma (ej: hoy a las 2:00 PM)
5. Si no tiene Telegram vinculado, ve instrucciones
6. Presiona "Activar Recordatorio"
7. El sistema guarda la configuración
8. El botón cambia a estado "⏰ ON" (verde con pulso)

---

## 3. Backend (API)

### Ubicación
- **Archivo**: `1_medicamentos.py`

### Endpoints

#### POST `/api/pastillero/<id>/activar-recordatorio`
Activa recordatorio para un medicamento.

**Request Body:**
```json
{
  "horas_entre_tomas": 8,
  "proxima_toma": "2025-12-23T14:00"
}
```

**Response:**
```json
{
  "ok": true,
  "mensaje": "Recordatorio activado"
}
```

**Lógica:**
1. Valida que el usuario esté autenticado
2. Valida que el medicamento pertenezca al usuario
3. Actualiza campos: `horas_entre_tomas`, `proxima_toma`, `recordatorio_activo = TRUE`
4. Retorna confirmación

---

#### POST `/api/pastillero/<id>/desactivar-recordatorio`
Desactiva recordatorio para un medicamento.

**Response:**
```json
{
  "ok": true,
  "mensaje": "Recordatorio desactivado"
}
```

**Lógica:**
1. Valida usuario y medicamento
2. Actualiza: `recordatorio_activo = FALSE`
3. Retorna confirmación

---

#### POST `/api/vincular-telegram`
Vincula un chat_id de Telegram con el usuario (endpoint legacy, no usado actualmente).

---

#### POST `/telegram/webhook`
**Recibe actualizaciones del bot de Telegram.**

Este es el endpoint que Telegram llama cuando:
- Un usuario envía un mensaje al bot
- Un usuario presiona un botón interactivo

**Tipos de updates recibidas:**

##### 1. Mensaje de texto (comando)
```json
{
  "message": {
    "chat": {"id": 123456},
    "text": "/vincular 3166686397"
  }
}
```

**Comandos soportados:**

**`/start`**
- Envía mensaje de bienvenida con instrucciones

**`/vincular TELEFONO`**
- Busca usuario por teléfono en la tabla `terceros`
- Si existe, guarda `chat_id` en `telegram_chat_id`
- Envía confirmación al usuario
- Si no existe, envía mensaje de error

**Ejemplo de vinculación:**
```
Usuario envía: /vincular 3166686397

Bot responde:
✅ ¡Vinculado correctamente!

Hola Rafael, ahora recibirás recordatorios de tus medicamentos.

Para activar recordatorios:
1. Abre tu pastillero en https://tuc-tuc.onrender.com
2. Presiona el botón ⏰ en el medicamento
3. Configura cada cuántas horas tomas el medicamento

¡Listo! Te enviaré recordatorios aquí en Telegram.
```

---

##### 2. Callback de botón (respuesta a recordatorio)
```json
{
  "callback_query": {
    "message": {
      "chat": {"id": 123456},
      "message_id": 789
    },
    "data": "tomar_42"
  }
}
```

**Callbacks soportados:**

**`tomar_<medicamento_id>`** - Usuario confirmó que tomó el medicamento
1. Busca usuario por `telegram_chat_id`
2. Busca medicamento en `pastillero_usuarios`
3. Resta 1 a la cantidad: `cantidad = cantidad - 1`
4. Calcula próxima toma: `proxima_toma = NOW() + horas_entre_tomas`
5. Actualiza la base de datos
6. Edita el mensaje para mostrar confirmación
7. **Si quedan ≤3 pastillas**: Agrega alerta con link a la tienda
8. **Si quedan 0 pastillas**: Agrega alerta urgente

**Ejemplo de respuesta:**
```
✅ Confirmado

Losartán 50mg

Quedan: 2 pastillas

⚠️ ¡Te quedan solo 2 pastillas!
¿Quieres hacer un pedido?
👉 https://tuc-tuc.onrender.com
```

**`cancelar_<medicamento_id>`** - Usuario canceló el recordatorio por hoy
1. No hace cambios en la base de datos
2. Solo edita el mensaje para confirmar cancelación

**Ejemplo de respuesta:**
```
❌ Recordatorio cancelado por hoy

Te recordaré en la próxima toma programada.
```

---

## 4. Bot de Telegram (APScheduler)

### Ubicación
- **Archivo**: `1_medicamentos.py`
- **Función**: `verificar_y_enviar_recordatorios()`

### Configuración del Scheduler

```python
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=verificar_y_enviar_recordatorios,
    trigger=IntervalTrigger(minutes=5),
    id='verificar_recordatorios',
    name='Verificar y enviar recordatorios de medicamentos',
    replace_existing=True
)
scheduler.start()
```

**Frecuencia**: Cada 5 minutos

---

### Lógica de Verificación

Cada 5 minutos, el scheduler ejecuta:

```sql
SELECT
    p.id,
    p.nombre,
    p.cantidad,
    p.horas_entre_tomas,
    p.proxima_toma,
    t.telegram_chat_id,
    t.nombre as usuario_nombre
FROM pastillero_usuarios p
INNER JOIN terceros t ON p.usuario_id = t.id
WHERE p.recordatorio_activo = TRUE
  AND p.proxima_toma IS NOT NULL
  AND p.proxima_toma <= NOW()
  AND t.telegram_chat_id IS NOT NULL
  AND t.telegram_chat_id != ''
```

**Condiciones:**
1. Recordatorio activo (`recordatorio_activo = TRUE`)
2. Tiene próxima toma configurada (`proxima_toma IS NOT NULL`)
3. Ya llegó la hora (`proxima_toma <= NOW()`)
4. Usuario tiene Telegram vinculado (`telegram_chat_id` no es NULL ni vacío)

---

### Envío de Recordatorio

Para cada medicamento pendiente:

1. **Construye el mensaje:**
```
⏰ Recordatorio de Medicamento

Hola Rafael, es hora de tomar:
Losartán 50mg

Quedan: 5 pastillas
Frecuencia: cada 8 horas
```

2. **Crea botones interactivos:**
```python
keyboard = {
    'inline_keyboard': [
        [
            {'text': '✓ Ya tomé', 'callback_data': 'tomar_42'},
            {'text': '❌ Cancelar hoy', 'callback_data': 'cancelar_42'}
        ]
    ]
}
```

3. **Envía mensaje vía API de Telegram:**
```python
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {
    'chat_id': chat_id,
    'text': mensaje,
    'parse_mode': 'HTML',
    'reply_markup': keyboard
}
requests.post(url, json=data)
```

4. **Actualiza próxima toma en DB:**
```python
nueva_proxima_toma = NOW() + timedelta(hours=horas_entre_tomas)
UPDATE pastillero_usuarios
SET proxima_toma = nueva_proxima_toma
WHERE id = medicamento_id
```

**Nota importante**: La próxima toma se actualiza **inmediatamente después de enviar el recordatorio**, no después de que el usuario confirme. Esto previene envíos duplicados.

---

## 5. Flujo Completo (Ejemplo Real)

### Paso 1: Usuario configura recordatorio

**Escenario:**
- Medicamento: Losartán 50mg
- Cantidad actual: 10 pastillas
- Frecuencia: Cada 8 horas
- Primera toma: Hoy a las 8:00 AM

**Acción del usuario:**
1. Abre pastillero en la web
2. Presiona botón ⏰ en Losartán
3. Selecciona "8h"
4. Elige próxima toma: "2025-12-23 08:00"
5. Presiona "Activar Recordatorio"

**Backend actualiza:**
```sql
UPDATE pastillero_usuarios SET
  horas_entre_tomas = 8,
  proxima_toma = '2025-12-23 08:00:00',
  recordatorio_activo = TRUE
WHERE id = 42
```

---

### Paso 2: Vinculación con Telegram

**Acción del usuario:**
1. Abre Telegram
2. Busca: `@TucTucMedicamentosBot`
3. Envía: `/vincular 3166686397`

**Bot verifica:**
```sql
SELECT id, nombre FROM terceros
WHERE telefono = '3166686397'
```

**Si encuentra el usuario:**
```sql
UPDATE terceros
SET telegram_chat_id = '123456789'
WHERE id = 5
```

**Bot responde:**
```
✅ ¡Vinculado correctamente!

Hola Rafael, ahora recibirás recordatorios...
```

---

### Paso 3: Primer recordatorio (8:00 AM)

**A las 8:05 AM** (scheduler ejecuta cada 5 min):

```sql
SELECT ... FROM pastillero_usuarios p
WHERE proxima_toma <= '2025-12-23 08:05:00'
-- Encuentra el Losartán
```

**Bot envía:**
```
⏰ Recordatorio de Medicamento

Hola Rafael, es hora de tomar:
Losartán 50mg

Quedan: 10 pastillas
Frecuencia: cada 8 horas

[Botón: ✓ Ya tomé] [Botón: ❌ Cancelar hoy]
```

**Bot actualiza:**
```sql
UPDATE pastillero_usuarios
SET proxima_toma = '2025-12-23 16:00:00'  -- 8 horas después
WHERE id = 42
```

---

### Paso 4: Usuario confirma que tomó el medicamento

**Usuario presiona:** `✓ Ya tomé`

**Telegram envía callback:**
```json
{
  "callback_query": {
    "data": "tomar_42",
    ...
  }
}
```

**Backend procesa:**
```sql
UPDATE pastillero_usuarios
SET cantidad = 9  -- 10 - 1
WHERE id = 42
```

**Bot edita el mensaje:**
```
✅ Confirmado

Losartán 50mg

Quedan: 9 pastillas
```

---

### Paso 5: Recordatorios subsecuentes

- **4:00 PM** (16:00): Envía recordatorio #2 → Próxima toma: 12:00 AM
- **12:00 AM** (00:00): Envía recordatorio #3 → Próxima toma: 8:00 AM
- **8:00 AM**: Envía recordatorio #4 → Próxima toma: 4:00 PM
- ...y así sucesivamente cada 8 horas

---

### Paso 6: Alerta de pocas pastillas

Después de 7 tomas, quedan 3 pastillas.

**Usuario presiona:** `✓ Ya tomé`

**Bot edita mensaje:**
```
✅ Confirmado

Losartán 50mg

Quedan: 2 pastillas

⚠️ ¡Te quedan solo 2 pastillas!
¿Quieres hacer un pedido?
👉 https://tuc-tuc.onrender.com
```

---

## 6. Configuración Inicial (Deployment)

### Script de migración
```bash
python ejecutar_migracion_recordatorios.py
```

Este script:
1. Conecta a PostgreSQL (producción)
2. Ejecuta `migracion_recordatorios.sql`
3. Verifica que las columnas se crearon correctamente

---

### Configurar webhook de Telegram
```bash
python configurar_webhook_telegram.py
```

Este script:
1. Elimina webhook anterior (si existe)
2. Configura nuevo webhook: `https://tuc-tuc.onrender.com/telegram/webhook`
3. Verifica configuración

**Importante**: Solo ejecutar UNA VEZ al hacer deploy inicial o cambiar URL.

---

## 7. Archivos Modificados/Creados

### Archivos nuevos:
- `migracion_recordatorios.sql` - Schema de BD
- `ejecutar_migracion_recordatorios.py` - Script de migración
- `configurar_webhook_telegram.py` - Configurar webhook
- `SISTEMA_RECORDATORIOS.md` - Esta documentación

### Archivos modificados:
- `1_medicamentos.py`:
  - Importar APScheduler
  - Función `verificar_y_enviar_recordatorios()`
  - Inicialización del scheduler
  - Endpoint `/telegram/webhook`
  - Funciones helper: `enviar_mensaje_telegram()`, `editar_mensaje_telegram()`, `responder_callback()`
  - Endpoints de API: `/api/pastillero/<id>/activar-recordatorio`, `/api/pastillero/<id>/desactivar-recordatorio`
  - Modificación de `/api/pastillero` para incluir campos de recordatorio

- `templates/tienda_home.html`:
  - Botón de recordatorio en tarjetas de medicamentos
  - Modal de configuración de recordatorios
  - Estilos CSS para botones y animaciones
  - Funciones JavaScript: `toggleRecordatorio()`, `mostrarModalRecordatorio()`, `guardarRecordatorio()`, etc.

- `requirements.txt`:
  - Agregado: `APScheduler==3.11.2`

---

## 8. Variables de Entorno

En `.env`:
```
DATABASE_URL=postgresql://...
TELEGRAM_BOT_TOKEN=8486881295:AAFjs-SU74er_shs4KnQYImMtyU5OTXycng
```

**Nota**: El token también está hardcodeado como fallback en el código.

---

## 9. Testing

### Test manual del webhook:
1. Enviar mensaje al bot: `/start`
2. Vincular teléfono: `/vincular 3166686397`
3. Configurar recordatorio en la web
4. Esperar 5 minutos para que el scheduler ejecute
5. Verificar que llegue el mensaje con botones
6. Presionar "✓ Ya tomé"
7. Verificar que se restó 1 pastilla en la web

---

## 10. Monitoreo y Logs

### Logs importantes:
```
[SCHEDULER] Verificando recordatorios pendientes...
[SCHEDULER] Encontrados 2 recordatorios pendientes
[OK] Recordatorio enviado: Losartán 50mg -> chat_id=123456
[SCHEDULER] Verificación de recordatorios completada
```

### Logs de webhook:
```
[TELEGRAM] Webhook recibido: {...}
[OK] Telegram vinculado: chat_id=123456 -> Rafael (tel: 3166686397)
[OK] Mensaje enviado a chat_id=123456
[OK] Mensaje editado: chat_id=123456, msg_id=789
```

---

## 11. Limitaciones y Consideraciones

1. **Frecuencia del scheduler**: 5 minutos
   - Los recordatorios no son exactos a la hora configurada
   - Pueden llegar hasta 5 minutos tarde

2. **Zona horaria**: Configurada a 'America/Bogota' en PostgreSQL

3. **Sin postponer**: No hay botón "Recordar en 30 min" (decisión del usuario)

4. **Próxima toma se actualiza al enviar**: No espera confirmación del usuario
   - Previene duplicados si el usuario no responde

5. **Alertas de pocas pastillas**: Se muestran solo cuando el usuario confirma toma
   - No se envían alertas automáticas sin interacción

---

## 12. Mejoras Futuras (No implementadas)

- [ ] Botón "Recordar en 30 minutos"
- [ ] Notificaciones proactivas cuando quedan ≤3 pastillas (sin esperar confirmación)
- [ ] Dashboard de estadísticas de adherencia
- [ ] Recordatorios recurrentes más precisos (cada minuto en vez de cada 5)
- [ ] Soporte para múltiples zonas horarias por usuario
- [ ] Historial de tomas en la web
- [ ] Gráficas de adherencia

---

## Resumen

Este sistema permite a los usuarios:
1. Configurar recordatorios de medicamentos desde la web
2. Vincular su cuenta con Telegram
3. Recibir recordatorios automáticos cada X horas
4. Confirmar tomas con un botón (resta automáticamente 1 pastilla)
5. Recibir alertas cuando quedan pocas pastillas
6. Cancelar recordatorios puntuales

**Tecnologías usadas:**
- Flask (Backend)
- PostgreSQL (Base de datos)
- APScheduler (Tareas programadas)
- Telegram Bot API (Mensajería)
- JavaScript (Frontend)

**Flujo simplificado:**
```
Usuario configura → Vincula Telegram → Scheduler verifica cada 5 min
→ Envía recordatorio con botones → Usuario confirma → Resta pastilla
→ Actualiza próxima toma → Ciclo se repite
```
