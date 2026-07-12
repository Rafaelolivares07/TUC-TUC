import os

def search_files(directory):
    for root, dirs, files in os.walk(directory):
        for f in files:
            path = os.path.join(root, f)
            # skip node_modules, build, git
            if 'node_modules' in path or '.git' in path or 'build' in path:
                continue
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                if 'rockola' in content.lower():
                    print(f"Match found in: {path}")
                    for i, line in enumerate(content.split('\n')):
                        if 'rockola' in line.lower():
                            print(f"  Line {i+1}: {line.strip()}")
            except Exception:
                pass

search_files(r"C:\Users\RAFAEL OLIVARES\Documents\TucTucV2")
