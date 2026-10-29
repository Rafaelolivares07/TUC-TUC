@echo off
chcp 65001 >nul
REM ============================================================
REM  INICIAR_MUSE.bat - Arranque diario de Muse (TUC TUC V2)
REM  Uso: doble clic cada dia. Pide tema, chequea entorno,
REM  abre pestana WT con titulo fijo e invoca muse --yolo.
REM  Idempotente. Directorio de trabajo: raiz (AGENTS.md + V2 + docs).
REM  Regla cmd: cero parentesis literales en echos dentro de
REM  bloques (...) - el texto con ) aborta el parseo. Estilo goto.
REM ============================================================
setlocal EnableDelayedExpansion
title Muse - arranque diario
cd /d "C:\Users\RAFAEL OLIVARES" || (echo No se pudo ir a la raiz & pause & exit /b 1)
set "V2=C:\Users\RAFAEL OLIVARES\Documents\TucTucV2"
set "DOCS=C:\Users\RAFAEL OLIVARES\Documents\docs"
set "CREDS=C:\Tools\muse-git-credentials"
set "TEMA=%DOCS%\_conversacion\tema_activo.txt"
set "SELECTOR=%DOCS%\_conversacion\ELEGIR_TEMA.ps1"

echo [1/8] Directorio: %CD%
if not exist "%V2%" echo AVISO: falta %V2%
if not exist "%DOCS%" echo AVISO: falta %DOCS%

echo [2/8] Git identidad + config repo V2
for /f "delims=" %%u in ('git config --global user.name 2^>nul') do echo   user: %%u
git -C "%V2%" config http.sslbackend openssl >nul
git -C "%V2%" config --get-all credential.helper 2>nul | findstr /C:"muse-git-credentials" >nul || git -C "%V2%" config credential.helper "store --file C:/Tools/muse-git-credentials" >nul
echo   sslbackend + credential-helper OK

echo [3/8] PAT para push solo de Muse
if exist "%CREDS%" echo   credenciales OK
if exist "%CREDS%" goto :pat_ok
echo   Falta %CREDS% - Muse no podra pushear solo (pedira aprobacion).
echo   Crea un PAT fine-grained en github.com: repo TUC-TUC, Contents read+write.
powershell -NoProfile -Command "if ([Console]::IsInputRedirected) { exit 2 }; $s=Read-Host 'Pega el PAT (no se muestra, Enter para omitir)' -AsSecureString; $p=[Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)); if($p.Length -lt 10){exit 1}; 'https://Rafaelolivares07:'+$p+'@github.com' | Out-File -FilePath 'C:\Tools\muse-git-credentials' -Encoding ascii -NoNewline"
if %errorlevel% equ 0 (echo   PAT guardado.) else if %errorlevel% equ 2 (echo   Omitido: sin consola interactiva.) else (echo   Omitido. Re-ejecuta este script cuando tengas el PAT.)
:pat_ok

echo [4/8] Fetch + estado V2
git -C "%V2%" fetch origin
set N=0
for /f "delims=" %%b in ('git -C "%V2%" status -sb 2^>nul') do (
  set /a N+=1
  if !N! leq 12 echo   %%b
)
if !N! gtr 12 echo   ... (!N! lineas en total, ver resto con git status)

echo [5/8] Tema de trabajo
if exist "%TEMA%" goto :tema_ant
echo   Sin tema anterior.
goto :tema_sel
:tema_ant
set /p TEMA_ANT=<"%TEMA%"
echo   Anterior: !TEMA_ANT!
:tema_sel
if not exist "%SELECTOR%" echo   AVISO: falta selector, sigo con el tema anterior.
if not exist "%SELECTOR%" goto :tema_ok
powershell -NoProfile -Command "if ([Console]::IsInputRedirected) { exit 2 }"
if %errorlevel% equ 2 goto :tema_noconsola
powershell -NoProfile -ExecutionPolicy Bypass -File "%SELECTOR%"
goto :tema_ok
:tema_noconsola
echo   Omitido: sin consola interactiva.
:tema_ok

echo [6/8] Etiqueta de pestana
set "ETIQUETA=TUCTUC"
powershell -NoProfile -Command "$p='C:\Users\RAFAEL OLIVARES\Documents\docs\_conversacion\tema_activo.txt'; $t=''; if (Test-Path $p) { $t=Get-Content $p -TotalCount 1 }; $r='TUCTUC'; if (-not [string]::IsNullOrWhiteSpace($t)) { $r=(($t -replace '^\d+_','') -replace '\.md$','').ToUpper() }; [IO.File]::WriteAllText($env:TEMP+'\muse_etiqueta.txt', $r)"
set /p ETIQUETA=<"%TEMP%\muse_etiqueta.txt" 2>nul
if not defined ETIQUETA set "ETIQUETA=TUCTUC"
del "%TEMP%\muse_etiqueta.txt" 2>nul
echo   Pestana: !ETIQUETA!

echo [7/8] Python + CLI muse + acceso
C:\Tools\Python313\python.exe --version 2>&1
set "MUSECMD="
for %%c in (muse muse-code) do (
  if not defined MUSECMD (
    where %%c >nul 2>nul && set "MUSECMD=%%c"
  )
)
if defined MUSECMD (echo   CLI: !MUSECMD!) else (echo   AVISO: muse no esta en PATH.)
C:\Tools\Python313\python.exe -c "import edge_tts" 2>nul && echo   voz OK || echo   AVISO: falta edge-tts, sin voz
if not exist "%V2%\muse_voz\habla_edge.py" echo   AVISO: falta muse_voz
call "%V2%\muse_telegram_autostart.bat" >nul 2>nul
echo   canal Telegram OK
set "LNK=%USERPROFILE%\Desktop\INICIAR MUSE.lnk"
if exist "%LNK%" echo   acceso OK
if exist "%LNK%" goto :lnk_ok
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($env:USERPROFILE+'\Desktop\INICIAR MUSE.lnk'); $s.TargetPath='C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\INICIAR_MUSE.bat'; $s.WorkingDirectory='C:\Users\RAFAEL OLIVARES'; $s.Save()"
if %errorlevel% equ 0 (echo   acceso creado.) else (echo   no se pudo crear acceso.)
:lnk_ok
if not defined MUSECMD (pause & exit /b 1)

echo [8/8] Abrir pestana !ETIQUETA!
C:\Tools\Python313\python.exe "%V2%\muse_cuota.py" 2>nul
set "CUOTATAG="
set /p CUOTATAG=<"%TEMP%\muse_cuota_tag.txt" 2>nul
del "%TEMP%\muse_cuota_tag.txt" 2>nul
if defined CUOTATAG set "ETIQUETA=!ETIQUETA! !CUOTATAG!"
echo   Titulo: !ETIQUETA!
echo !ETIQUETA!>%TEMP%\muse_tab_title.txt
where wt >nul 2>nul
if %errorlevel% neq 0 goto :sin_wt
echo   wt --title "!ETIQUETA!" --suppressApplicationTitle -d "%CD%" cmd /k !MUSECMD! --yolo
wt --title "!ETIQUETA!" --suppressApplicationTitle -d "%CD%" cmd /k !MUSECMD! --yolo
if %errorlevel% neq 0 goto :wt_fallo
echo   Listo. Trabaja en la pestana !ETIQUETA!.
exit /b 0
:wt_fallo
echo   AVISO: no se pudo abrir Windows Terminal. Pausa y sigo en esta ventana.
pause
:sin_wt
title !ETIQUETA!
echo   Abriendo !MUSECMD! aqui...
!MUSECMD! --yolo
