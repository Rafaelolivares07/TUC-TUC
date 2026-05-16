# instalar_sar.ps1
# Descarga AdminAgent.exe y SarReportes.exe desde GitHub
# Todo queda bajo C:\S.A.R\actualizaciones\agentes\
# Crea VBS de startup. No requiere Python.
#
# Uso:
#   irm URL | iex                          <- usa cliente "pilar" por defecto
#   & ([scriptblock]::Create((irm URL))) -Cliente lenovo   <- cliente personalizado

param(
    [string]$Cliente = "pilar",
    [string]$Nombre  = ""
)

$BASE_URL  = "https://github.com/Rafaelolivares07/TUC-TUC/releases/download/SarAgentes-v1.0"
$SAR_DIR   = "C:\S.A.R\actualizaciones\agentes"
$STARTUP   = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$CLIENTE   = $Cliente
if (-not $Nombre) { $Nombre = "Oficina $((Get-Culture).TextInfo.ToTitleCase($CLIENTE))" }
$LOG       = "$SAR_DIR\instalar_sar.log"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts $msg" | Out-File $LOG -Append -Encoding utf8
    Write-Host $msg
}

New-Item -ItemType Directory -Force -Path $SAR_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $STARTUP | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

Log "=== instalar_sar.ps1 iniciado ==="

# Descargar EXEs
foreach ($exe in @("AdminAgent.exe", "SarReportes.exe")) {
    $dest = "$SAR_DIR\$exe"
    Log "Descargando $exe..."
    try {
        Invoke-WebRequest -Uri "$BASE_URL/$exe" -OutFile $dest -UseBasicParsing
        $mb = [math]::Round((Get-Item $dest).Length / 1MB, 1)
        Log "OK $exe ($mb MB) -> $dest"
    } catch {
        Log "ERROR descargando $exe`: $_"
        exit 1
    }
}

# admin_agent.ini (solo si no existe)
$ini = "$SAR_DIR\admin_agent.ini"
if (-not (Test-Path $ini)) {
    [System.IO.File]::WriteAllText($ini, "[agent]`r`nnombre = $Nombre`r`n", $utf8NoBom)
    Log "OK admin_agent.ini creado ($Nombre)"
}

# server.ini (siempre — credenciales del servidor)
$serverIni = "$SAR_DIR\server.ini"
[System.IO.File]::WriteAllText($serverIni, "[aws]`r`nbase_url = https://admin.tuc-tuc.co`r`nusuario = rafael`r`npassword = grandesventas99`r`ncliente_id = $CLIENTE`r`n", $utf8NoBom)
Log "OK server.ini creado"

# VBS AdminAgent — ANSI sin BOM — corre EXE directo sin cmd wrapper
$agentExe = "C:\S.A.R\actualizaciones\agentes\AdminAgent.exe"
$vbsAgent = "Set WshShell = CreateObject(`"WScript.Shell`")`r`nWshShell.Run `"`"`"$agentExe`"`" --servidor https://admin.tuc-tuc.co --cliente $CLIENTE`", 0, False`r`n"
[System.IO.File]::WriteAllText("$STARTUP\AdminAgent.vbs", $vbsAgent, [System.Text.Encoding]::Default)
[System.IO.File]::WriteAllText("$SAR_DIR\AdminAgent.vbs", $vbsAgent, [System.Text.Encoding]::Default)
Log "OK AdminAgent.vbs en startup + copia en agentes\"

# VBS SarReportes — ANSI sin BOM — corre EXE directo sin cmd wrapper
$sarExe = "C:\S.A.R\actualizaciones\agentes\SarReportes.exe"
$vbsSar = "Set WshShell = CreateObject(`"WScript.Shell`")`r`nWshShell.Run `"`"`"$sarExe`"`"`", 0, False`r`n"
[System.IO.File]::WriteAllText("$STARTUP\SarReportes.vbs", $vbsSar, [System.Text.Encoding]::Default)
[System.IO.File]::WriteAllText("$SAR_DIR\SarReportes.vbs", $vbsSar, [System.Text.Encoding]::Default)
Log "OK SarReportes.vbs en startup + copia en agentes\"

# Eliminar VBS obsoletos
foreach ($old in @("AdministratorWeb.vbs")) {
    $p = "$STARTUP\$old"
    if (Test-Path $p) { Remove-Item $p -Force; Log "Eliminado $old obsoleto" }
}

Log "=== Instalacion completa. Reiniciar el PC para activar. ==="
Write-Host ""
Write-Host "Listo. Reinicia el PC para activar AdminAgent y SarReportes."
