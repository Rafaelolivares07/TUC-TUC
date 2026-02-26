@echo off
title TUC TUC - Bridges
color 0A

echo.
echo  ================================================
echo   TUC TUC - Bridges  [%DATE% %TIME%]
echo   chat_bridge  +  git_bridge  corriendo
echo  ================================================
echo.

REM Lanzar git_bridge con auto-reinicio en ventana separada
start "TUC TUC - git bridge" /min "C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\start_git_bridge.bat"

:inicio
echo  [%TIME%] Iniciando chat_bridge...

py "C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\chat_bridge.py"

REM Si salió con código 0 = ya había otra instancia corriendo, cerrar silencioso
if %errorlevel% equ 0 goto fin

REM Si falló (crash), esperar y reiniciar
echo.
echo  [%TIME%] chat_bridge terminado inesperadamente. Reiniciando en 5s...
timeout /t 5 /nobreak > nul
goto inicio

:fin
