# Referencia VFP para Merlin
_Creado: 2026-04-02 — acumulado de errores reales en sesiones con Rafael_

---

## 1. ON TIMER — comando legacy, problemático en .exe

### Sintaxis oficial
```foxpro
ON TIMER [nSeconds] [Command]
```

### Problemas conocidos
- **No acepta variables como nSeconds en .exe compilado** — causa "Error de sintaxis" en tiempo de compilación cuando el PRG es parte del proyecto.
- **No puede llamar procedimientos de otros PRGs** — al compilar el .exe, el compilador no encuentra el procedimiento si está en otro archivo fuente.
- **Sí funciona en modo desarrollo** (carga el .prg como .fxp externo, menos validación).

### Alternativa correcta para .exe: Timer control en un formulario abierto
Agregar un control Timer al formulario que queda como pantalla principal (ej: `fondo_menu_limpio.scx`):
- **Propiedades**: `Name = tmrAllegra`, `Interval = 0`, `Enabled = .F.` (el Init los setea dinámico)
- **Evento Init** del Timer: leer `allegra_config.dbf` → setear `ThisForm.tmrAllegra.Interval` y `.Enabled`
- **Evento Timer**: `DO C:\S.A.R\PROYECTO\alegra_timer.prg`
- El formulario queda abierto toda la sesión → el Timer vive toda la sesión.
- `Interval` en **milisegundos** (1 min = 60000).

Esta es la forma recomendada por la comunidad VFP. Evita todos los problemas de `ON TIMER`.

### Alternativa secundaria: Timer object en _SCREEN
```foxpro
**** En s.a.r.prg, ANTES de READ EVENTS:
LOCAL loT
loT = _SCREEN.AddObject("oAllegraTimer", "clsAllegraTimer")
loT.Interval = 60000   && milisegundos (60 seg)
loT.Enabled  = .T.

**** Al final de s.a.r.prg, como DEFINE CLASS:
DEFINE CLASS clsAllegraTimer AS Timer
    PROCEDURE Timer
        DO C:\S.A.R\PROYECTO\alegra_timer.prg
    ENDPROC
ENDDEFINE
```

- El objeto en `_SCREEN` persiste durante toda la sesión (READ EVENTS mantiene el loop).
- Funciona igual en desarrollo y en .exe compilado.
- `Interval` es en **milisegundos** (60 seg = 60000).
- En VFP, Interval, Enabled, Name etc. se llaman **propiedades** del control (no "valores por defecto").

---

## 2. Funciones que NO existen en VFP

| Lo que parece obvio | Lo correcto |
|---|---|
| `PADS()` | No existe. Usar `CNTPAD("_MSYSMENU")` para contar pads |
| `PAD(n)` | No existe como función standalone |
| `SHELL(cmd)` | No existe. Usar `RUN /N cmd` o ShellExecute via DECLARE |
| `EXECSCRIPT()` | Existe desde VFP 7, pero no resuelve procedimientos del .exe compilado |

---

## 3. STRTOFILE — llamar como statement requiere `=`

En VFP, las funciones que devuelven valor deben asignarse o usar `=` para descartar:

```foxpro
**** MAL — puede causar parse ambiguo en algunos contextos:
STRTOFILE("texto", "archivo.txt", .T.)

**** BIEN:
= STRTOFILE("texto", "archivo.txt", .T.)
```

El tercer parámetro `.T.` (append) existe desde VFP 8.

---

## 4. DEFINE CLASS — código ejecutable NO puede ir después de ENDDEFINE

En VFP, la estructura de un PRG debe ser:

```
[código principal ejecutable]    ← AQUÍ, antes de todo
DEFINE CLASS ... ENDDEFINE       ← clases
PROCEDURE ... ENDPROC            ← procedimientos
FUNCTION ... ENDFUNC             ← funciones
```

Código después de `ENDDEFINE` genera: **"La instrucción no está en un procedimiento"**.

Nota: el código principal SÍ puede referenciar clases/procedimientos definidos más abajo en el mismo archivo — VFP los registra antes de ejecutar el main body.

---

## 5. Encoding de archivos .prg VFP

- Los `.prg` usan **Windows-1252 (cp1252)** — pero pueden contener bytes que cp1252 no mapea (0x81, etc.).
- Usar siempre **`latin-1`** para leer/escribir con Python (mapea 1:1 todos los bytes 0x00-0xFF).
- **Nunca usar el Edit tool de Claude** para modificar `.prg` — corrompe ñ, acentos y otros chars.
- **Siempre usar Python con manipulación binaria** (leer como `latin-1`, modificar, escribir como `latin-1`).
- Los `.scx` / `.sct` son DBF/FPT binarios — tampoco editar como texto.

---

## 6. Scope de procedimientos en .exe compilado

- Un procedimiento definido en `s.a.r.prg` (el programa principal) está disponible **durante toda la sesión** gracias a `READ EVENTS`.
- Un procedimiento definido en un PRG externo (llamado con `DO archivo.prg`) **solo está disponible mientras ese PRG está en el call stack** — al retornar, desaparece.
- Para `ON TIMER` o eventos que disparan después de que el PRG retornó, el procedimiento debe estar en `s.a.r.prg` o en un objeto (Timer, Form) que persista en `_SCREEN`.

---

## 7. Macro substitución `&` en VFP

```foxpro
LOCAL lc_valor
lc_valor = "60"
ON TIMER &lc_valor DO mi_proc   && expande a: ON TIMER 60 DO mi_proc
```

- Solo funciona con **variables de tipo Character** — para numéricos, convertir con `LTRIM(STR(n))` primero.
- El compilador del .exe puede rechazarla en algunos contextos — preferir Timer object.

---

## 8. Rutas en código VFP

- Las rutas con `\a`, `\n`, `\t` etc. dentro de strings VFP **NO son secuencias de escape** — VFP no usa `\` como escape en strings.
- Pero Python SÍ interpreta `\a`, `\n` etc. — usar **raw strings** `r"C:\S.A.R\..."` o doble barra `"C:\\S.A.R\\"` al generar código VFP desde Python.

---

## 9. Compilación vs modo desarrollo

| Situación | Comportamiento |
|---|---|
| Modo desarrollo (`DO s.a.r.prg`) | PRGs externos se recompilan a `.fxp` si el `.prg` es más nuevo. Menos validación de referencias. |
| `.exe` compilado | El compilador valida referencias, scope de procedimientos, y es más estricto con sintaxis. Errores que no aparecen en desarrollo pueden aparecer en .exe. |
| PRGs en el proyecto VFP | Se compilan dentro del .exe — el compilador los ve todos. |
| PRGs externos (DO con ruta completa) | Se cargan como `.fxp` en runtime — el compilador del .exe NO los valida. |

**Regla**: siempre probar en .exe antes de considerar que algo funciona.

---

## 10. RUN — ejecutar programas externos desde VFP

```foxpro
RUN /N python "C:\S.A.R\script.py"   && /N = no esperar, sin ventana
RUN python "C:\S.A.R\script.py"      && espera a que termine
```

No devuelve código de retorno accesible directamente. Para capturar output usar redirección a archivo.
