@echo off
echo === Build PilarSetup.exe ===
cd /d "C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos"

python -m PyInstaller --onefile --windowed --uac-admin --name "PilarSetup" ^
  --add-data "administrator_web.py;." ^
  --add-data "admin_agent.py;." ^
  --add-data "popup_web.py;." ^
  --add-data "templates\adm_ventas_clientes.html;templates" ^
  --add-data "templates\adm_consulta_cuentas.html;templates" ^
  pilar_setup.py

echo.
if exist dist\PilarSetup.exe (
    echo OK: dist\PilarSetup.exe listo
    explorer dist
) else (
    echo ERROR: no se genero el EXE
)
pause
