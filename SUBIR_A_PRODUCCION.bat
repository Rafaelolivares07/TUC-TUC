@echo off
chcp 65001 >nul
title SUBIR TUCTUC A PRODUCCION
cd /d "%~dp0"
echo ================================================
echo  TUC TUC V2 - Subir a produccion
echo ================================================
echo.
for /f %%h in ('git rev-parse --short HEAD') do set HEAD=%%h
echo [1/3] Tu commit actual: %HEAD%
echo.
echo [2/3] Subiendo a GitHub (rama v2)...
git push origin v2
if errorlevel 1 (
  echo.
  echo X ERROR al subir. Revisa tu internet y haz doble clic de nuevo.
  echo.
  pause
  exit /b 1
)
echo.
echo OK - Subido a GitHub.
echo.
echo [3/3] Esperando que el servidor actualice (puede tardar unos minutos)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verificar_deploy.ps1" "%HEAD%"
echo.
pause
