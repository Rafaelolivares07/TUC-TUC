@echo off
echo Actualizando SAR Reportes...
taskkill /f /im SarReportes.exe >nul 2>&1
powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://github.com/Rafaelolivares07/TUC-TUC/releases/download/SarAgentes-v1.2/SarReportes.exe' -OutFile 'C:\S.A.R\actualizaciones\agentes\SarReportes.exe' -UseBasicParsing"
start "" "C:\S.A.R\actualizaciones\agentes\SarReportes.exe"
echo Listo. SAR Reportes actualizado a v1.2
pause
