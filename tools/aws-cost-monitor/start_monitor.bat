@echo off
setlocal
title AWS Infrastructure Monitor - Solo lectura
cd /d "%~dp0"

echo ====================================================
echo   AWS Infrastructure Monitor - Puerto 5020
echo   Modo seguro: solo lectura
echo ====================================================
echo.

where aws >nul 2>&1
if errorlevel 1 (
    echo ERROR: AWS CLI no esta disponible.
    pause
    exit /b 1
)

start "AWS Monitor Server" /b python app.py
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5020

echo Panel abierto en http://127.0.0.1:5020
echo Cierra esta ventana para detener el servidor local.
echo.
pause
endlocal
