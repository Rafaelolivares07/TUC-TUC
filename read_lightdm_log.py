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
chan.recv(4096)
chan.send(root_password + '\n')
time.sleep(2)
chan.recv(4096)

# Read lightdm.log
print("=== /var/log/lightdm/lightdm.log ===")
chan.send('tail -n 40 /var/log/lightdm/lightdm.log\n')
time.sleep(2)
safe_print(chan.recv(8192).decode('utf-8', errors='replace'))

# Read x-0.log
print("\n=== /var/log/lightdm/x-0.log ===")
chan.send('tail -n 40 /var/log/lightdm/x-0.log\n')
time.sleep(2)
safe_print(chan.recv(8192).decode('utf-8', errors='replace'))

ssh.close()
