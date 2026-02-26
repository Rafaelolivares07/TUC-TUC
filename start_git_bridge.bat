@echo off
title TUC TUC - git bridge

:inicio
py "C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\git_bridge.py"

REM Si salió con código 0 = ya había otra instancia corriendo, cerrar silencioso
if %errorlevel% equ 0 goto fin

REM Si falló (crash), esperar y reiniciar
echo.
echo  [%TIME%] git_bridge terminado inesperadamente. Reiniciando en 5s...
timeout /t 5 /nobreak > nul
goto inicio

:fin
