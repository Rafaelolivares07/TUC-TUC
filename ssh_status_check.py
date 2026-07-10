import paramiko
import sys

ip = '192.168.1.15'
username = 'kiosco'
password = 'rafaelolivares07'

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password, timeout=10)
    
    stdin, stdout, stderr = ssh.exec_command('grep -E "lightdm|kiosco" /etc/passwd')
    print("PASSWD USERS:")
    print(stdout.read().decode())
    
    ssh.close()
except Exception as e:
    print("Connection failed:", e)
