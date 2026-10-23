# Diagnóstico de Caídas por Memoria (OOM Killer) y Solución Recomendada

## 1. Historial de Caídas Detectadas en el Servidor AWS (EC2)
Al auditar los registros del kernel de Linux (`dmesg`), se encontraron los siguientes eventos en los que la aplicación se cayó/reinició forzosamente:

1. **Martes 13 de Octubre de 2026 - 12:18:39 PM**
   - **Evento:** `oom-kill` (Out of Memory)
   - **Proceso afectado:** `gunicorn` (PID 2586724)
   - **Consumo al momento de la caída:** ~896 MB de RAM
   - **Causa:** La memoria RAM física (1.9 GB total) llegó al 100% y, al no existir memoria Swap de amortiguación, el kernel de Linux mató el proceso de Gunicorn para evitar el bloqueo del sistema operativo.

2. **Martes 20 de Octubre de 2026 - 09:00:35 AM**
   - **Evento:** `systemd invoked oom-killer`
   - **Proceso afectado:** `gunicorn` (PID 3588343)
   - **Consumo al momento de la caída:** ~840 MB de RAM
   - **Causa:** Pico de concurrencia/procesamiento matutino sin margen de memoria libre.

---

## 2. Diagnóstico Técnico
- **RAM Física:** 1.9 GB (`t3.small`)
- **Swap configurado actualmente:** 0 B (Desactivado)
- **Disco disponible:** 1.8 GB libres (de 7.6 GB)
- **Comportamiento:** Cuando 3 workers de Gunicorn atienden peticiones simultáneas pesadas (reportes, sincronizaciones o consultas complejas), el consumo roza los 900 MB y el sistema agota la memoria libre, provocando el cierre abrupto del servicio.

---

## 3. Solución Recomendada (Costo $0 USD en AWS)
Cuando se decida aplicar la solución preventiva:

### Paso A: Activar Swap de 1 GB en Linux
Aprovecha 1 GB del disco duro existente (sin costos adicionales en AWS) para servir de colchón de seguridad ante picos:

```bash
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Paso B: Ajustar 'Swappiness' para no degradar rendimiento de disco
```bash
sudo sysctl vm.swappiness=15
echo 'vm.swappiness=15' | sudo tee -a /etc/sysctl.conf
```
*(Un swappiness de 15 le indica a Linux que solo use el Swap en situaciones críticas de emergencia, manteniendo la velocidad normal en RAM).*

---
*Documento registrado para auditoría y seguimiento del sistema TucTuc V2.*
