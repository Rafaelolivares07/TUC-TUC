param(
    [string]$Cliente  = "lenovo",
    [string]$Nombre   = "Oficina lenovo"
)

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$BASE = "https://github.com/Rafaelolivares07/TUC-TUC/releases/download/agentes"
$DEST = "C:\S.A.R\actualizaciones\agentes"

Write-Host "=== SAR Agentes - Actualizacion ===" -ForegroundColor Cyan
Write-Host "Cliente  : $Cliente"
Write-Host "Nombre   : $Nombre"
Write-Host "Destino  : $DEST"
Write-Host ""

# Descargar EXEs
New-Item -ItemType Directory -Force $DEST | Out-Null
foreach ($exe in @("AdminAgent.exe", "SarReportes.exe")) {
    Write-Host "Descargando $exe..."
    $dest_tmp = "$DEST\${exe}_new"
    & curl.exe -L --retry 3 --retry-delay 2 --silent --show-error -o $dest_tmp "$BASE/$exe"
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR curl $exe (codigo $LASTEXITCODE)" -ForegroundColor Red; exit 1 }
    Write-Host "$exe OK" -ForegroundColor Green
}

# Detener agentes
Write-Host "Deteniendo agentes..."
Stop-Process -Name "AdminAgent"  -Force -ErrorAction SilentlyContinue
Stop-Process -Name "SarReportes" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

# Reemplazar EXEs
Write-Host "Reemplazando ejecutables..."
foreach ($exe in @("AdminAgent.exe", "SarReportes.exe")) {
    Remove-Item -Force "$DEST\$exe" -ErrorAction SilentlyContinue
    Move-Item "$DEST\${exe}_new" "$DEST\$exe"
}

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
