# Groq Agent (Llama 3.3 70B) — Manual de Desarrollo
_Creado: 2026-04-23_

## Propósito

`groq_agent.py` es un agente basado en Llama 3.3 70B via Groq API que actúa como ejecutor de tareas cuando Claude no está disponible, y como subordinado cuando Claude quiere delegar trabajo rutinario.

**Objetivo estratégico:** llevar el gasto de tokens de Claude a 0 en tareas mecánicas — lecturas, búsquedas, git, código boilerplate.

---

## Ubicación y configuración

- Archivo: `C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\groq_agent.py`
- API key: `GROQ_API_KEY` en `.env` (misma carpeta)
- Modelo: `llama-3.3-70b-versatile` (Groq, 14.400 req/día free, 500 tok/s)
- **No usa el SDK `groq`** — usa `requests` directo (el SDK cuelga en Python 3.14)

---

## Tres modos de uso

### 1. Servidor (`--server`) — modo principal
```bash
python groq_agent.py --server
```
- Levanta HTTP en `http://127.0.0.1:7778`
- Lanza el daemon de inbox en hilo de fondo
- Arranca automáticamente con Windows via `TucTuc_GroqAgent.vbs` (Startup folder)

### 2. Orquestación Claude → Llama (`--call`)
```bash
python groq_agent.py --call "tarea en lenguaje natural"
```
- Envía la tarea al servidor HTTP en :7778 usando Python (no curl — evita encoding issues de bash)
- Imprime la respuesta en stdout
- Claude lo usa así para delegar sin gastar sus propios tokens

### 3. Directo (sin servidor)
```bash
python groq_agent.py "tarea"
```
- Corre `_agente()` directamente, imprime resultado
- Útil para pruebas o cuando el servidor no está activo

---

## HTTP API (:7778)

| Método | Ruta | Body | Respuesta |
|---|---|---|---|
| POST | `/tarea` | `{"tarea": "..."}` | `{"ok": true, "respuesta": "..."}` |
| GET | `/estado` | — | `{"ok": true, "modelo": "llama-3.3-70b-versatile"}` |

---

## Herramientas disponibles (6)

El modelo usa etiquetas `<tool>` y `<input>` para invocar herramientas. Loop agentico de hasta 8 rondas.

| Herramienta | Descripción | Ejemplo de uso |
|---|---|---|
| `LEER_ARCHIVO` | Lee un archivo local (max 4000 chars) | Revisar código, configs |
| `ESCRIBIR_ARCHIVO` | Crea/sobreescribe archivo. 1ª línea=ruta, resto=contenido | Crear scripts, editar archivos simples |
| `EJECUTAR` | Corre comando bash/PowerShell | Ver logs, correr scripts, instalar paquetes |
| `GIT` | Corre git en TucTucV2 (`V2_DIR`) | status, log, diff, commit, push |
| `BUSCAR_WEB` | DuckDuckGo HTML — top 5 resultados, sin API key | Documentación, errores, ejemplos |
| `LEER_URL` | Descarga una URL y extrae texto plano | Leer docs oficiales, páginas específicas |

---

## Flujo agentico interno

```
_agente(tarea)
  │
  ├─ _llamar_groq(mensajes)  → Groq API → respuesta
  │
  ├─ ¿contiene <tool>?
  │   ├─ Sí → _ejecutar_herramienta(nombre, entrada)
  │   │        → agrega resultado como user msg
  │   │        → siguiente ronda (max 8)
  │   └─ No → respuesta final (limpiar etiquetas residuales)
```

---

## Daemon de inbox (fallback Rafael)

Cuando Rafael escribe desde el chat móvil y Claude no está disponible, el daemon actúa como fallback:

1. `merlin_daemon.py` detecta mensaje Rafael → escribe en `merlin_inbox.json`
2. Daemon de groq_agent (hilo de fondo en modo --server) detecta el inbox
3. Llama `_agente(tarea)` con el contenido
4. Escribe respuesta en `merlin_outbox.json`
5. `merlin_daemon.py` detecta el outbox → inserta en BD → Rafael ve la respuesta

---

## Arranque automático Windows

`TucTuc_GroqAgent.vbs` en `shell:startup`:
```vbscript
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & "C:\Python314\python.exe" & Chr(34) & " " & Chr(34) & "C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\groq_agent.py" & Chr(34) & " --server", 0, False
```
- `0` = sin ventana visible
- `False` = no bloquea el arranque de Windows

---

## Startup folder completo (2026-04-23)

| Archivo VBS | Proceso |
|---|---|
| `TucTuc_MerlinDaemon.vbs` | `merlin_daemon.py` — bridge Rafael↔Claude, heartbeat |
| `TucTuc_GroqAgent.vbs` | `groq_agent.py --server` — HTTP :7778 + inbox Llama |
| `monitor_tuctuc_b4e14ba7.vbs` | monitor heartbeat independiente |
| `AlegraDaemon.exe` | daemon Alegra VFP |
| `TUC TUC Arranque.lnk` | app Flask local |

---

## Qué tareas hace bien vs qué necesita Claude

### Llama (groq_agent) — autónomo
- Leer archivos y resumir / buscar cosas
- git status / log / diff / commit / push
- Ejecutar scripts y reportar output
- Endpoint CRUD simple (boilerplate)
- Preguntas técnicas (busca en web + lee la doc)
- Responder mensajes de Rafael cuando Claude no está

### Claude — intervención necesaria
- Decisiones de arquitectura
- Bugs sutiles (race conditions, sesiones, encoding)
- Refactors que tocan múltiples archivos con lógica compleja
- Código que requiere razonar sobre efectos secundarios en producción
- Contextos muy largos (Llama pierde el hilo)

---

## Cómo Claude orquesta a Llama

```bash
# Desde bash (Claude delega una tarea)
python groq_agent.py --call "Lee app/blueprints/crm.py y lista todas las rutas con método HTTP"

# Resultado viene en stdout — Claude lo lee y decide qué hacer con él
```

El patrón típico:
1. Claude recibe tarea compleja
2. Claude delega la parte de "recolectar info" a Llama via `--call`
3. Llama ejecuta (lee archivos, git, busca web)
4. Claude recibe el output y toma la decisión / escribe el código final
