"""
pilar_setup.py -- Instalador automatico para PC de Pilar
Empaquetado con PyInstaller --onefile --windowed

Que hace:
  1. Copia archivos a C:/S.A.R/
  2. Escribe admin_agent.ini, abrir_web.prg y PRGs wrapper
  3. pip install flask openpyxl
  4. Crea VBS en Startup para administrator_web y admin_agent
  5. Agrega 2 registros en FORMULARIOS.DBF (ventas web + cuentas web)
  6. Messagebox de confirmacion

Nota: el servidor (ngrok) se configura en admin_agent.ini despues de instalar.
"""

import os, sys, shutil, subprocess, socket
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

SAR_DIR     = Path(r'C:\S.A.R')
STARTUP_DIR = Path(os.environ.get('APPDATA', '')) / 'Microsoft/Windows/Start Menu/Programs/Startup'
CLIENTE_ID  = 'pilar'
AGENT_NAME  = 'Oficina Pilar'


def _base():
    """Directorio donde PyInstaller extrae los datos bundleados."""
    return Path(getattr(sys, '_MEIPASS', Path(__file__).parent))


# ── Paso 1: copiar archivos ───────────────────────────────────────────────────

def paso1_copiar():
    SAR_DIR.mkdir(exist_ok=True)
    (SAR_DIR / 'templates').mkdir(exist_ok=True)

    base = _base()
    for nombre in ['administrator_web.py', 'admin_agent.py', 'popup_web.py']:
        src = base / nombre
        if src.exists():
            shutil.copy2(src, SAR_DIR / nombre)

    for nombre in ['adm_ventas_clientes.html', 'adm_consulta_cuentas.html']:
        src = base / 'templates' / nombre
        if src.exists():
            shutil.copy2(src, SAR_DIR / 'templates' / nombre)


# ── Paso 2: archivos de configuración ────────────────────────────────────────

def paso2_configs():
    # admin_agent.ini — servidor se configura desde la UI de Rafael antes de cada sesión
    (SAR_DIR / 'admin_agent.ini').write_text(
        '[agent]\nnombre = Oficina Pilar\nservidor = \n', encoding='utf-8'
    )

    # abrir_web.prg con path actualizado para C:\S.A.R\
    (SAR_DIR / 'abrir_web.prg').write_bytes(
        '* abrir_web.prg — abre formulario web de Administrator\r\n'
        'LPARAMETERS lcURL\r\n'
        'WAIT WINDOW "Abriendo en el navegador..." NOWAIT\r\n'
        'RUN /N python "C:\\S.A.R\\administrator_web.py"\r\n'
        '=INKEY(2)\r\n'
        'RUN /N C:\\Windows\\System32\\cmd.exe /c start "" &lcURL\r\n'
        'WAIT CLEAR\r\n'.encode('cp1252')
    )

    # abrir_web.bat (alternativa sin VFP)
    (SAR_DIR / 'abrir_web.bat').write_text(
        '@echo off\r\n'
        'start "" python "C:\\S.A.R\\popup_web.py"\r\n'
        'start "" python "C:\\S.A.R\\administrator_web.py"\r\n'
        'timeout /t 2 /nobreak > nul\r\n'
        'start "" %1\r\n',
        encoding='cp1252'
    )



# ── Paso 3: dependencias Python ───────────────────────────────────────────────

def paso3_pip():
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', 'flask', 'openpyxl', '--quiet',
         '--disable-pip-version-check'],
        capture_output=True
    )


# ── Paso 4: arranque automático ───────────────────────────────────────────────

def paso4_startup():
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)

    # administrator_web.py — salida a log
    (STARTUP_DIR / 'AdministratorWeb.vbs').write_text(
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        'WshShell.Run "cmd /c python ""C:\\S.A.R\\administrator_web.py"" '
        '>> ""C:\\S.A.R\\administrator_web.log"" 2>&1", 0, False\r\n',
        encoding='utf-8'
    )

    # admin_agent.py — lee servidor desde admin_agent.ini
    (STARTUP_DIR / 'AdminAgent.vbs').write_text(
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.Run "cmd /c python ""C:\\S.A.R\\admin_agent.py"" '
        f'--cliente {CLIENTE_ID} '
        '>> ""C:\\S.A.R\\admin_agent.log"" 2>&1", 0, False\r\n',
        encoding='utf-8'
    )


# ── Paso 5: FORMULARIOS.DBF ───────────────────────────────────────────────────

