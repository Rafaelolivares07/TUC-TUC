# Usage Tracker — Manual de Desarrollo
_Creado: 2026-03-25_

Sistema de monitoreo de uso de Claude Code (Merlin) para Rafael. Muestra en la barra de estado cuánto de la ventana de conversación y del límite semanal se ha consumido, sin depender de APIs externas.

---

## Archivos del sistema

Todos residen en `~/.claude/` (`C:/Users/RAFAEL OLIVARES/.claude/`):

| Archivo | Rol |
|---|---|
| `usage_hooks.py` | Hook: registra actividad en cada sesión y tool use |
| `usage_tracker.py` | StatusLine: imprime la línea de estado |
| `usage_data.json` | Datos acumulados (ventana + semana) |
| `settings.json` | Configura hooks y statusLine |

---

## Arquitectura

```
SessionStart  ──► usage_hooks.py session_start  ──► usage_data.json
PostToolUse   ──► usage_hooks.py tool_use        ──► usage_data.json
statusLine    ──► usage_tracker.py               ──► lee usage_data.json → imprime
```

### Qué mide

1. **Ventana de conversación** — Claude Code tiene un límite de contexto por conversación. El tracker estima cuánto tiempo queda hasta que se resetea, basado en `cal.window_hours`.
2. **Semana** — Acumula caracteres procesados desde el lunes. Sirve para ver el ritmo de uso semanal.

---

## usage_hooks.py

Llamado por los hooks de `settings.json`. Acepta dos comandos:

### `session_start`
- Rota la ventana si han pasado más de `cal.window_hours` horas desde `window.start`
- Rota la semana si el lunes actual es distinto al guardado
- No suma chars — solo gestiona la rotación de periodos

### `tool_use`
- Lee `stdin` (el payload del tool) y cuenta sus caracteres (mínimo 100)
- Suma a `window.tool_calls`, `window.chars`, `week.chars_total` y `week.daily[hoy]`

---

## usage_tracker.py

Genera una línea de texto para el `statusLine` de Claude Code. Formato:

```
💬🟢23% · reset 3h42m  |  📅🟢 ritmo 15k/día · 4d sem
```

### Bloque ventana (`💬`)
| Condición | Output |
|---|---|
| Ventana activa | `💬{icono}{pct}% · reset {tiempo_restante}` |
| Ventana expirada | `💬✅ ventana libre` |

### Bloque semana (`📅`)
| Condición | Output |
|---|---|
| Sin datos aún | `📅🟢 inicio sem · {días_restantes}` |
| Sin `week_limit_chars` (sin calibrar) | `📅{icono} ritmo {Nk}/día · {días_restantes} sem` |
| Con `week_limit_chars` (calibrado) | `📅{icono}{pct}% sem · agota {tiempo}` |

### Iconos de color
| Icono | Umbral |
|---|---|
| 🟢 | < 55% |
| 🟡 | 55–79% |
| 🔴 | ≥ 80% |

---

## usage_data.json — Estructura

```json
{
  "window": {
    "start": "2026-03-25T10:50:43.958357",  // ISO — inicio de la ventana actual
    "tool_calls": 10,                         // calls acumulados en la ventana
    "chars": 15383                            // chars acumulados en la ventana
  },
  "week": {
    "monday": "2026-03-23",                   // lunes de la semana actual (YYYY-MM-DD)
    "chars_total": 15383,                     // total semana
    "daily": {
      "2026-03-25": 15383                     // desglose por día
    }
  },
  "cal": {
    "window_hours": 5,                        // duración estimada de la ventana de contexto
    "week_limit_chars": null                  // null = sin calibrar; número = límite semanal calibrado
  }
}
```

---

## settings.json — Configuración relevante

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{"type": "command",
                 "command": "python \"C:/Users/RAFAEL OLIVARES/.claude/usage_hooks.py\" session_start"}]
    }],
    "PostToolUse": [{
      "hooks": [{"type": "command",
                 "command": "python \"C:/Users/RAFAEL OLIVARES/.claude/usage_hooks.py\" tool_use",
                 "async": true}]
    }]
  },
  "statusLine": {
    "type": "command",
    "command": "python \"C:/Users/RAFAEL OLIVARES/.claude/usage_tracker.py\""
  }
}
```

`PostToolUse` usa `async: true` para no bloquear la respuesta mientras escribe en disco.

---

## Calibración pendiente

Dos valores en `cal` deben ajustarse una vez observados:

### `window_hours`
- **Qué es**: cuántas horas dura la ventana de contexto de Claude Code antes de resetearse.
- **Cómo calibrar**: cuando Rafael vea el mensaje de "conversación comprimida" o el reset, anotar la hora. Calcular diferencia con `window.start` en `usage_data.json`. Actualizar `cal.window_hours` con ese valor.
- **Valor actual**: `5` (estimado)

### `week_limit_chars`
- **Qué es**: el límite semanal de caracteres (proxy del límite de uso de claude.ai).
- **Cómo calibrar**: cuando Rafael vea su porcentaje de uso semanal en `claude.ai/settings/usage`, decirle a Merlin el % y los chars acumulados ese día (`week.chars_total`). Con eso se calcula el límite total.
  - Fórmula: `week_limit_chars = chars_total / (pct_visto / 100)`
- **Valor actual**: `null` (sin calibrar — muestra ritmo en vez de porcentaje)

---

## Mantenimiento

- Los archivos `.py` y `.json` se editan directamente en `~/.claude/`
- No requieren reinicio de Claude Code salvo que se cambie `settings.json`
- Si `usage_data.json` se corrompe, borrarlo — se recrea solo en el próximo `session_start`
