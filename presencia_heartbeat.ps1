# presencia_heartbeat.ps1
# Envia heartbeat de presencia al servidor TUC TUC cada 1 minuto.
# Detecta: idle (teclado/mouse combinado), movimiento de cursor (mouse),
#          audio activo (procesos media), ventana en primer plano.
# URL: /api/domotica/heartbeat?token=TOKEN&idle=N&mouse=0/1&audio=0/1&ventana=TITULO

$SERVER        = "https://tuc-tuc.onrender.com"
$TOKEN         = "tuctuc-hb-2026"
$INTERVALO_SEG = 60   # cada 1 minuto

# ── Win32: idle + cursor + foreground window ──────────────────────────────────
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class PC {
    // Idle (teclado + mouse combinado)
    [DllImport("user32.dll")]
    static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);
    [StructLayout(LayoutKind.Sequential)]
    struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    public static int GetIdleSeconds() {
        LASTINPUTINFO info = new LASTINPUTINFO();
        info.cbSize = (uint)System.Runtime.InteropServices.Marshal.SizeOf(info);
        GetLastInputInfo(ref info);
        return (int)((Environment.TickCount - info.dwTime) / 1000);
    }

    // Posicion del cursor
    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT lpPoint);
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X; public int Y; }
    public static POINT GetCursor() {
        POINT p; GetCursorPos(out p); return p;
    }

    // Ventana en primer plano
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    public static string GetActiveWindow() {
        IntPtr hwnd = GetForegroundWindow();
        if (hwnd == IntPtr.Zero) return "";
        StringBuilder sb = new StringBuilder(128);
        GetWindowText(hwnd, sb, 128);
        return sb.ToString();
    }
}
"@

# Procesos de media que indican audio activo
$MEDIA_PROCS = @('chrome','msedge','firefox','spotify','vlc','wmplayer',
                 'groove','mpc-hc','mpc-be','itunes','winamp','potplayer',
                 'mpv','obs64','obs32')

$lastCursorX = -1
$lastCursorY = -1

Write-Host "[heartbeat] Iniciado. Reportando cada $INTERVALO_SEG s a $SERVER"

# Al apagar/cerrar sesion: mandar idle=99999 para marcar ausente de inmediato
Register-EngineEvent PowerShell.Exiting -Action {
    try {
        Invoke-RestMethod -Uri "https://tuc-tuc.onrender.com/api/domotica/heartbeat?token=tuctuc-hb-2026&idle=99999&mouse=0&audio=0&ventana=apagado" -Method Get -TimeoutSec 8 -ErrorAction Stop
        Write-Host "[heartbeat] Presencia limpiada al salir"
    } catch {
        Write-Host "[heartbeat] No se pudo limpiar presencia al salir: $_"
    }
}

while ($true) {
    try {
        $idle = [PC]::GetIdleSeconds()

        # Mouse: el cursor cambio de posicion desde la ultima medicion?
        $cur   = [PC]::GetCursor()
        $mouse = if ($cur.X -ne $lastCursorX -or $cur.Y -ne $lastCursorY) { 1 } else { 0 }
        $lastCursorX = $cur.X
        $lastCursorY = $cur.Y

        # Audio: proceso de media con CPU > 0.3s (fue activo recientemente)
        $audio = 0
        $mediaActivos = Get-Process -ErrorAction SilentlyContinue | Where-Object {
            $MEDIA_PROCS -contains $_.Name.ToLower() -and $_.CPU -gt 0.3
        }
        if ($mediaActivos) { $audio = 1 }

        # Ventana activa (truncada a 60 chars)
        $ventana = [PC]::GetActiveWindow()
        if ($ventana.Length -gt 60) { $ventana = $ventana.Substring(0, 60) }
        $ventanaEnc = [System.Uri]::EscapeDataString($ventana)

        $url  = "$SERVER/api/domotica/heartbeat?token=$TOKEN&idle=$idle&mouse=$mouse&audio=$audio&ventana=$ventanaEnc"
        $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15 -ErrorAction Stop
        Write-Host "[heartbeat] idle=$idle mouse=$mouse audio=$audio ventana='$ventana' activo=$($resp.activo) $(Get-Date -Format 'HH:mm:ss')"
    } catch {
        Write-Host "[heartbeat] Error: $_"
    }
    Start-Sleep -Seconds $INTERVALO_SEG
}
