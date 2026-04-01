# Estado de Sesión Activa
_Actualizado: 2026-04-01_

## Módulo en trabajo
**VFP / SAR — Construcción de `configurar_allegra.scx` (PRÓXIMA SESIÓN)**

---

## PRÓXIMA SESIÓN — Construir `configurar_allegra.scx` en VFP IDE

### Spec completa en:
`docs/SPEC_FORM_CONFIGURAR_ALLEGRA.md` — incluye:
- Boceto ASCII del formulario al inicio
- Tabla de controles con nombres, posiciones y tamaños exactos
- Código completo de `Init` y `btn_guardar.Click` listo para copiar/pegar
- Verificaciones de migración de BD en el Init

### Lo que el formulario hace
- Lee/escribe `allegra_config.dbf` — **un registro por empresa (02 y LP)**
- Parámetros globales: `max_fact`, `intervalo`, `desde_ult` (aplican a ambas empresas)
- Por empresa: `num_inicio` (ej: PTV21200 para 02, PJP15780 para LP)
- Estado informativo (solo lectura): `ultima_sin`, `total_proc`, `ultimo_log` por empresa

### Pasos para construir el SCX en VFP IDE
1. `File → New → Form`
2. Poner propiedades del form (Caption, Width=500, Height=520, WindowType=1, AutoCenter=.T.)
3. Agregar controles según spec (sección por sección)
4. Pegar código en `Init` y `btn_guardar.Click` desde la spec
5. Guardar → `COMPILE FORM C:\S.A.R\PROYECTO\configurar_allegra.scx`
6. Probar: `DO FORM C:\S.A.R\PROYECTO\configurar_allegra`

### Verificación post-construcción
El `Init` ya incluye checks automáticos:
- Si DBF no existe → mensaje claro
- Si DBF sin campo `empresa` → mensaje: correr `allegra_sync.py` primero
- Si faltan registros 02 o LP → mensaje: idem
- Solo carga si todo está OK

---

## Trabajo sesión 2026-04-01 (continuación)

### Asistencia Remota — V1.1 y V1.2
- **Transferencia de archivos por chunks (512KB)** — sin límite de tamaño
- **Carpetas se zipean automáticamente** antes de transferir
- **Terminal remota** en el visor (`⌨️ Terminal`) — ejecuta comandos en PC del cliente
- **`exec` en el agente** — subprocess con timeout 60s, output a visor
- **Código de sesión aleatorio** visible en la ventana del agente (V1.2)
- **merlin_remote.py** en `C:\S.A.R\` — API local :7777 para que Merlin opere PCs remotas
- **gh CLI instalado** — releases via `'C:\Program Files\GitHub CLI\gh.exe' release create`
- Releases publicados: V1.1 y V1.2 en GitHub

### Pendientes asistencia remota
- Probar con PC de Pilar: Pilar descargó V1.2, pendiente prueba de conexión
- Configurar exe para que arranque automáticamente con Windows en PC de Pilar

## Trabajo sesión 2026-04-01

### Chat / Merlin
- `chat_bridge.py` y `git_bridge.py` **eliminados** — no se usan
- Flujo Rafael↔Merlin: `captura_watcher.ps1` → `__MERLIN__` → esta terminal (sin bridge intermedio)
- `chat_merlin_bridge.py` sigue vivo — para usuarios TUC TUC con Merlin como contacto
- Chulos ✓✓: color cambiado de azul (`#93c5fd`) a blanco (`#ffffff`) — visibles sobre globos azules

### Alegra — allegra_config.dbf ahora por empresa
- **Campo nuevo**: `empresa C(5)` — un registro por empresa (02 y LP)
- `num_inicio`, `ultima_sin`, `total_proc`, `ultimo_log` → por empresa
- `max_fact`, `intervalo`, `desde_ult` → globales (mismo valor en ambos registros)
- `allegra_sync.py` — `_migrar_config()` corre al inicio, migra automáticamente si estructura vieja
- `allegra_sync.py` — `leer_config()` retorna `por_empresa: {02: {...}, LP: {...}}`
- `allegra_sync.py` — `main()` usa `num_inicio` de cada empresa al filtrar facturas
- `instalar_allegra_bd.py` — crea 2 registros (02 y LP) al crear desde cero
- `docs/SPEC_FORM_CONFIGURAR_ALLEGRA.md` — actualizada con diseño por empresa + boceto + Init con verificaciones

### Docs y manuales
- Todos los manuales y specs van en `docs/` del proyecto TUC TUC (regla fija)
- `SPEC_FORM_CONFIGURAR_ALLEGRA.md` movida de `C:\S.A.R\PROYECTO\` a `docs/`

---

## Pendientes Alegra (después del SCX)
1. **Primera prueba real** con 1 factura sobre `basedatosempresas_TEST`
2. **Verificar REG_CTAS** después de prueba (débitos = créditos)
3. **Completar `tip_admin`** para invoice/creditNote en `alegra_tiposdoc.dbf` cuando aplique

## Pendientes chat /chat
- **Whisper tiny**: transcripción imprecisa en audios, considerar `small` para apuntes de Merlin

---

## Contexto técnico fijo
- bypassPermissions activo en `~/.claude/settings.json` ✓
- Rafael trabaja en Cali, Colombia — timezone America/Bogota
- App en producción: `tuc-tuc.onrender.com`
- BD Pilar: `C:\D\Pilar Peralta\basedatosempresas\`
- BD Pilar TEST: `C:\D\Pilar Peralta\basedatosempresas_TEST\`
- Flujo chat Rafael↔Merlin: `captura_watcher.ps1` → `__MERLIN__` → esta terminal
- Archivos Alegra en: `C:\S.A.R\` (Python) y `C:\S.A.R\PROYECTO\` (PRGs y SCX)
