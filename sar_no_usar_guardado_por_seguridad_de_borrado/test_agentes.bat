@echo off
echo Probando comando exacto del VBS...
cmd /c ""C:\S.A.R\actualizaciones\agentes\AdminAgent.exe"" --servidor https://admin.tuc-tuc.co --cliente lenovo >> ""C:\S.A.R\actualizaciones\agentes\admin_agent.log"" 2>&1
echo FIN codigo: %ERRORLEVEL%
pause
