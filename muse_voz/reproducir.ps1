$mp3 = $args[0]
Add-Type -AssemblyName presentationCore
$m = New-Object System.Windows.Media.MediaPlayer
$m.Volume = 1
$m.Open($mp3)
$m.Play()
Start-Sleep -Milliseconds 800
$n = 0
while (-not $m.NaturalDuration.HasTimeSpan -and $n -lt 25) { Start-Sleep -Milliseconds 200; $n++ }
if ($m.NaturalDuration.HasTimeSpan) { Start-Sleep -Seconds ($m.NaturalDuration.TimeSpan.TotalSeconds + 0.5) }
$m.Close()
