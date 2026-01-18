#!/usr/bin/env python3
"""Fix character data - change 報 to 报"""
import json
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent
BASE_DIR = _backend_dir.parent.parent
CHARACTERS_JSON = BASE_DIR / "data" / "characters.json"

# Load data
with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find and fix
found = False
for char in data:
    if char.get('Character', '') == '報':
        print(f"Found 報 at Index {char.get('Index')}, custom_id {char.get('custom_id')}")
        char['Character'] = '报'
        print(f"Changed to: 报")
        found = True
        break

if found:
    # Save back
    with open(CHARACTERS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✓ File updated successfully")
    
    # Verify
    with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
        data_check = json.load(f)
    char_check = next((c for c in data_check if c.get('Character', '') == '报'), None)
    if char_check:
        print(f"✓ Verified: 报 found at Index {char_check.get('Index')}")
    else:
        print("✗ Verification failed")
else:
    print("✗ Character 報 not found in data")