def paso5_formularios():
    try:
        import dbf
    except ImportError:
        return 'dbf no instalado — instalar con pip install dbf'

    import datetime

    ruta_file = Path(r'C:\S.A.R\RutaBaseDatos\ruta.dbf')
    if not ruta_file.exists():
        return 'No se encontró C:\\S.A.R\\RutaBaseDatos\\ruta.dbf'

    t = dbf.Table(str(ruta_file), codepage='cp1252', ignore_memos=True)
    t.open(dbf.READ_ONLY)
    ruta_bd = None
    for r in t:
        ruta_bd = r['RUTA'].strip()
        break
    t.close()

    if not ruta_bd:
        return 'ruta.dbf no tiene registro'

    bd_dir        = Path(ruta_bd).parent
    form_path     = bd_dir / 'FORMULARIOS.DBF'
    permisos_path = bd_dir / 'USUARIOS_PERFILES_FORMULARIOS.DBF'

    if not form_path.exists():
        return f'No se encontró FORMULARIOS.DBF en {bd_dir}'

    # ── FORMULARIOS: agregar los 2 registros ──────────────────────────────────
    t = dbf.Table(str(form_path), codepage='cp1252', ignore_memos=True)
    t.open(dbf.READ_WRITE)

    nombres = {str(r['NOMBRE']).lower().strip() for r in t if not dbf.is_deleted(r)}
    max_c   = max((r['CONSECUTIV'] for r in t if not dbf.is_deleted(r)), default=0)

    nom_ventas  = r'run /n c:\s.a.r\abrir_web.bat http://localhost:5002/ventas_clientes'
    nom_cuentas = r'run /n c:\s.a.r\abrir_web.bat http://localhost:5002/consulta_cuentas'
    nuevos = []

    if nom_ventas not in nombres:
        max_c += 1
        t.append({'NOMBRE_MEN': 'ventas por clientes', 'NOMBRE': nom_ventas,
                  'CONSECUTIV': max_c, 'ACCESO': 20, 'MODULO': 25, 'VEMPRESA': 1, 'VCUENTA': 0})
        nuevos.append(max_c)

    if nom_cuentas not in nombres:
        max_c += 1
        t.append({'NOMBRE_MEN': 'terceros acumulados x cuenta en rango fechas', 'NOMBRE': nom_cuentas,
                  'CONSECUTIV': max_c, 'ACCESO': 20, 'MODULO': 25, 'VEMPRESA': 1, 'VCUENTA': 0})
        nuevos.append(max_c)

    t.close()

    if not nuevos or not permisos_path.exists():
        return None

    # ── USUARIOS_PERFILES_FORMULARIOS: dar acceso a los mismos usuarios del módulo 25 ──
    # Encontrar consecutivos actuales del módulo 25
    t_f = dbf.Table(str(form_path), codepage='cp1252', ignore_memos=True)
    t_f.open(dbf.READ_ONLY)
    mod25 = {r['CONSECUTIV'] for r in t_f if not dbf.is_deleted(r) and r['MODULO'] == 25}
    t_f.close()

    tp = dbf.Table(str(permisos_path), codepage='cp1252', ignore_memos=True)
    tp.open(dbf.READ_WRITE)

    from collections import Counter
    conteo = Counter(r['USUARIO'] for r in tp
                     if not dbf.is_deleted(r) and r['FORMULARIO'] in mod25 and r['ESTADO'] == 1)
    usuarios_activos = [u for u, _ in conteo.most_common(10)]

    existentes = {(r['USUARIO'], r['FORMULARIO']) for r in tp if not dbf.is_deleted(r)}
    ahora = datetime.datetime.now()

    for usuario in usuarios_activos:
        for consec in nuevos:
            if (usuario, consec) not in existentes:
                tp.append({
                    'USUARIO':    usuario,
                    'FORMULARIO': consec,
                    'ESTADO':     1,
                    'USUARIO_IN': usuario,
                    'FECHAHORA':  ahora,
                })

    tp.close()
    return None




# ── Log ──────────────────────────────────────────────────────────────────────

LOG_FILE = SAR_DIR / 'pilar_setup.log'

def _log(linea: str):
    import datetime
    SAR_DIR.mkdir(exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {linea}\n")




# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.withdraw()

    _log('=== PilarSetup iniciado ===')
    advertencias = []

    pasos = [
        ('Copiando archivos',               paso1_copiar),
        ('Escribiendo configuración',        paso2_configs),
        ('Instalando dependencias Python',   paso3_pip),
        ('Configurando inicio automático',   paso4_startup),
        ('Configurando Administrator VFP',   paso5_formularios),
    ]

    for desc, fn in pasos:
        try:
            resultado = fn()
            if isinstance(resultado, str):
                _log(f'ADVERTENCIA [{desc}]: {resultado}')
                advertencias.append(f'• {desc}: {resultado}')
            else:
                _log(f'OK [{desc}]')
        except Exception as e:
            _log(f'ERROR [{desc}]: {e}')
            advertencias.append(f'• {desc}: {e}')

    if advertencias:
        _log('Instalación completada con advertencias.')
    else:
        _log('Instalación completada exitosamente.')

    if advertencias:
        messagebox.showwarning(
            'Instalación con advertencias',
            'Instalación completada, pero con advertencias:\n\n' +
            '\n'.join(advertencias) +
            '\n\nRevisa C:\\S.A.R\\pilar_setup.log o contacta a Rafael.'
        )
    else:
        messagebox.showinfo(
            'Instalación completa ✓',
            'Todo listo.\n\n'
            '• Administrator Web y Admin Agent se inician solos al encender el PC.\n'
            '• Reinicia el PC para activarlo.'
        )


if __name__ == '__main__':
    main()
