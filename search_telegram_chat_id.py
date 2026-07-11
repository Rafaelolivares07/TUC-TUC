import os

def search_files(directory):
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                if 'telegram_chat_id' in content:
                    print(f"File: {path}")
                    for i, line in enumerate(content.split('\n')):
                        if 'telegram_chat_id' in line:
                            print(f"  Line {i+1}: {line.strip()}")

search_files(r"C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app")
