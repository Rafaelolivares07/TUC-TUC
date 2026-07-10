import paramiko
import time
import sys

ip = '192.168.1.15'
username = 'kiosco'
password = 'rafaelolivares07'
root_password = 'grandesventas99'

def safe_print(text):
    try:
        sys.stdout.write(text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
    except Exception:
        sys.stdout.write(text.encode('ascii', errors='replace').decode('ascii'))
    sys.stdout.flush()

print("Conectando al Vaio...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(ip, username=username, password=password, timeout=10)

chan = ssh.invoke_shell()
time.sleep(1)

def run_root_command(cmd, wait_time=2):
    print(f"\n[Root]: {cmd}")
    chan.send(cmd + '\n')
    time.sleep(wait_time)
    if chan.recv_ready():
        resp = chan.recv(4096).decode('utf-8', errors='replace')
        safe_print(resp)

# Elevate
chan.send('su -\n')
time.sleep(1)
if chan.recv_ready():
    safe_print(chan.recv(1024).decode('utf-8', errors='replace'))
chan.send(root_password + '\n')
time.sleep(2)
if chan.recv_ready():
    safe_print(chan.recv(1024).decode('utf-8', errors='replace'))

# Check
chan.send('whoami\n')
time.sleep(1)
check_resp = chan.recv(1024).decode('utf-8', errors='replace')
if 'root' not in check_resp:
    print("ERROR: No se pudo ingresar como root.")
    ssh.close()
    sys.exit(1)

# 1. Configurar logind.conf para desactivar la suspension al cerrar la tapa de la pantalla
logind_conf_changes = """
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
"""
# Comentamos las lineas viejas de HandleLidSwitch y agregamos las nuevas
run_root_command("sed -i 's/#HandleLidSwitch=/HandleLidSwitch=ignore/g' /etc/systemd/logind.conf")
run_root_command("sed -i 's/#HandleLidSwitchExternalPower=/HandleLidSwitchExternalPower=ignore/g' /etc/systemd/logind.conf")
run_root_command("sed -i 's/#HandleLidSwitchDocked=/HandleLidSwitchDocked=ignore/g' /etc/systemd/logind.conf")
# Por si acaso no existieran comentadas, las agregamos al final si no estan
run_root_command("grep -q 'HandleLidSwitch=ignore' /etc/systemd/logind.conf || echo 'HandleLidSwitch=ignore' >> /etc/systemd/logind.conf")
run_root_command("grep -q 'HandleLidSwitchExternalPower=ignore' /etc/systemd/logind.conf || echo 'HandleLidSwitchExternalPower=ignore' >> /etc/systemd/logind.conf")
run_root_command("grep -q 'HandleLidSwitchDocked=ignore' /etc/systemd/logind.conf || echo 'HandleLidSwitchDocked=ignore' >> /etc/systemd/logind.conf")

# Reiniciar logind para aplicar los cambios de tapa
run_root_command("systemctl restart systemd-logind")

# 2. Habilitar e iniciar LightDM (la interfaz grafica)
run_root_command("systemctl enable lightdm")
run_root_command("systemctl start lightdm")

# 3. Verificar si el agente de TucTuc inicio correctamente
run_root_command("systemctl status adminagent.service")

ssh.close()
print("=== CONFIGURACION DE INTERFAZ Y TAPA COMPLETADAS CON EXITO ===")
