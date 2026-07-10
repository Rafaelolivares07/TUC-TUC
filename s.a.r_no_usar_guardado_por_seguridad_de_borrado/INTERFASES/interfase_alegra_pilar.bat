@echo off
powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm 'https://github.com/Rafaelolivares07/TUC-TUC/releases/download/interfases/instalar_interfases.ps1')))"
pause
