# Checklist despliegue Alegra — PC Pilar Peralta
_Sesión presencial/remota: 2026-04-14 ~3pm_

---

## CHECKLIST 1 — Verificación de requisitos (antes de tocar nada)

### A. Python

- [x] Python instalado: `python --version` ≥ 3.9 — **3.11.9** ✅
- [x] `pip` disponible: `pip --version` — **24.0** ✅
- [x] Paquete `dbf`: instalado ✅
- [x] Paquete `requests`: **2.33.1** ✅
- [x] `tkinter` disponible: ok ✅
- [x] Python en PATH (accesible desde cmd sin ruta completa) ✅

> Si falta algún paquete: `pip install dbf requests`

---

### B. Estructura de carpetas y archivos en C:\S.A.R\

- [x] Carpeta `C:\S.A.R\` existe ✅
- [x] `C:\S.A.R\RutaBaseDatos\ruta.dbf` — apunta a `\\192.168.1.104\BASEDATOSEMPRESAS\DATOS_SAR.DBC` ✅
- [x] `C:\S.A.R\bd_esperada.txt` — no existe, no crítico ✅
- [x] `C:\S.A.R\alegra_daemon.pid` — no existe (daemon no corriendo) ✅
- [x] `C:\S.A.R\alegra_daemon_pausa.txt` — no existe ✅

**Scripts Python presentes:**

- [x] `C:\S.A.R\alegra_daemon.py` ✅
- [x] `C:\S.A.R\configurar_allegra.py` ✅
- [x] `C:\S.A.R\interfaz_allegra.py` ✅
- [x] `C:\S.A.R\allegra_sync.py` ✅
- [x] `C:\S.A.R\instalar_allegra_bd.py` ✅

**Ejecutable compilado:**

- [x] `C:\S.A.R\AlegraDaemon.exe` existe ✅
- [ ] Versión del exe: al correrlo escribe en `alegra_daemon.log` la versión — confirmar `v2.8`

---

### C. Base de datos del cliente

- [x] Carpeta BD existe: `\\192.168.1.104\BASEDATOSEMPRESAS\` (share de red, no C:\D\) ✅
- [ ] Abre Administrator sin errores — empresa 02 y empresa LP
- [x] `ruta.dbf` apunta a `\\192.168.1.104\BASEDATOSEMPRESAS\DATOS_SAR.DBC` ✅
- [x] `allegra_config.dbf` — creado con instalar_allegra_bd.py (ver Paso 3)
- [x] `alegra_tiposdoc.dbf` — creado con instalar_allegra_bd.py (ver Paso 3)
- [ ] `allegra_pendientes.dbf` — se crea al primer sync

---

### D. Startup de Windows

- [x] `AlegraDaemon.exe` en startup — `AlegraDaemon.bat` creado en `shell:startup` ✅
- [ ] El daemon arranca automáticamente al iniciar sesión Windows — pendiente verificar en próximo reinicio

---

### E. Acceso a internet / Alegra

- [ ] Internet activo desde el PC
- [ ] Verificar acceso a API: `python -c "import requests; r=requests.get('https://api.alegra.com/api/v1/invoices?limit=1', headers={'Authorization': 'Basic ' + __import__('base64').b64encode(b'electronicastvyvideo@hotmail.com:ade8e319ce85985fb47c').decode()}, timeout=10); print(r.status_code)"`
  - Resultado esperado: `200`

---

## CHECKLIST 2 — Procedimiento de la sesión

### Paso 1 — Conectar y verificar

1. [x] Establecer conexión remota ✅ (AsistenciaTucTuc + relay)
2. [x] Abrir cmd como administrador ✅
3. [x] Correr verificaciones del Checklist 1 de arriba ✅
4. [x] Diferencias encontradas: BD en red `\\192.168.1.104\BASEDATOSEMPRESAS\`, no en C:\D\ ✅

---

### Paso 2 — Copiar archivos actualizados

Copiar desde el PC de Rafael (o desde el repositorio) a `C:\S.A.R\` en el PC de Pilar:

- [x] `alegra_daemon.py` — transferido vía relay ✅
- [x] `AlegraDaemon.exe` — compilado 14/04/2026 04:23pm ✅
- [x] `configurar_allegra.py` — transferido vía relay ✅
- [x] `interfaz_allegra.py` — transferido vía relay ✅
- [x] `allegra_sync.py` — transferido vía relay ✅

---

### Paso 3 — Instalar tablas en BD (solo si es primera vez o faltan tablas)

```cmd
python C:\S.A.R\instalar_allegra_bd.py
```

- [x] Confirmar que crea/verifica `allegra_config.dbf` sin errores ✅
- [x] Confirmar que crea/verifica `alegra_tiposdoc.dbf` ✅

---

### Paso 4 — Configurar desde el formulario

Abrir: `python C:\S.A.R\configurar_allegra.py`

**Tab Configuración — por empresa (02 y LP):**

- [x] **BD esperada** — apunta a `\\192.168.1.104\BASEDATOSEMPRESAS\DATOS_SAR.DBC` ✅
- [x] **Máximo de facturas por ciclo** — configurado ✅
- [x] **Pausa entre ciclos (seg)** — configurado ✅
- [x] **Tipo de documento** — `013` (FACTURA VENTA POS) para cada empresa ✅
- [x] **Métodos de pago** — mapeados por Rafael junto a Pilar ✅
- [x] **Num inicio** — definido por empresa ✅
- [x] **Auto-crear NITs** — configurado según preferencia de Pilar ✅
- [x] Guardar configuración — sin errores ✅

**Tab Configuración — vendedores:**

- [x] Sellers mapeados por Rafael junto a Pilar ✅

---

### Paso 5 — Prueba con un ciclo manual

- [x] Tab Estado & Log → clic **"Un ciclo"** ✅ (hecho por Rafael junto a Pilar)
- [x] Revisar log — sin errores críticos ✅
- [x] Tab Facturas — facturas en categorías ✅
- [x] Verificar en Administrator que quedaron los registros ✅ — todas las fases procesaron correctamente

> **Bug conocido (cosmético):** la UI solo muestra "hecho" en f_prod1, no en f_standar/f_costos/f_contab. Los registros SÍ se crean correctamente en Administrator. Fix pendiente.

---

### Paso 6 — Verificar en Administrator

Abrir Administrator con Pilar:

- [x] Módulo de movimientos de inventario — registros procesados confirmados ✅
- [x] Módulo contabilidad — asientos de hoy correctos ✅
- [x] Sin duplicados ✅

---

### Paso 7 — Activar modo automático

- [x] Ajustar intervalo a valor definitivo de producción ✅
- [x] Guardar ✅
- [x] `AlegraDaemon.bat` en shell:startup ✅ (bat lanza AlegraDaemon.exe)
- [ ] Reiniciar el daemon y verificar log — pendiente verificar próximo arranque Windows

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

- [ ] Daemon corriendo en modo automático — pendiente verificar
- [x] Log del último ciclo visible y limpio ✅
- [x] Pilar sabe abrir el formulario — acceso directo "Alegra Config" en escritorio ✅
- [x] Pilar sabe identificar las 4 categorías de facturas ✅
- [x] Pilar sabe cuándo llamar a Rafael ✅

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
| BD cliente | `\\192.168.1.104\BASEDATOSEMPRESAS\` (share de red) |
| Scripts | `C:\S.A.R\` |
| Log daemon | `C:\S.A.R\alegra_daemon.log` |
| PID daemon | `C:\S.A.R\alegra_daemon.pid` |
| Archivo pausa | `C:\S.A.R\alegra_daemon_pausa.txt` |
| Empresa TV & Video | `02` — email: `electronicastvyvideo@hotmail.com` |
| Empresa J&P | `LP` — email: `electronicajyp@hotmail.com` |
| Versión actual | `v2.8` |
