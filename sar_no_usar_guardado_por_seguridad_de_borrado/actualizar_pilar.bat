@echo off
powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm 'https://github.com/Rafaelolivares07/TUC-TUC/releases/download/agentes/instalar_sar.ps1'))) -Cliente pilar -Nombre 'Oficina Pilar'"
pause
