@echo off
powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm 'https://github.com/Rafaelolivares07/TUC-TUC/releases/download/SarAgentes-v1.0/instalar_sar.ps1'))) -Cliente lenovo -Nombre 'Lenovo Pruebas'"
pause
