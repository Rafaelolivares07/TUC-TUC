param(
    [string]$Cliente = "lenovo"
)

$BASE  = "https://github.com/Rafaelolivares07/TUC-TUC/releases/download/interfases"
$DEST  = "C:\S.A.R\ACTUALIZACIONES\INTERFASES"
$STARTUP = [Environment]::GetFolderPath("Startup")

Write-Host "=== SAR Interfases - Instalacion ===" -ForegroundColor Cyan
Write-Host "Cliente : $Cliente"
Write-Host "Destino : $DEST"
Write-Host ""

# Crear carpeta destino
if (-not (Test-Path $DEST)) {
    New-Item -ItemType Directory -Force $DEST | Out-Null
    Write-Host "Carpeta creada: $DEST" -ForegroundColor Gray
}

# Detener daemon si corre
Stop-Process -Name "AlegraDaemon" -Force -ErrorAction SilentlyContinue

# Descargar EXEs
foreach ($exe in @("AlegraDaemon.exe", "ConfigurarAlegra.exe", "PROCESADOR_STAGING.EXE")) {
    Write-Host "Descargando $exe..." -NoNewline
    Invoke-WebRequest "$BASE/$exe" -OutFile "$DEST\${exe}_new" -UseBasicParsing
    Move-Item -Force "$DEST\${exe}_new" "$DEST\$exe"
    Write-Host " OK" -ForegroundColor Green
}

# VBS de arranque automatico (igual patron que AdminAgent.vbs)
$vbsPath = "$STARTUP\AlegraDaemon.vbs"
$vbsContent = "Set WshShell = CreateObject(""WScript.Shell"")`r`nWshShell.Run chr(34) & ""$DEST\AlegraDaemon.exe"" & chr(34), 0, False`r`n"
[System.IO.File]::WriteAllText($vbsPath, $vbsContent, [System.Text.Encoding]::Default)
Write-Host "VBS startup creado: $vbsPath" -ForegroundColor Green

# Acceso directo en escritorio para ConfigurarAlegra
$escritorio = [Environment]::GetFolderPath("Desktop")
$lnkPath = "$escritorio\Alegra - Configuracion.lnk"
$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnkPath)
$sc.TargetPath = "$DEST\ConfigurarAlegra.exe"
$sc.WorkingDirectory = $DEST
$sc.Description = "Configuracion interfaz Alegra"
$sc.Save()
Write-Host "Acceso directo creado en escritorio" -ForegroundColor Green

# Iniciar daemon ahora
Write-Host "Iniciando AlegraDaemon..." -NoNewline
Start-Process "$DEST\AlegraDaemon.exe"
Write-Host " OK" -ForegroundColor Green

Write-Host ""
Write-Host "=== Instalacion completada ===" -ForegroundColor Green
Write-Host "Abrir 'Alegra - Configuracion' en el escritorio para configurar."
