#!/usr/bin/env python3
"""Check for dictionary markers in character data"""
import json
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent
BASE_DIR = _backend_dir.parent.parent
CHARACTERS_JSON = BASE_DIR / "extract_characters_using_ai" / "output" / "characters.json"

with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Checking for dictionary markers in character data...")
print(f"Total characters: {len(data)}\n")

dict_examples = []
for i, char in enumerate(data[:50]):  # Check first 50
    for field in ['Pinyin', 'Radical', 'Strokes', 'Structure', 'Sentence']:
        val = char.get(field, '')
        if isinstance(val, list):
            # Check each item in the list
            for item in val:
                if isinstance(item, str) and ' (dictionary)' in item:
                    dict_examples.append((i, field, item, 'list'))
        elif isinstance(val, str) and ' (dictionary)' in val:
            dict_examples.append((i, field, val, 'string'))

if dict_examples:
    print(f"Found {len(dict_examples)} dictionary markers in first 50 characters:")
    for idx, field, val, type_info in dict_examples[:5]:
        print(f"  Character {idx}, Field {field}: {val}")
else:
    print("No dictionary markers found in first 50 characters")
    print("Checking a wider sample...")
    for i, char in enumerate(data):
        for field in ['Pinyin', 'Radical', 'Strokes', 'Structure', 'Sentence']:
            val = char.get(field, '')
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and ' (dictionary)' in item:
                        dict_examples.append((i, field, item, 'list'))
                        break
            elif isinstance(val, str) and ' (dictionary)' in val:
                dict_examples.append((i, field, val, 'string'))
                break
        if len(dict_examples) >= 3:
            break
    
    if dict_examples:
        print(f"Found examples:")
        for idx, field, val, type_info in dict_examples:
            print(f"  Character {idx}, Field {field}: {val}")
    else:
        print("No dictionary markers found in the data")
