# Checklist despliegue Alegra — PC Pilar Peralta
_Sesión presencial/remota: 2026-04-14 ~3pm_

---

## CHECKLIST 1 — Verificación de requisitos (antes de tocar nada)

### A. Python

- [ ] Python instalado: `python --version` ≥ 3.9
- [ ] `pip` disponible: `pip --version`
- [ ] Paquete `dbf`: `python -c "import dbf; print(dbf.__version__)"`
- [ ] Paquete `requests`: `python -c "import requests; print(requests.__version__)"`
- [ ] `tkinter` disponible: `python -c "import tkinter; print('ok')"`
- [ ] Python en PATH (accesible desde cmd sin ruta completa)

> Si falta algún paquete: `pip install dbf requests`

---

### B. Estructura de carpetas y archivos en C:\S.A.R\

- [ ] Carpeta `C:\S.A.R\` existe
- [ ] `C:\S.A.R\RutaBaseDatos\ruta.dbf` existe y apunta a la BD correcta
- [ ] `C:\S.A.R\bd_esperada.txt` existe con la ruta correcta
- [ ] `C:\S.A.R\alegra_daemon.pid` — puede o no existir (no crítico)
- [ ] `C:\S.A.R\alegra_daemon_pausa.txt` — NO debe existir (si existe, el daemon arranca pausado)

**Scripts Python presentes:**

- [ ] `C:\S.A.R\alegra_daemon.py`
- [ ] `C:\S.A.R\configurar_allegra.py`
- [ ] `C:\S.A.R\interfaz_allegra.py`
- [ ] `C:\S.A.R\allegra_sync.py`
- [ ] `C:\S.A.R\instalar_allegra_bd.py`

**Ejecutable compilado:**

- [ ] `C:\S.A.R\AlegraDaemon.exe` existe
- [ ] Versión del exe: al correrlo escribe en `alegra_daemon.log` la versión — confirmar `v2.8`

---

### C. Base de datos del cliente

- [ ] Carpeta BD existe: `C:\D\Pilar Peralta\basedatosempresas\`
- [ ] Abre Administrator sin errores — empresa 02 y empresa LP
- [ ] `ruta.dbf` apunta a esa carpeta (verificar con `configurar_allegra.py` → campo "BD esperada")
- [ ] `allegra_config.dbf` existe en la carpeta BD (si no, correr `instalar_allegra_bd.py`)
- [ ] `alegra_tiposdoc.dbf` existe en la carpeta BD
- [ ] `allegra_pendientes.dbf` existe en la carpeta BD (se crea al primer sync)

---

### D. Startup de Windows

- [ ] `AlegraDaemon.exe` en `shell:startup` (o acceso directo a él)
  - Verificar: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`
- [ ] El daemon arranca automáticamente al iniciar sesión Windows

---

### E. Acceso a internet / Alegra

- [ ] Internet activo desde el PC
- [ ] Verificar acceso a API: `python -c "import requests; r=requests.get('https://api.alegra.com/api/v1/invoices?limit=1', headers={'Authorization': 'Basic ' + __import__('base64').b64encode(b'electronicastvyvideo@hotmail.com:ade8e319ce85985fb47c').decode()}, timeout=10); print(r.status_code)"`
  - Resultado esperado: `200`

---

## CHECKLIST 2 — Procedimiento de la sesión

### Paso 1 — Conectar y verificar

1. [ ] Establecer conexión remota
2. [ ] Abrir cmd como administrador
3. [ ] Correr verificaciones del Checklist 1 de arriba
4. [ ] Anotar cualquier diferencia vs. lo esperado antes de modificar

---

### Paso 2 — Copiar archivos actualizados

