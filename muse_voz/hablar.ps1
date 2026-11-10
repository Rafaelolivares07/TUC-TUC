param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$txt,
    [Parameter(Position=1)]
    [string]$voz = 'es-CO-SalomeNeural',
    [Parameter(Position=2)]
    [string]$vol = '+50%'
)
# Voz de Muse en un solo paso: sintetiza y reproduce.
# Un mp3 único por mensaje (nadie pisa el archivo ajeno); el turno entre
# terminales lo ponen habla_edge.py (sintetizar) y reproducir.ps1 (sonar).
$mp3 = Join-Path $env:TEMP ("muse_voz_{0}_{1}.mp3" -f $PID, [DateTime]::Now.Ticks)
try {
    & C:\Tools\Python313\python.exe (Join-Path $PSScriptRoot 'habla_edge.py') $txt $mp3 $voz $vol
    if (-not (Test-Path $mp3)) { exit 1 }
    & (Join-Path $PSScriptRoot 'reproducir.ps1') $mp3
} finally {
    Remove-Item $mp3 -Force -ErrorAction SilentlyContinue
}
