param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$mp3,
    [switch]$deleteAfter
)

if (-not (Test-Path $mp3)) { exit 0 }

# Cola de turnos global para evitar que se pisen los audios
# entre diferentes agentes o entre terminales simultaneas
$mutexName = "TucTuc_Audio_Turno_Mutex"
$mutex = $null
$hasLock = $false

try {
    $mutex = New-Object System.Threading.Mutex($false, $mutexName)
    try {
        # Esperar hasta 2 minutos para tomar el turno de voz
        $hasLock = $mutex.WaitOne(120000)
    } catch [System.Threading.AbandonedMutexException] {
        # El proceso previo termino sin liberar el mutex; recuperamos el control
        $hasLock = $true
    }

    if ($hasLock) {
        Add-Type -AssemblyName presentationCore
        $m = New-Object System.Windows.Media.MediaPlayer
        $m.Volume = 1
        $m.Open($mp3)
        $m.Play()
        Start-Sleep -Milliseconds 800
        $n = 0
        while (-not $m.NaturalDuration.HasTimeSpan -and $n -lt 30) {
            Start-Sleep -Milliseconds 200
            $n++
        }
        if ($m.NaturalDuration.HasTimeSpan) {
            Start-Sleep -Seconds ($m.NaturalDuration.TimeSpan.TotalSeconds + 0.3)
        }
        $m.Close()
        # Breve silencio de 400ms para separar oradores y dar claridad
        Start-Sleep -Milliseconds 400
    }
} finally {
    if ($hasLock -and $mutex -ne $null) {
        try { $mutex.ReleaseMutex() } catch {}
    }
    if ($mutex -ne $null) {
        $mutex.Dispose()
    }
    if ($deleteAfter -and (Test-Path $mp3)) {
        try { Remove-Item $mp3 -Force -ErrorAction SilentlyContinue } catch {}
    }
}
