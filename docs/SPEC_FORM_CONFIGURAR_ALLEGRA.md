# Especificación — Formulario configurar_allegra.scx
## Sistema Administrator SAR — Módulo Alegra

_Autor: Rafael / Claude — 2026-03-31 (actualizado 2026-04-01)_

---

## Vista previa del formulario

```
┌──────────────────────────────────────────────────────┐
│       Allegra — Configuración y Sincronización       │
│   Configure los parámetros de sincronización         │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Máximo de facturas por lote:        [  50  ]        │
│                                                      │
│  Intervalo automático (min, 0=manual):  [  0  ]      │
│                                                      │
│  Solo desde última sincronización:   [✓]             │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Empresa 02 — Última factura ingresada:              │
│                              [ PTV21200        ]     │
│  Empresa LP — Última factura ingresada:              │
│                              [ PJP15780        ]     │
│                                                      │
│  Ej: 02=PTV21200 LP=PJP15780 — procesará desde       │
│  el siguiente número en cada empresa                 │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Empresa 02 — Última sync:   01/04/2026 08:32:15     │
│  Empresa 02 — Total procesadas:   1.248 facturas     │
│  Empresa LP — Última sync:   01/04/2026 08:32:15     │
│  Empresa LP — Total procesadas:     432 facturas     │
│                                                      │
│  Último proceso:                                     │
│  ┌────────────────────────────────────────────────┐  │
│  │ 2026-04-01 08:32 — 3 facturas procesadas OK    │  │
│  │ PTV21201, PTV21202, PTV21203                   │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
├──────────────────────────────────────────────────────┤
│  [ Guardar ]  [ Sincronizar ahora ]      [ Cerrar ]  │
└──────────────────────────────────────────────────────┘
```

**Zonas del formulario:**
1. **Título** — nombre del módulo
2. **Parámetros globales** — aplican a las dos empresas (max_fact, intervalo, desde_ult)
3. **Número de inicio por empresa** — 02 y LP tienen prefijos distintos (PTV / PJP)
4. **Estado informativo** — solo lectura: última sync y total por empresa + log
5. **Botones** — Guardar / Sincronizar ahora / Cerrar

---

## Propósito

Formulario modal de configuración del módulo Alegra.
Se abre desde el menú **Allegra → Configurar / Sincronizar**.
Lee y escribe en `allegra_config.dbf` (ruta dinámica via `alegra_get_bd.prg`).

---

## Tabla que lee/escribe: `allegra_config.dbf`

**Un registro por empresa** (`empresa = "02"` y `empresa = "LP"`).

| Campo | Tipo | Por empresa | Descripción |
|---|---|---|---|
| `empresa` | C(5) | ✅ | Código empresa (02 / LP) |
| `max_fact` | N(5,0) | — global | Máximo de facturas por lote |
| `intervalo` | N(3,0) | — global | Intervalo automático en **minutos** (0 = solo manual) |
| `desde_ult` | L | — global | Solo trae facturas desde la última sincronización |
| `num_inicio` | C(20) | ✅ | Último número de factura Alegra ya ingresado en Administrator para esta empresa |
| `ultima_sin` | T | ✅ | Fecha/hora de la última sincronización — **solo lectura** |
| `total_proc` | N(10,0) | ✅ | Total de facturas procesadas históricas — **solo lectura** |
| `ultimo_log` | M | ✅ | Log del último proceso — **solo lectura** |

Los campos globales (max_fact, intervalo, desde_ult) se leen del registro de empresa "02" y se escriben en ambos registros al guardar.

---

## Propiedades del formulario

| Propiedad | Valor |
|---|---|
| `Caption` | "Allegra — Configuración y Sincronización" |
| `Width` | 500 |
| `Height` | 520 |
| `AutoCenter` | .T. |
| `WindowType` | 1 (modal) |
| `MaxButton` | .F. |
| `MinButton` | .F. |
| `BorderStyle` | 2 |
| `Name` | frm_configurar_allegra |

---

## Controles

### Sección 1 — Título

| Control | Tipo | Caption / Value | Left | Top | Width | Height |
|---|---|---|---|---|---|---|
| `lbl_titulo` | Label | "Interfaz Alegra — Administrator" | 10 | 10 | 480 | 24 |
| `lbl_subtitulo` | Label | "Configure los parámetros de sincronización" | 10 | 34 | 480 | 18 |

`lbl_titulo`: FontSize=12, FontBold=.T., ForeColor=RGB(0,70,140), Alignment=2

---

### Sección 2 — Parámetros globales

| # | Label (Caption) | Control | Tipo | Left | Top | Width |
|---|---|---|---|---|---|---|
| 1 | "Máximo de facturas por lote:" | `txt_max_fact` | Textbox | 220 | 70 | 60 |
| 2 | "Intervalo automático (min, 0=manual):" | `txt_intervalo` | Textbox | 220 | 100 | 60 |
| 3 | "Solo desde última sincronización:" | `chk_desde_ult` | Checkbox | 220 | 130 | 20 |

