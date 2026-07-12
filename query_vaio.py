import paramiko
import sys

ip = '192.168.1.15'
username = 'kiosco'
password = 'rafaelolivares07'

def run_ssh_commands(commands):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, timeout=10)
        
        for cmd in commands:
            print(f"\n--- Running: {cmd} ---")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode('utf-8', errors='replace')
            err = stderr.read().decode('utf-8', errors='replace')
            if out:
                print(out)
            if err:
                print(f"Error output:\n{err}")
        
        ssh.close()
    except Exception as e:
        print("SSH Connection failed:", e)

commands = [
    "df -h",
    "free -h",
    "rfkill list",
    "systemctl status bluetooth || service bluetooth status",
    "hciconfig -a || lsusb",
    "bluetoothctl show"
]

run_ssh_commands(commands)
