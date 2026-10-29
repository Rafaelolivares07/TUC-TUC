@echo off
REM ============================================================
REM  muse_telegram_autostart.bat - Canal Telegram a prueba de reinicio
REM  Levanta tunel SSH 5435 + escuchador. Idempotente: si ya corre,
REM  no duplica (single_flight decide). Se invoca desde:
REM  - Acceso directo en shell:startup (arranque de Windows)
REM  - INICIAR_MUSE.bat [7/8] (apertura de sesion)
REM ============================================================
set "V2=C:\Users\RAFAEL OLIVARES\Documents\TucTucV2"
set "PY=C:\Tools\Python313\pythonw.exe"
set "PEM=C:\Users\RAFAEL OLIVARES\Documents\tuctuc-linux.pem"

REM Tunel solo si 5435 no escucha
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 5435 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel% neq 0 start "muse-tunel-5435" /min ssh -i "%PEM%" -L 5435:localhost:5432 -N -o StrictHostKeyChecking=no -o ServerAliveInterval=30 ubuntu@18.217.231.167

REM Escuchador (no duplica si ya vive)
start "muse-tg-listener" "%PY%" "%V2%\muse_tg_listener.py"
