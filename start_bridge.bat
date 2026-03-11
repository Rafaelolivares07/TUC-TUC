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

REM Código 0 = instancia duplicada o toggle desactivado → cerrar silencioso
if %errorlevel% equ 0 goto fin

REM Si falló (crash o sin BD), esperar y reiniciar
echo.
echo  [%TIME%] chat_bridge terminado. Reiniciando en 30s...
timeout /t 30 /nobreak > nul
goto inicio

:fin
