Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Idle {
    [DllImport("user32.dll")]
    public static extern bool GetLastInputInfo(ref LASTINPUTINFO li);
    public struct LASTINPUTINFO {
        public uint cbSize;
        public uint dwTime;
    }
    public static int GetIdleSeconds() {
        LASTINPUTINFO li = new LASTINPUTINFO();
        li.cbSize = (uint)System.Runtime.InteropServices.Marshal.SizeOf(li);
        GetLastInputInfo(ref li);
        return (int)((Environment.TickCount - li.dwTime) / 1000);
    }
}
"@ -Language CSharp

$baseUrl = "https://admin.tuc-tuc.co/api/domotica/heartbeat?token=tuctuc-hb-2026"

# Al apagar/cerrar sesion: marcar ausente de inmediato
Register-EngineEvent PowerShell.Exiting -Action {
    try {
        Invoke-WebRequest -Uri "https://admin.tuc-tuc.co/api/domotica/heartbeat?token=tuctuc-hb-2026&idle=99999" -Method GET -TimeoutSec 8 -UseBasicParsing | Out-Null
    } catch {}
}

while ($true) {
    $inactivo = [Idle]::GetIdleSeconds()
    $url = "$baseUrl&idle=$inactivo"
    try {
        Invoke-WebRequest -Uri $url -Method GET -TimeoutSec 30 -UseBasicParsing | Out-Null
    } catch {}
    Start-Sleep -Seconds 60
}
