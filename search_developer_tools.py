import os

user_dir = r"C:\Users\RAFAEL OLIVARES"
print("Scanning user directory for gradle/android/sdk folders...")
for name in os.listdir(user_dir):
    path = os.path.join(user_dir, name)
    if os.path.isdir(path):
        lower_name = name.lower()
        if 'gradle' in lower_name or 'android' in lower_name or 'sdk' in lower_name or name.startswith('.'):
            print(f"  {name}")
