@echo off
echo Aplicando fix Lenovo...

echo [aws]> "C:\S.A.R\actualizaciones\agentes\server.ini"
echo base_url = https://admin.tuc-tuc.co>> "C:\S.A.R\actualizaciones\agentes\server.ini"
echo usuario = rafael>> "C:\S.A.R\actualizaciones\agentes\server.ini"
echo password = grandesventas99>> "C:\S.A.R\actualizaciones\agentes\server.ini"
echo cliente_id = lenovo>> "C:\S.A.R\actualizaciones\agentes\server.ini"
echo OK server.ini

taskkill /f /im SarReportes.exe >nul 2>&1
start "" "C:\S.A.R\actualizaciones\agentes\SarReportes.exe"
echo OK SarReportes iniciado
pause
