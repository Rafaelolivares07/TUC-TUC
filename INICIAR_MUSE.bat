@echo off
chcp 65001 >nul
REM ============================================================
REM  INICIAR_MUSE.bat - Arranque diario de Muse (TUC TUC V2)
REM  Uso: doble clic cada dia. Deja la terminal lista e invoca muse.
REM  Idempotente. Directorio de trabajo: raiz (AGENTS.md + V2 + docs).
REM ============================================================
setlocal EnableDelayedExpansion
title Muse - arranque diario
cd /d "C:\Users\RAFAEL OLIVARES" || (echo No se pudo ir a la raiz & pause & exit /b 1)
set "V2=C:\Users\RAFAEL OLIVARES\Documents\TucTucV2"
set "DOCS=C:\Users\RAFAEL OLIVARES\Documents\docs"
set "CREDS=C:\Tools\muse-git-credentials"

echo [1/6] Directorio: %CD%
if not exist "%V2%" echo AVISO: falta %V2%
if not exist "%DOCS%" echo AVISO: falta %DOCS%

echo [2/6] Git identidad + config repo V2
for /f "delims=" %%u in ('git config --global user.name 2^>nul') do echo   user: %%u
git -C "%V2%" config http.sslbackend openssl >nul
git -C "%V2%" config --get-all credential.helper 2>nul | findstr /C:"muse-git-credentials" >nul || git -C "%V2%" config credential.helper "store --file C:/Tools/muse-git-credentials" >nul
echo   sslbackend + credential-helper OK

echo [3/6] PAT para push solo de Muse
if exist "%CREDS%" echo   credenciales OK
if exist "%CREDS%" goto :pat_ok
echo   Falta %CREDS% - Muse no podra pushear solo (pedira aprobacion).
echo   Crea un PAT fine-grained en github.com: repo TUC-TUC, Contents read+write.
powershell -NoProfile -Command "$s=Read-Host 'Pega el PAT (no se muestra, Enter para omitir)' -AsSecureString; $p=[Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)); if($p.Length -lt 10){exit 1}; 'https://Rafaelolivares07:'+$p+'@github.com' | Out-File -FilePath 'C:\Tools\muse-git-credentials' -Encoding ascii -NoNewline"
if %errorlevel% equ 0 (echo   PAT guardado.) else (echo   Omitido. Re-ejecuta este script cuando tengas el PAT.)
:pat_ok

echo [4/6] Fetch + estado V2
git -C "%V2%" fetch origin
set N=0
for /f "delims=" %%b in ('git -C "%V2%" status -sb 2^>nul') do (
  set /a N+=1
  if !N! leq 12 echo   %%b
)
if !N! gtr 12 echo   ... (!N! lineas en total, ver resto con git status)

echo [5/6] Python global + CLI muse
C:\Tools\Python313\python.exe --version 2>&1
set "MUSECMD="
for %%c in (muse muse-code) do (
  if not defined MUSECMD (
    where %%c >nul 2>nul && set "MUSECMD=%%c"
  )
)
if defined MUSECMD (echo   CLI: !MUSECMD!) else (echo   AVISO: 'muse' no esta en PATH. Agregalo o abrelo desde su carpeta.)

echo [6/6] Acceso directo en Escritorio
set "LNK=%USERPROFILE%\Desktop\INICIAR MUSE.lnk"
if exist "%LNK%" echo   acceso OK
if exist "%LNK%" goto :lnk_ok
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($env:USERPROFILE+'\Desktop\INICIAR MUSE.lnk'); $s.TargetPath='C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\INICIAR_MUSE.bat'; $s.WorkingDirectory='C:\Users\RAFAEL OLIVARES'; $s.Save()"
if %errorlevel% equ 0 (echo   acceso creado.) else (echo   no se pudo crear acceso.)
:lnk_ok

echo.
if not defined MUSECMD (pause & exit /b 1)
echo Listo. Invocando !MUSECMD! desde %CD% ...
!MUSECMD!
