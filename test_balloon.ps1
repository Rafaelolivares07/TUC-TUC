Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.BalloonTipTitle = 'TUC TUC - Deploy Listo'
$n.BalloonTipText = 'Commit 23e2dcf ya esta en produccion - prueba OK'
$n.Visible = $true
$n.ShowBalloonTip(6000)
Start-Sleep 7
$n.Dispose()
