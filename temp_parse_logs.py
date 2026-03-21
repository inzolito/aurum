import re

log_path = 'c:/www/Aurum/bot_live.log'
try:
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    # We want to find the last occurrence of NLPWorker or GERENTE outputs before the crash
    meaningful_lines = []
    for line in lines[-20000:]: # check last 20k lines
        if 'telegram.error' in line or 'getUpdates' in line or 'raise exception' in line or 'site-packages' in line:
            continue
        meaningful_lines.append(line.strip())
        
    print("--- LAST 100 MEANINGFUL LOG LINES ---")
    for line in meaningful_lines[-100:]:
        print(line)
        
except Exception as e:
    print(f"Error: {e}")
