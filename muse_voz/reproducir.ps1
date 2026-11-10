param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$mp3,
    [switch]$deleteAfter
)

if (-not (Test-Path $mp3)) { exit 0 }

$gapSec = 15
$mutexName = 'Local\TucTucVoz'
# Higiene: candado de directorio de la versión vieja (tenía carrera, ya no se usa)
Remove-Item -Path (Join-Path $env:TEMP "tuctuc_voz_playing.lock") -Force -Recurse -ErrorAction SilentlyContinue

# Turno de audio entre terminales: mutex de sesión (atómico; se libera solo si muere el dueño)
$mutex = [System.Threading.Mutex]::new($false, $mutexName)
$adquirido = $false
try {
    $adquirido = $mutex.WaitOne(300000)
} catch [System.Threading.AbandonedMutexException] {
    $adquirido = $true
}
if (-not $adquirido) {
    Write-Warning "muse_voz: turno de audio ocupado 5 min, reproduzco de todos modos"
}

try {
    $played = $false
    try {
        $wmp = New-Object -ComObject WMPlayer.OCX
        $wmp.settings.volume = 100
        $wmp.URL = $mp3
        $wmp.controls.play()
        Start-Sleep -Milliseconds 300
        $timeout = 0
        while ($wmp.playState -ne 3 -and $timeout -lt 25) {
            Start-Sleep -Milliseconds 100
            $timeout++
        }
        $played = ($wmp.playState -eq 3)
        while ($wmp.playState -eq 3) {
            Start-Sleep -Milliseconds 150
        }
        $wmp.close()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wmp) | Out-Null
    } catch {
        $played = $false
    }

    if (-not $played) {
        Add-Type -AssemblyName presentationCore
        $m = New-Object System.Windows.Media.MediaPlayer
        $m.Volume = 1
        $m.Open($mp3)
        $m.Play()
        Start-Sleep -Milliseconds 500
        $n = 0
        while (-not $m.NaturalDuration.HasTimeSpan -and $n -lt 25) {
            Start-Sleep -Milliseconds 150
            $n++
        }
        if ($m.NaturalDuration.HasTimeSpan) {
            Start-Sleep -Seconds ($m.NaturalDuration.TimeSpan.TotalSeconds + 0.3)
        }
        $m.Close()
    }
    Start-Sleep -Seconds $gapSec
} finally {
    if ($adquirido) {
        try { $mutex.ReleaseMutex() } catch { }
    }
    try { $mutex.Dispose() } catch { }
    if ($deleteAfter -and (Test-Path $mp3)) {
        Remove-Item $mp3 -Force -ErrorAction SilentlyContinue
    }
}