- `txt_max_fact` y `txt_intervalo`: `Format = "9"` (solo numérico)
- `chk_desde_ult`: Caption = "" (el label va a la izquierda)
- Todos los labels: Left=10, Width=200, Height=18, Alignment=1 (derecha)

---

### Sección 3 — Última factura por empresa

Separador visual (Shape o línea). Top=155.

| # | Label (Caption) | Control | Left | Top | Width |
|---|---|---|---|---|---|
| 1 | "Empresa 02 — Última factura ingresada:" | `txt_num_inicio_02` | 220 | 170 | 150 |
| 2 | "Empresa LP — Última factura ingresada:" | `txt_num_inicio_lp` | 220 | 200 | 150 |

- Ambos: `InputMask = "XXXXXXXXXXXXXXXXXXXX"` (20 chars alfanumérico)
- Labels: Left=10, Width=200, Height=18, Alignment=1

**Texto de ayuda:**

| Control | Caption | Left | Top | Width |
|---|---|---|---|---|
| `lbl_ayuda_inicio` | Label | "Ej: 02=PTV21200 LP=PJP15780 — el sistema procesará desde el siguiente" | 10 | 222 | 480 |

`lbl_ayuda_inicio`: FontSize=8, ForeColor=RGB(120,120,120), FontItalic=.T.

---

### Sección 4 — Estado por empresa (solo lectura)

Separador visual. Top=245.

| Label | Control | Left | Top | Width |
|---|---|---|---|---|
| "Empresa 02 — Última sync:" | `lbl_ultima_sin_02` | 220 | 260 | 260 |
| "Empresa 02 — Total procesadas:" | `lbl_total_proc_02` | 220 | 278 | 260 |
| "Empresa LP — Última sync:" | `lbl_ultima_sin_lp` | 220 | 298 | 260 |
| "Empresa LP — Total procesadas:" | `lbl_total_proc_lp` | 220 | 316 | 260 |

Labels: Left=10, Width=200, Height=16, Alignment=1. Se llenan en `Init`.

**Log del último proceso:**

| Control | Tipo | Left | Top | Width | Height |
|---|---|---|---|---|---|
| `lbl_log_titulo` | Label "Último proceso:" | 10 | 338 | 100 | 18 |
| `edt_ultimo_log` | Editbox | 10 | 356 | 480 | 70 |

`edt_ultimo_log`: ReadOnly=.T., ScrollBars=2, BackColor=RGB(240,240,240)

---

### Sección 5 — Botones

| Control | Caption | Left | Top | Width | Height | Acción |
|---|---|---|---|---|---|---|
| `btn_guardar` | "Guardar" | 10 | 455 | 100 | 27 | Guarda en allegra_config.dbf |
| `btn_sync` | "Sincronizar ahora" | 120 | 455 | 140 | 27 | DO alegra_forzar_sync.prg |
| `btn_cancelar` | "Cerrar" | 400 | 455 | 90 | 27 | THISFORM.Release |

`btn_guardar`: BackColor=RGB(0,100,180), ForeColor=RGB(255,255,255), FontBold=.T.
`btn_sync`: BackColor=RGB(0,140,0), ForeColor=RGB(255,255,255)

---

## Código de los métodos

### `Init`
```foxpro
DO C:\S.A.R\PROYECTO\alegra_get_bd.prg   && → PUBLIC LC_ALEGRA_BD

LOCAL LC_CFG, LN_REC02, LN_RECLP
LC_CFG = LC_ALEGRA_BD + "allegra_config.dbf"

**** Verificar que el archivo existe
IF NOT FILE(LC_CFG)
    MESSAGEBOX("allegra_config.dbf no encontrado." + CHR(13) + ;
        "Ejecute instalar_allegra_bd.py primero.", 16, "Alegra")
    RETURN .F.
ENDIF

USE (LC_CFG) IN 0 ALIAS allegra_cfg SHARED
SELECT allegra_cfg

**** Verificar que tiene el campo empresa (estructura nueva)
IF TYPE("allegra_cfg.empresa") == "U"
    USE IN allegra_cfg
    MESSAGEBOX("allegra_config.dbf tiene estructura desactualizada." + CHR(13) + ;
        "Ejecute allegra_sync.py una vez para migrar automáticamente.", 48, "Alegra — Migración requerida")
    RETURN .F.
ENDIF

**** Verificar que existen registros para ambas empresas
LN_REC02 = 0
LN_RECLP = 0
SCAN
    IF ALLTRIM(allegra_cfg.empresa) == "02"
        LN_REC02 = 1
    ENDIF
    IF ALLTRIM(allegra_cfg.empresa) == "LP"
        LN_RECLP = 1
    ENDIF
ENDSCAN

IF LN_REC02 = 0 OR LN_RECLP = 0
    USE IN allegra_cfg
    MESSAGEBOX("Faltan registros en allegra_config.dbf." + CHR(13) + ;
        "Ejecute allegra_sync.py para completar la migración.", 48, "Alegra — Datos incompletos")
    RETURN .F.
ENDIF

**** Leer campos globales del registro 02
LOCATE FOR ALLTRIM(allegra_cfg.empresa) == "02"
THISFORM.txt_max_fact.Value  = allegra_cfg.max_fact
THISFORM.txt_intervalo.Value = allegra_cfg.intervalo
THISFORM.chk_desde_ult.Value = IIF(allegra_cfg.desde_ult, 1, 0)
THISFORM.txt_num_inicio_02.Value = ALLTRIM(allegra_cfg.num_inicio)
THISFORM.lbl_ultima_sin_02.Caption = IIF(EMPTY(allegra_cfg.ultima_sin), ;
    "Sin sincronizaciones", ;
    DTOC(DATE(allegra_cfg.ultima_sin)) + " " + TTOC(allegra_cfg.ultima_sin, 2))
THISFORM.lbl_total_proc_02.Caption = ALLTRIM(STR(allegra_cfg.total_proc)) + " facturas"
THISFORM.edt_ultimo_log.Value = allegra_cfg.ultimo_log

**** Leer datos empresa LP
LOCATE FOR ALLTRIM(allegra_cfg.empresa) == "LP"
THISFORM.txt_num_inicio_lp.Value = ALLTRIM(allegra_cfg.num_inicio)
THISFORM.lbl_ultima_sin_lp.Caption = IIF(EMPTY(allegra_cfg.ultima_sin), ;
    "Sin sincronizaciones", ;
    DTOC(DATE(allegra_cfg.ultima_sin)) + " " + TTOC(allegra_cfg.ultima_sin, 2))
THISFORM.lbl_total_proc_lp.Caption = ALLTRIM(STR(allegra_cfg.total_proc)) + " facturas"

USE IN allegra_cfg
```

