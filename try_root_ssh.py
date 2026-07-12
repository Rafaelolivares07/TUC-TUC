import paramiko

ip = '192.168.1.4'
username = 'root'
password = 'rafaelolivares07'

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password, timeout=5)
    print("SSH Connection as root SUCCEEDED!")
    ssh.close()
except Exception as e:
    print("SSH Connection as root failed:", e)
