"""
instalar_tuctuc.py — Instalador TUC TUC para PC cliente
Uso: python instalar_tuctuc.py [nombre_pc]
     python instalar_tuctuc.py "Pilar Peralta"
"""

import os, sys, subprocess, shutil, configparser

REPO_URL = "https://github.com/Rafaelolivares07/TUC-TUC.git"
REPO_DIR = r"C:\TUC-TUC"
SAR_DIR  = r"C:\S.A.R"
NOMBRE   = sys.argv[1] if len(sys.argv) > 1 else "Cliente TUC TUC"

PAQUETES = "flask openpyxl dbf requests numpy"

OK  = "  [OK]"
ERR = "  [!!]"
INF = "  [--]"

def titulo(txt):
    print(f"\n{'='*52}\n  {txt}\n{'='*52}")

def run(cmd, capture=False):
    print(f"      > {cmd[:80]}")
    return subprocess.run(cmd, shell=True,
                          capture_output=capture,
                          text=True)


# ── 1. Estructura carpetas ────────────────────────────────────────────────────

def crear_estructura():
    print("\n[1] Estructura de carpetas C:\\S.A.R\\")
    for sub in ['alegra', 'web', 'agent', 'remote']:
        d = os.path.join(SAR_DIR, sub)
        os.makedirs(d, exist_ok=True)
        print(f"{OK} {d}")


# ── 2. Git ────────────────────────────────────────────────────────────────────

def verificar_git():
    print("\n[2] Git")
    r = run("git --version", capture=True)
    if r.returncode == 0:
        print(f"{OK} {r.stdout.strip()}")
        return True
    print(f"{INF} Git no encontrado — instalando via winget...")
    r = run("winget install Git.Git --silent --accept-source-agreements --accept-package-agreements")
    if r.returncode == 0:
        os.environ['PATH'] += r';C:\Program Files\Git\cmd'
        print(f"{OK} Git instalado — puede requerir reiniciar la terminal")
        return True
    print(f"{ERR} No se pudo instalar Git automáticamente")
    print(f"      Descarga manual: https://git-scm.com/download/win")
    return False


# ── 3. Repositorio ────────────────────────────────────────────────────────────

def clonar_o_actualizar():
    print("\n[3] Repositorio TUC TUC")
    if os.path.isdir(os.path.join(REPO_DIR, '.git')):
        print(f"{INF} Ya existe — actualizando...")
        run(f'git -C "{REPO_DIR}" pull --quiet')
    else:
        print(f"{INF} Clonando en {REPO_DIR}...")
        run(f'git clone "{REPO_URL}" "{REPO_DIR}"')
    print(f"{OK} Repo listo en {REPO_DIR}")


# ── 4. Paquetes Python ────────────────────────────────────────────────────────

def instalar_paquetes():
    print("\n[4] Paquetes Python")
    run(f'pip install {PAQUETES} --quiet --disable-pip-version-check')
    print(f"{OK} {PAQUETES}")


# ── 5. abrir_web.bat ─────────────────────────────────────────────────────────

def configurar_bat():
    print("\n[5] abrir_web.bat")
    bat = os.path.join(SAR_DIR, 'abrir_web.bat')
    contenido = (
        "@echo off\n"
        f'start "" python "{REPO_DIR}\\popup_web.py"\n'
        f'start "" python "{REPO_DIR}\\administrator_web.py"\n'
        "timeout /t 2 /nobreak > nul\n"
        "start \"\" %1\n"
    )
    with open(bat, 'w') as f:
        f.write(contenido)
    print(f"{OK} {bat}")


# ── 6. admin_agent.ini ───────────────────────────────────────────────────────

def configurar_agent():
    print("\n[6] admin_agent.ini")
    ini = os.path.join(REPO_DIR, 'admin_agent.ini')
    cfg = configparser.ConfigParser()
    cfg['agent'] = {'nombre': NOMBRE}
    with open(ini, 'w') as f:
        cfg.write(f)
    print(f"{OK} {ini}  (nombre={NOMBRE})")


# ── 7. Startup Windows ───────────────────────────────────────────────────────

def configurar_startup():
    print("\n[7] Startup Windows")
    startup = os.path.join(
        os.environ.get('APPDATA', ''),
        r'Microsoft\Windows\Start Menu\Programs\Startup'
    )

    # admin_agent
    agent_bat = os.path.join(startup, 'TucTuc_AdminAgent.bat')
    with open(agent_bat, 'w') as f:
        f.write(
            "@echo off\n"
            f'start "" python "{REPO_DIR}\\admin_agent.py"\n'
        )
    print(f"{OK} AdminAgent startup: {agent_bat}")

    # Nota AsistenciaTucTuc
    exe_dest = os.path.join(SAR_DIR, 'remote', 'AsistenciaTucTuc.exe')
    if not os.path.isfile(exe_dest):
        print(f"{INF} AsistenciaTucTuc.exe — descargar y copiar a {exe_dest}")
        print(f"      URL: https://github.com/Rafaelolivares07/TUC-TUC/releases/latest/download/AsistenciaTucTuc.exe")
    else:
        remote_bat = os.path.join(startup, 'TucTuc_AsistenciaRemota.bat')
        with open(remote_bat, 'w') as f:
            f.write(
                "@echo off\n"
                f'start "" "{exe_dest}"\n'
            )
        print(f"{OK} AsistenciaRemota startup: {remote_bat}")


# ── 8. Actualizar repo a futuro ───────────────────────────────────────────────

def crear_actualizador():
    print("\n[8] Actualizador")
    upd = os.path.join(SAR_DIR, 'actualizar_tuctuc.bat')
    with open(upd, 'w') as f:
        f.write(
            "@echo off\n"
            f'git -C "{REPO_DIR}" pull\n'
            f'pip install {PAQUETES} --quiet --upgrade\n'
            'echo Actualizacion completada\n'
            'pause\n'
        )
    print(f"{OK} {upd}  (doble clic para actualizar todo)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    titulo(f"TUC TUC — Instalador  ({NOMBRE})")

    crear_estructura()
    git_ok = verificar_git()
    if git_ok:
        clonar_o_actualizar()
    else:
        print(f"\n{ERR} Instala Git manualmente y vuelve a correr este script")
        input("  Presiona Enter para salir...")
        sys.exit(1)
    instalar_paquetes()
    configurar_bat()
    configurar_agent()
    configurar_startup()
    crear_actualizador()

    titulo("Instalacion completa")
    print(f"{OK} Repo:         {REPO_DIR}")
    print(f"{OK} Scripts SAR:  {SAR_DIR}")
    print(f"{OK} Actualizador: {SAR_DIR}\\actualizar_tuctuc.bat")
    print(f"\n{INF} Para actualizar en el futuro:")
    print(f"      git -C \"{REPO_DIR}\" pull")
    print(f"      — o doble clic en actualizar_tuctuc.bat")
    input("\n  Presiona Enter para cerrar...")


if __name__ == '__main__':
    main()
