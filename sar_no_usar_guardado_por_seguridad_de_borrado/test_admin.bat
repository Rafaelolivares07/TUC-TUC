@echo off
cd /d C:\S.A.R
echo Corriendo AdminAgent.exe...
AdminAgent.exe --servidor https://admin.tuc-tuc.co --cliente lenovo
echo.
echo === FIN - codigo de salida: %ERRORLEVEL% ===
pause
