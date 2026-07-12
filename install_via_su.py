import paramiko
import time

ip = '192.168.1.4'
username = 'kiosco'
password = 'rafaelolivares07'

def run_su_command(cmd_to_run):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, timeout=10)
        
        # Invoke an interactive shell session
        channel = ssh.invoke_shell()
        time.sleep(1)
        
        # Read initial banner
        resp = channel.recv(9999).decode('utf-8', errors='replace')
        print(resp)
        
        # Send su command
        channel.send("su -\n")
        time.sleep(1)
        
        resp = channel.recv(9999).decode('utf-8', errors='replace')
        print(resp)
        
        # Send root password (assuming same as kiosco)
        channel.send(password + "\n")
        time.sleep(2)
        
        resp = channel.recv(9999).decode('utf-8', errors='replace')
        print(resp.replace(password, '******'))
        
        if '#' in resp or 'root@' in resp:
            print("Successfully logged in as ROOT!")
            # Run the installation command
            channel.send(cmd_to_run + "\n")
            
            # Wait for execution (could take a while, let's wait 30 seconds and check output periodically)
            for _ in range(30):
                time.sleep(2)
                if channel.recv_ready():
                    out = channel.recv(9999).decode('utf-8', errors='replace')
                    print(out)
                else:
                    # check if the prompt is back
                    pass
        else:
            print("Failed to switch to root. Authentication failed or su prompted differently.")
            
        channel.close()
        ssh.close()
    except Exception as e:
        print("Error:", e)

run_su_command("apt-get update && apt-get install -y pulseaudio-module-bluetooth && systemctl restart bluetooth")
