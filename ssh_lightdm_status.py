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

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(ip, username=username, password=password, timeout=10)

chan = ssh.invoke_shell()
time.sleep(1)
chan.send('su -\n')
time.sleep(1)
chan.recv(1024)
chan.send(root_password + '\n')
time.sleep(2)
chan.recv(1024)

# Run journalctl to inspect lightdm log
chan.send('journalctl -u lightdm --no-pager -n 30\n')
time.sleep(2)

resp = chan.recv(8192).decode('utf-8', errors='replace')
print("LIGHTDM LOGS:")
safe_print(resp)

ssh.close()
