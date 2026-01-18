#!/usr/bin/env python3
"""Check if a specific character exists in the data"""
import json
import sys
from pathlib import Path

# Calculate the same path as app.py
_backend_dir = Path(__file__).resolve().parent
BASE_DIR = _backend_dir.parent.parent
CHARACTERS_JSON = BASE_DIR / "data" / "characters.json"

# Get character from command line or use default
search_char = sys.argv[1] if len(sys.argv) > 1 else "丛"

with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
    data = json.load(f)

chars = [c.get('Character', '').strip() for c in data]
print(f"Searching for character: '{search_char}'")
print(f"Total entries in JSON: {len(data)}")
print(f"Character exists: {search_char in chars}")

if search_char in chars:
    indices = [i for i, c in enumerate(data) if c.get('Character', '').strip() == search_char]
    print(f"Found at {len(indices)} location(s): {indices}")
    for idx in indices:
        entry = data[idx]
        print(f"\nEntry {idx}:")
        print(f"  custom_id: {entry.get('custom_id')}")
        print(f"  Index: {entry.get('Index')}")
        print(f"  Character: {entry.get('Character')}")
        print(f"  Pinyin: {entry.get('Pinyin')}")
        print(f"  Radical: {entry.get('Radical')}")
else:
    print(f"\nCharacter '{search_char}' NOT FOUND in the data")
    print(f"\nSample characters (first 20): {chars[:20]}")
    print(f"\nSample characters (last 20): {chars[-20:]}")
