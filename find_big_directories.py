import os
import sys

def get_dir_size(path):
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_dir_size(entry.path)
    except Exception:
        pass
    return total

print("Checking root directories size on C:\\...")
root_dirs = ["C:\\Users", "C:\\Program Files", "C:\\Program Files (x86)", "C:\\ProgramData", "C:\\Windows"]
for d in root_dirs:
    if os.path.exists(d):
        size = get_dir_size(d)
        print(f"{d}: {round(size / (1024**3), 2)} GB")

# Also check other top level items
try:
    for entry in os.scandir("C:\\"):
        if entry.is_dir(follow_symlinks=False) and entry.path not in root_dirs:
            # check if it starts with $ or is System Volume Information
            if not entry.name.startswith("$") and entry.name != "System Volume Information":
                size = get_dir_size(entry.path)
                if size > 1024**2: # > 1MB
                    print(f"{entry.path}: {round(size / (1024**3), 2)} GB")
except Exception as e:
    print(f"Error reading root: {e}")
