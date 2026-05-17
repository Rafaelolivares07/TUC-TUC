param(
    [string]$Cliente  = "lenovo",
    [string]$Nombre   = "Oficina lenovo"
)

$BASE = "https://github.com/Rafaelolivares07/TUC-TUC/releases/download/agentes"
$DEST = "C:\S.A.R\actualizaciones\agentes"

Write-Host "=== SAR Agentes — Actualizacion ===" -ForegroundColor Cyan
Write-Host "Cliente  : $Cliente"
Write-Host "Nombre   : $Nombre"
Write-Host "Destino  : $DEST"
Write-Host ""

# Descargar EXEs
foreach ($exe in @("AdminAgent.exe", "SarReportes.exe")) {
    Write-Host "Descargando $exe..." -NoNewline
    Invoke-WebRequest "$BASE/$exe" -OutFile "$DEST\${exe}_new" -UseBasicParsing
    Write-Host " OK" -ForegroundColor Green
}

# Detener agentes
Write-Host "Deteniendo agentes..."
Stop-Process -Name "AdminAgent"  -Force -ErrorAction SilentlyContinue
Stop-Process -Name "SarReportes" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Reemplazar EXEs
Write-Host "Reemplazando ejecutables..."
Move-Item -Force "$DEST\AdminAgent.exe_new"  "$DEST\AdminAgent.exe"
Move-Item -Force "$DEST\SarReportes.exe_new" "$DEST\SarReportes.exe"

# Escribir ini
Write-Host "Configurando ini..."
$ini = "[agent]`r`nnombre = $Nombre`r`ncliente_id = $Cliente`r`n"
[System.IO.File]::WriteAllText("$DEST\admin_agent.ini", $ini, [System.Text.Encoding]::Default)

Write-Host "--- Contenido ini ---" -ForegroundColor Yellow
Get-Content "$DEST\admin_agent.ini"
Write-Host "---------------------" -ForegroundColor Yellow

# Reiniciar agentes
Write-Host "Reiniciando agentes..."
Start-Process "$DEST\AdminAgent.exe"  -ArgumentList "--cliente $Cliente"
Start-Process "$DEST\SarReportes.exe"

Write-Host ""
Write-Host "=== Actualizacion completada ===" -ForegroundColor Green