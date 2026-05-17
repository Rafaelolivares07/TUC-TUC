@echo off
echo Actualizando SAR Agentes...

set DEST=C:\S.A.R\actualizaciones\agentes
set BASE=https://github.com/Rafaelolivares07/TUC-TUC/releases/download/agentes

echo Descargando AdminAgent.exe...
powershell -Command "Invoke-WebRequest '%BASE%/AdminAgent.exe' -OutFile '%DEST%\AdminAgent_new.exe'"
if not exist "%DEST%\AdminAgent_new.exe" (
    echo ERROR: No se pudo descargar AdminAgent.exe
    pause & exit /b 1
)

echo Descargando SarReportes.exe...
powershell -Command "Invoke-WebRequest '%BASE%/SarReportes.exe' -OutFile '%DEST%\SarReportes_new.exe'"
if not exist "%DEST%\SarReportes_new.exe" (
    echo ERROR: No se pudo descargar SarReportes.exe
    pause & exit /b 1
)

echo Deteniendo agentes...
taskkill /f /im AdminAgent.exe >nul 2>&1
taskkill /f /im SarReportes.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Reemplazando ejecutables...
move /y "%DEST%\AdminAgent_new.exe"  "%DEST%\AdminAgent.exe"
move /y "%DEST%\SarReportes_new.exe" "%DEST%\SarReportes.exe"

echo Configurando ini...
(echo [agent]& echo nombre = Oficina lenovo& echo cliente_id = lenovo) > "%DEST%\admin_agent.ini"

echo Reiniciando agentes...
start "" "%DEST%\AdminAgent.exe" --cliente lenovo
start "" "%DEST%\SarReportes.exe"

echo.
echo Actualizacion completada. Agentes reiniciados.
pause