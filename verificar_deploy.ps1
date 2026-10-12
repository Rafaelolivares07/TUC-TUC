param([string]$esperado)
$max = 20
for ($i = 1; $i -le $max; $i++) {
  try {
    $r = Invoke-RestMethod -Uri 'https://admin.tuc-tuc.co/api/version' -TimeoutSec 20
    $vivo = $r.commit
    Write-Host "  Intento $i/$max - servidor en: $vivo (esperado: $esperado)"
    if ($vivo -eq $esperado) {
      Write-Host ""
      Write-Host "OK - PRODUCCION ACTUALIZADA al commit $vivo"
      Write-Host "Ya puedes probar el cambio en el navegador."
      exit 0
    }
  } catch {
    Write-Host "  Intento $i/$max - sin respuesta, reintentando..."
  }
  Start-Sleep -Seconds 15
}
Write-Host ""
Write-Host "X El servidor no actualizo despues de 5 minutos."
Write-Host "El publicador automatico (watcher) puede estar detenido."
Write-Host "Avisale a Merlin con este mensaje: WATCHER CAIDO, commit esperado $esperado"
exit 1
