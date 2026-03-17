# presencia_heartbeat.ps1
# Envia heartbeat de presencia al servidor TUC TUC cada 2 minutos.
# Detecta inactividad real del usuario (mouse/teclado) via GetLastInputInfo de Win32.
# URL: /api/domotica/heartbeat?token=TOKEN&idle=SEGUNDOS
#
# Arranque: iniciado por iniciar_tuctuc.ps1 en background sin ventana.

$SERVER  = "https://tuc-tuc.onrender.com"
$TOKEN   = "tuctuc-hb-2026"
$INTERVALO_SEG = 120   # cada 2 minutos

# ── Función Win32: obtener segundos desde última actividad de teclado/mouse ──
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class IdleTimer {
    [DllImport("user32.dll")]
    static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);
    [StructLayout(LayoutKind.Sequential)]
    struct LASTINPUTINFO {
        public uint cbSize;
        public uint dwTime;
    }
    public static int GetIdleSeconds() {
        LASTINPUTINFO info = new LASTINPUTINFO();
        info.cbSize = (uint)Marshal.SizeOf(info);
        GetLastInputInfo(ref info);
        return (int)((Environment.TickCount - info.dwTime) / 1000);
    }
}
"@

Write-Host "[heartbeat] Iniciado. Reportando cada $INTERVALO_SEG segundos a $SERVER"

while ($true) {
    try {
        $idle = [IdleTimer]::GetIdleSeconds()
        $url  = "$SERVER/api/domotica/heartbeat?token=$TOKEN&idle=$idle"
        $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15 -ErrorAction Stop
        Write-Host "[heartbeat] idle=$idle s — activo=$($resp.activo) — $(Get-Date -Format 'HH:mm:ss')"
    } catch {
        Write-Host "[heartbeat] Error: $_"
    }
    Start-Sleep -Seconds $INTERVALO_SEG
}
