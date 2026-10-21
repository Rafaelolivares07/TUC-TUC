import subprocess

commands = [
    "sudo timedatectl set-timezone America/Bogota",
    "sudo -u postgres psql -d tuctuc -c \"ALTER SYSTEM SET timezone TO 'America/Bogota';\"",
    "sudo -u postgres psql -d tuctuc -c \"SELECT pg_reload_conf();\"",
    "sudo -u postgres psql -d tuctuc -c \"SHOW timezone; SELECT NOW();\"",
    "timedatectl"
]

remote_cmd = " && ".join(commands)

res = subprocess.run([
    "ssh", "-i", r"C:\Users\RAFAEL OLIVARES\Documents\tuctuc-linux.pem",
    "ubuntu@18.217.231.167",
    remote_cmd
], capture_output=True, text=True)

print("STDOUT:\n", res.stdout)
print("STDERR:\n", res.stderr)
