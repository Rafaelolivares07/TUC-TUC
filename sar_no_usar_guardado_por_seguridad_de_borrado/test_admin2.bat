@echo off
cd /d C:\S.A.R
echo Corriendo AdminAgentDebug.exe...
AdminAgentDebug.exe --servidor https://admin.tuc-tuc.co --cliente lenovo
echo.
echo === FIN - codigo de salida: %ERRORLEVEL% ===
pause
