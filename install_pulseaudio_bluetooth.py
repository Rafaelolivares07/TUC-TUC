import paramiko
import sys

ip = '192.168.1.4'
username = 'kiosco'
password = 'rafaelolivares07'

def run_sudo_commands(commands):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, timeout=20)
        
        for cmd in commands:
            print(f"\n--- Running (sudo): {cmd} ---")
            stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
            
            # Send password when prompted
            stdin.write(password + '\n')
            stdin.flush()
            
            out = stdout.read().decode('utf-8', errors='replace')
            safe_out = out.encode('ascii', errors='replace').decode('ascii')
            
            if safe_out:
                # Remove password prompt output for safety/cleanliness
                clean_out = safe_out.replace(password, '******')
                print(clean_out)
                
        ssh.close()
        print("Sudo commands executed successfully.")
    except Exception as e:
        print("SSH Connection failed:", e)

commands = [
    "sudo -S apt-get update",
    "sudo -S apt-get install -y pulseaudio-module-bluetooth",
    "pulseaudio -k",
    "sudo -S systemctl restart bluetooth"
]

run_sudo_commands(commands)
