import paramiko
import socket
import sys

username = 'kiosco'
password = 'rafaelolivares07'

def try_ssh(ip):
    try:
        # First check port 22
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        result = sock.connect_ex((ip, 22))
        sock.close()
        if result != 0:
            return False
            
        # Try actual SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, timeout=2)
        ssh.close()
        return True
    except Exception:
        return False

print("Scanning for VAIO SSH on local network...")
found = []
for i in range(1, 40):
    ip = f"192.168.1.{i}"
    if try_ssh(ip):
        print(f"FOUND VAIO AT: {ip}")
        found.append(ip)

if not found:
    print("VAIO not found on 192.168.1.1-40. Let's check ARP or larger range.")
else:
    print(f"Discovery complete. Found IPs: {found}")