Copiar desde el PC de Rafael (o desde el repositorio) a `C:\S.A.R\` en el PC de Pilar:

- [ ] `alegra_daemon.py` (v2.8 — intervalo en segundos)
- [ ] `AlegraDaemon.exe` (recompilado 2026-04-14)
- [ ] `configurar_allegra.py` (v2.8 — 4 paneles, UI adaptativa)
- [ ] `interfaz_allegra.py` (4 fases + alertas parciales)
- [ ] `allegra_sync.py`

> Si el daemon está corriendo: matar el proceso antes de sobrescribir el .exe
> `taskkill /IM AlegraDaemon.exe /F`

---

### Paso 3 — Instalar tablas en BD (solo si es primera vez o faltan tablas)

```cmd
python C:\S.A.R\instalar_allegra_bd.py
```

- [ ] Confirmar que crea/verifica `allegra_config.dbf` sin errores
- [ ] Confirmar que crea/verifica `alegra_tiposdoc.dbf`

---

### Paso 4 — Configurar desde el formulario

Abrir: `python C:\S.A.R\configurar_allegra.py`

**Tab Configuración — por empresa (02 y LP):**

- [ ] **BD esperada** — apunta a `C:\D\PILAR PERALTA\BASEDATOSEMPRESAS\DATOS_SAR.DBC`
- [ ] **Máximo de facturas por ciclo** — definir (recomendado: 5 para prueba, luego 20-50)
- [ ] **Pausa entre ciclos (seg)** — definir (recomendado: 300 = 5 minutos en producción; para prueba: 30)
- [ ] **Tipo de documento** — seleccionar `013` (FACTURA VENTA POS) para cada empresa
- [ ] **Métodos de pago** — mapear para cada empresa:
  - Efectivo → `cash`
  - Tarjeta débito → `debit-card`
  - Tarjeta crédito → `credit-card`
  - Transferencia → `transfer`
  - Cobrar cliente → `credit`
- [ ] **Num inicio** — definir el número de factura desde donde arrancar (ej: última factura ya registrada en Administrator)
- [ ] **Auto-crear NITs** — definir si ON o OFF según preferencia de Pilar
- [ ] Guardar configuración — confirmar sin errores

**Tab Configuración — vendedores:**

- [ ] Mapear seller_id Alegra → vendedor Administrator para cada empresa
  - Empresa 02: sellers 1, 2, 3, 4, 6
  - Empresa LP: sellers 1, 3, 4, 7

---

### Paso 5 — Prueba con un ciclo manual

- [ ] Tab Estado & Log → clic **"Un ciclo"**
- [ ] Esperar a que termine (máx 2-3 min con pocos datos)
- [ ] Revisar log en tab Estado & Log — sin errores críticos
- [ ] Tab Facturas — verificar que aparecen facturas en alguna categoría
- [ ] Si hay facturas en "Pendientes": esperado — el ciclo las procesará en la siguiente ejecución
- [ ] Si hay facturas en "Con inconsistencias": revisar motivo — NIT no encontrado o producto sin mapeo
- [ ] Si hay facturas en "Procesadas" o "Procesadas con alertas": verificar en Administrator que quedaron los registros

---

### Paso 6 — Verificar en Administrator

Abrir Administrator con Pilar:

- [ ] Módulo de movimientos de inventario — buscar por fecha hoy — aparecen los registros procesados
- [ ] Módulo contabilidad — buscar asientos de hoy — cuadran débito=crédito
- [ ] Sin duplicados (mismo num_doc aparece solo una vez)

---

### Paso 7 — Activar modo automático

- [ ] Ajustar intervalo a valor definitivo de producción (ej: 300 seg)
- [ ] Guardar
- [ ] Confirmar que `AlegraDaemon.exe` está en startup
- [ ] Reiniciar el daemon desde el formulario (Reanudar) o desde startup
- [ ] Dejar corriendo unos minutos y verificar que el log se actualiza solo

---

### Paso 7b — Probar Pausar / Reanudar

- [ ] Tab Estado & Log → clic **"Pausar"**
  - Label daemon cambia a "Pausado"
  - Botón cambia a "Reanudar"
  - Botones **"Borrado DBF"** y **"Reiniciar proceso"** se habilitan
- [ ] Clic **"Reanudar"**
  - Label daemon vuelve a "Activo"
  - Botón vuelve a "Pausar"
  - Botones **"Borrado DBF"** y **"Reiniciar proceso"** se deshabilitan
- [ ] Verificar que el daemon retoma ciclos automáticamente tras reanudar (log se actualiza)

---

### Paso 8 — Checklist de cierre

- [ ] Daemon corriendo — tab Estado muestra "Activo"
- [ ] Log del último ciclo visible y limpio
- [ ] Pilar sabe abrir el formulario desde el acceso directo del escritorio
- [ ] Pilar sabe identificar las 4 categorías de facturas
- [ ] Pilar sabe cuándo llamar a Rafael (inconsistencias que no se auto-resuelven)

---

## PROBLEMAS CONOCIDOS / PENDIENTES

| Situación | Qué hacer |
|---|---|
| "NIT no encontrado" en inconsistencias | Tab Terceros → Crear o activar auto_nit |
| "Producto no encontrado" | Verificar código producto en Alegra vs Administrator |
| Factura "Con alerta" por overflow de saldo | Reportar a Rafael — revisar saldo producto |
| CDX APPEND — filtros por fecha en Administrator no muestran registros nuevos | Pendiente resolver — workaround: `SELECT * FROM PROD_FACT1` sin filtro sí los muestra |
| Daemon no arranca solo | Verificar que AlegraDaemon.exe está en shell:startup |

---

## DATOS CLAVE (referencia rápida)

| Concepto | Valor |
|---|---|
| BD cliente | `C:\D\PILAR PERALTA\BASEDATOSEMPRESAS\` |
| Scripts | `C:\S.A.R\` |
| Log daemon | `C:\S.A.R\alegra_daemon.log` |
| PID daemon | `C:\S.A.R\alegra_daemon.pid` |
| Archivo pausa | `C:\S.A.R\alegra_daemon_pausa.txt` |
| Empresa TV & Video | `02` — email: `electronicastvyvideo@hotmail.com` |
| Empresa J&P | `LP` — email: `electronicajyp@hotmail.com` |
| Versión actual | `v2.8` |
