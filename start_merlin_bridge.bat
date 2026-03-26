@echo off
title TUC TUC - Merlin Bridge
color 0B

echo.
echo  ================================================
echo   TUC TUC - Merlin Bridge  [%DATE% %TIME%]
echo   Merlin responde en el chat de usuarios
echo  ================================================
echo.

:inicio
echo  [%TIME%] Iniciando chat_merlin_bridge...

py "C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\chat_merlin_bridge.py"

REM Código 0 = instancia duplicada → cerrar silencioso
if %errorlevel% equ 0 goto fin

REM Si falló, esperar y reiniciar
echo.
echo  [%TIME%] Bridge terminado. Reiniciando en 30s...
timeout /t 30 /nobreak > nul
goto inicio

:fin
