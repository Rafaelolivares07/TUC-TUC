param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$mp3,
    [switch]$deleteAfter
)

if (-not (Test-Path $mp3)) { exit 0 }

$lockDir = Join-Path $env:TEMP "tuctuc_voz_playing.lock"
$waited = 0
while ((Test-Path $lockDir) -and $waited -lt 15) {
    Start-Sleep -Milliseconds 250
    $waited += 0.25
}

# Marcar inicio de turno de audio
New-Item -ItemType Directory -Path $lockDir -Force -ErrorAction SilentlyContinue | Out-Null

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
        while ($wmp.playState -eq 3) {
            Start-Sleep -Milliseconds 150
        }
        $wmp.close()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wmp) | Out-Null
        $played = $true
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
    Start-Sleep -Milliseconds 250
} finally {
    Remove-Item -Path $lockDir -Force -Recurse -ErrorAction SilentlyContinue
    if ($deleteAfter -and (Test-Path $mp3)) {
        Remove-Item $mp3 -Force -ErrorAction SilentlyContinue
    }
}
