# presencia_apagado.ps1
# Se ejecuta al apagar/cerrar sesion Windows.
# Envia heartbeat con idle=99999 para que el servidor marque laptop_last_seen=NULL
# y los switches reaccionen inmediatamente (ej: apagar ventilador de oficina).

$SERVER = "https://tuc-tuc.onrender.com"
$TOKEN  = "tuctuc-hb-2026"
$URL    = "$SERVER/api/domotica/heartbeat?token=$TOKEN&idle=99999"

try {
    $resp = Invoke-RestMethod -Uri $URL -Method Get -TimeoutSec 10 -ErrorAction Stop
    Write-Host "[apagado] Presencia limpiada OK — activo=$($resp.activo)"
} catch {
    Write-Host "[apagado] Error al limpiar presencia: $_"
}
