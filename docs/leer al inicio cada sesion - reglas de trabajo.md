# Reglas de Trabajo — Claude + Rafael
_Actualizado: 2026-03-31_

Estas reglas se han definido a lo largo de sesiones anteriores. Aplicar siempre sin necesidad de que Rafael las repita.

---

## Comportamiento general

- **Nombre**: Rafael me llama "Merlin"

## Perfil de Rafael
- Pragmático — va al grano, no le gusta el ruido ni las respuestas infladas
- Metódico pero flexible — acumula cambios, piensa antes de ejecutar
- Le importa la calidad de la comunicación, no solo el resultado técnico
- Experimentado — no necesita explicaciones básicas ni contexto obvio
- Paciente para enseñar cuando considera que vale la pena
- Desarrollador full-stack con años de experiencia, tres proyectos activos en paralelo
- Trabaja en Cali, Colombia
- **Idioma**: siempre responder en español
- **Tono**: no hacer preguntas proactivas al final de cada respuesta ("¿seguimos con X?", "¿hay algo más?"). Responder y punto.
- **Permisos**: `bypassPermissions` activo globalmente en `~/.claude/settings.json` — no pedir confirmación para leer, editar ni ejecutar comandos
- **Commits**: pre-autorizados en TUC TUC. Hacer commit+push sin preguntar cuando Rafael indique que el trabajo está listo. Usar mensaje descriptivo del cambio.
- **Git push**: pre-autorizado siempre en este proyecto. No preguntar.
- **Acumulación de cambios**: Rafael prefiere acumular varios cambios antes de hacer commit. No proponer commit después de cada cambio pequeño — esperar a que Rafael lo indique.

---

## Reglas globales — leer siempre
El archivo principal de convenciones es **`convenios_desarrollo.md`** — aplica a todos los módulos:
1. Autocomplete en inputs que afectan tablas existentes (cuadrícula debajo, mín. 2 chars, debounce 280ms, navegable con ↑↓Enter/Escape)
2. Teléfono como identificador universal
3. No crear tablas nuevas si `terceros`, `pedidos`, `solicitudes_transporte` o `negocios` pueden absorber el caso
4. APIs siempre responden `{ "ok": true/false, "error": "...", ...datos }`
5. JS en templates Python: no escapar backticks (`\``), validar con `ast.parse` antes de push
6. Migraciones BD: patrón `_asegurar_*` / `crear_tablas_*` — nunca endpoints manuales ni `if __name__`
7. Timestamps: sesión PG en Bogotá, `ZoneInfo` en Python, reglas distintas para chat vs logs (ver §7)

## Reglas de UI — General

---

## Reglas de UI — Domótica

Definidas tras feedback directo (algunas rechazadas 2+ veces):

- **NO usar 2 columnas** en la grilla de switches del panel de control. Siempre `flex-col`, 1 columna, full-width. Fue rechazado dos veces — no volver a proponer.
- `.ctrl-icon { height: min(60vw, 220px) }` — el ícono debe llenar la card
- `.ctrl-nombre { font-size: .75rem; padding: 4px 8px 6px }` — título pequeño debajo del ícono
- Modal de detalle: `max-w-full` en ambas capas para no salirse en mobile

---

## Reglas de HTML general

- **Nunca anidar `<a>` dentro de `<a>`**, ni `<button>` dentro de `<a>`
- Para links secundarios dentro de una card-link usar `<span onclick>` o `<button onclick>` con `event.stopPropagation()`
- Motivo: Chrome "arregla" el HTML inválido creando elementos fantasma en el grid

### Scroll en `<select>` — bloquear siempre

Los `<select>` enfocados responden al scroll del mouse y cambian valor **silenciosamente**. Aplica en browsers (HTML) y en tkinter (ttk.Combobox). Bloquear siempre:

**HTML (Flask templates)** — en el template base o en cada página con selects:
```javascript
document.querySelectorAll('select').forEach(sel => {
    sel.addEventListener('wheel', e => { e.preventDefault(); }, { passive: false });
});
```

**Python / tkinter** — al crear cualquier `ttk.Combobox`:
```python
cmb.bind("<MouseWheel>", lambda e: "break")
cmb.bind("<Button-4>",   lambda e: "break")   # Linux scroll up
cmb.bind("<Button-5>",   lambda e: "break")   # Linux scroll down
```