### `btn_guardar.Click`
```foxpro
DO C:\S.A.R\PROYECTO\alegra_get_bd.prg

LOCAL LC_CFG, LN_MAX, LN_INT, LB_DESDE, LC_NUM02, LC_NUMLP
LC_CFG   = LC_ALEGRA_BD + "allegra_config.dbf"
LN_MAX   = VAL(ALLTRIM(STR(THISFORM.txt_max_fact.Value)))
LN_INT   = VAL(ALLTRIM(STR(THISFORM.txt_intervalo.Value)))
LB_DESDE = (THISFORM.chk_desde_ult.Value == 1)
LC_NUM02 = UPPER(ALLTRIM(THISFORM.txt_num_inicio_02.Value))
LC_NUMLP = UPPER(ALLTRIM(THISFORM.txt_num_inicio_lp.Value))

IF LN_MAX <= 0
    MESSAGEBOX("El máximo de facturas debe ser mayor a 0.", 48, "Alegra")
    RETURN
ENDIF

USE (LC_CFG) IN 0 ALIAS allegra_cfg_w EXCLUSIVE
SELECT allegra_cfg_w

LOCATE FOR ALLTRIM(allegra_cfg_w.empresa) == "02"
IF FOUND()
    REPLACE max_fact WITH LN_MAX, intervalo WITH LN_INT, ;
            desde_ult WITH LB_DESDE, num_inicio WITH LC_NUM02
ENDIF

LOCATE FOR ALLTRIM(allegra_cfg_w.empresa) == "LP"
IF FOUND()
    REPLACE max_fact WITH LN_MAX, intervalo WITH LN_INT, ;
            desde_ult WITH LB_DESDE, num_inicio WITH LC_NUMLP
ENDIF

USE IN allegra_cfg_w

**** Reiniciar el timer con el nuevo intervalo
ON TIMER 0
IF LN_INT > 0
    ON TIMER (LN_INT * 60) DO C:\S.A.R\PROYECTO\alegra_timer.prg
ENDIF

MESSAGEBOX("Configuración guardada.", 64, "Alegra")
```

### `btn_sync.Click`
```foxpro
THISFORM.Release
DO C:\S.A.R\PROYECTO\alegra_forzar_sync.prg
```

### `btn_cancelar.Click`
```foxpro
THISFORM.Release
```

---

## Flujo de activación inicial (primera vez)

1. Pilar abre **Allegra → Configurar / Sincronizar**
2. Revisa en Alegra cuál fue el último número de factura ya ingresado en Administrator — **por empresa**:
   - Empresa 02 (TV & Video): ej. `PTV21200`
   - Empresa LP (J&P): ej. `PJP15780`
3. Escribe cada número en su campo correspondiente
4. Define el intervalo automático (ej: `5`) o deja `0` para manual
5. Clic en **Guardar**
6. Clic en **Sincronizar ahora** → primera sincronización desde el siguiente número en cada empresa

---

## Notas para construcción en VFP IDE

- Crear el `.scx` desde el IDE de VFP: **File → New → Form**
- Después de crear y guardar, correr en Command Window:
  `COMPILE FORM C:\S.A.R\PROYECTO\configurar_allegra.scx`
- **NO modificar el SCT con Python después de compilar** — respeta el OBJCODE
- El menú llama al SCX vía `configurar_allegra.prg` → `DO FORM configurar_allegra`
