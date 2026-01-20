#!/usr/bin/env python3
"""Check for duplicate characters in the data"""
import json
from pathlib import Path
from collections import Counter

# Calculate the same path as app.py
# File is in backend/tests/, so go up to backend/, then up to chinese_chr_app/chinese_chr_app/
_backend_dir = Path(__file__).resolve().parent.parent  # backend/
BASE_DIR = _backend_dir.parent  # chinese_chr_app/chinese_chr_app/
CHARACTERS_JSON = BASE_DIR / "data" / "characters.json"

with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
    data = json.load(f)

chars = [c.get('Character', '').strip() for c in data]
char_counts = Counter(chars)
duplicates = {char: count for char, count in char_counts.items() if count > 1}

print(f"Total entries in JSON: {len(data)}")
print(f"Unique characters: {len(set(chars))}")
print(f"Duplicate characters: {len(duplicates)}")

if duplicates:
    print(f"\nDuplicate characters found:")
    for char, count in duplicates.items():
        print(f"  '{char}': appears {count} times")
        # Show which entries have this character
        indices = [i for i, c in enumerate(data) if c.get('Character', '').strip() == char]
        print(f"    At indices: {indices}")
        for idx in indices:
            entry = data[idx]
            print(f"      - Index {idx}: custom_id={entry.get('custom_id')}, Index={entry.get('Index')}")
else:
    print("\nNo duplicate characters found!")