Aplicar **siempre** al crear el widget/elemento, no como fix posterior. No dejar ningún Combobox o select sin este bloqueo.

---

## Reglas SAR — allegra_sync.py y configurar_allegra.py

### max_fact e intervalo NO controlan la descarga de Alegra

`max_fact` e `intervalo` son parámetros de `interfaz_allegra.py` — controlan cuántas facturas *procesa* Administrator por ciclo y cada cuánto corre el daemon.

**No tienen nada que ver con cuántas facturas descarga `allegra_sync.py`.**

`allegra_sync.py` siempre descarga **todas** las facturas nuevas (número > num_inicio de cada empresa) sin límite. El único freno del sync es `num_inicio` — cuando encuentra una factura con número ≤ num_inicio para de paginar.

**Nunca agregar un límite de max_fact al loop de descarga de allegra_sync.** Si el sync tarda mucho, el problema es la cantidad de facturas nuevas o la velocidad de la API, no un límite a configurar.

---

## Computer Use — MCP windows-mcp activo (desde 2026-04-09)

Claude Code tiene control GUI del PC de Rafael:
- **Screenshot**: capturar pantalla en cualquier momento
- **Mouse + teclado**: hacer clic, escribir, scroll, abrir apps
- **Implicación directa**: nunca pedir a Rafael que "abra la consola y diga qué ve", "copie el error", "describa el estado de la UI" — hacerlo directamente
- Para depurar JS: abrir DevTools con F12 + screenshot
- Para verificar un query: abrir pgAdmin/DBeaver y ver el resultado directamente
- Si el MCP no responde → pedir a Rafael que verifique con `/mcp`

---

## Reglas técnicas — Backend

- **Tuya region**: usar `openapi.tuyaeu.com` (Europa), no `openapi.tuyaus.com`
- **Timestamps en PostgreSQL**: la sesión PG usa `SET TIME ZONE 'America/Bogota'` → `CURRENT_TIMESTAMP` guarda hora Colombia (naive). Ver §7 de `convenios_desarrollo.md` para el convenio completo. Resumen:
  - Python: `ZoneInfo('America/Bogota')` → produce `-05:00`. **Nunca `timezone.utc`**.
  - Toda conexión (Flask y bridge) debe ejecutar `SET TIME ZONE 'America/Bogota'` al abrirse.
  - JS /chat: `toLocaleTimeString('es-CO')` **sin** `timeZone` forzado — el offset del servidor maneja la conversión para cualquier zona del usuario.
  - JS logs/domótica: `toLocaleString('es-CO', { timeZone: 'America/Bogota' })` — strings sin offset, pantallas internas Colombia.
- **Bluetooth puro**: el MOES BAT-80A ATS es Bluetooth puro — nunca intentar integrarlo sin gateway WiFi/Zigbee

---

## Al inicio de cada sesión

1. Leer este archivo
2. Leer `leer al inicio cada sesion - estado sesion activa.md`
3. Si hay cambios pendientes de commit mencionados ahí, tenerlos en cuenta antes de sugerir nuevos commits

---

## Regla de documentación — la memoria de Claude es del presente

La memoria interna de Claude (auto-memory) es efímera y orientada al momento actual. **No es confiable entre sesiones.**

**Los docs son la memoria permanente.** Todo lo que deba sobrevivir a un reinicio de sesión debe estar en `docs/`:

- Decisiones de arquitectura → `docs/vfp_administrator_pilar.md` u otro manual técnico
- Estado de trabajo → `docs/leer al inicio cada sesion - estado sesion activa.md`
- Reglas y convenciones → `docs/convenios_desarrollo.md` o este archivo

### Al terminar cualquier bloque de trabajo significativo:
- Documentar en el archivo técnico correspondiente: qué se creó, por qué, cómo funciona
- No asumir que "quedó en la memoria" — si no está en docs/, no existe para la próxima sesión
- Las memorias internas (`memory/`) son punteros a docs/, no fuente de verdad

### Qué documentar siempre:
- Archivos nuevos creados: propósito, ubicación, cómo se invoca
- Decisiones no obvias: por qué se hizo así y no de otra forma
- Workarounds técnicos: el problema que resuelven (ej: lector binario por .fpt huérfano)
- Comportamientos automáticos: qué crea/verifica/actualiza cada script al correr
