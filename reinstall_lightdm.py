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

print("Conectando al Vaio para reinstalar y configurar LightDM...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(ip, username=username, password=password, timeout=10)

chan = ssh.invoke_shell()
time.sleep(1)

def run_root_command(cmd, wait_time=2, max_wait=300):
    print(f"\n[Root]: {cmd}")
    chan.send(cmd + '\n')
    
    t_start = time.time()
    output = ""
    while time.time() - t_start < max_wait:
        if chan.recv_ready():
            chunk = chan.recv(8192).decode('utf-8', errors='replace')
            output += chunk
            safe_print(chunk)
            if "root@VAIODEBIAN" in chunk or "root@vaio" in chunk or "# " in chunk[-10:]:
                break
        time.sleep(wait_time)
    return output

# Elevate
chan.send('su -\n')
time.sleep(1)
chan.recv(1024)
chan.send(root_password + '\n')
time.sleep(2)
chan.recv(1024)

# 1. Reinstalar lightdm para forzar la creacion del usuario del sistema lightdm
run_root_command("apt-get install --reinstall -y lightdm", wait_time=3, max_wait=300)

# 2. Habilitar y arrancar de nuevo
run_root_command("systemctl enable lightdm")
run_root_command("systemctl restart lightdm")

# 3. Ver estado de lightdm
run_root_command("systemctl status lightdm --no-pager")

ssh.close()
print("=== REINSTALACION FINALIZADA ===")
