@echo off
copy /Y "%USERPROFILE%\Desktop\admin_agent.py" "C:\S.A.R\admin_agent.py"

(
echo Set WshShell = CreateObject^("WScript.Shell"^)
echo WshShell.Run "cmd /c python ""C:\S.A.R\admin_agent.py"" --servidor https://admin.tuc-tuc.co --cliente pilar ^>^> ""C:\S.A.R\admin_agent.log"" 2^>^&1", 0, False
) > "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AdminAgent.vbs"

echo.
echo ===========================
echo  Instalacion completada OK
echo  Reinicia el PC para activar
echo ===========================
pause
