#!/usr/bin/env python3
"""Test script to verify character data can be loaded correctly"""
import json
import sys
from pathlib import Path

# Calculate the same path as app.py
_backend_dir = Path(__file__).resolve().parent
BASE_DIR = _backend_dir.parent.parent
CHARACTERS_JSON = BASE_DIR / "extract_characters_using_ai" / "output" / "characters.json"

def test_data_loading():
    """Test that character data loads correctly"""
    print("=" * 60)
    print("Testing Character Data Loading")
    print("=" * 60)
    
    print(f"\n1. Checking JSON file path...")
    print(f"   Path: {CHARACTERS_JSON}")
    print(f"   Exists: {CHARACTERS_JSON.exists()}")
    
    if not CHARACTERS_JSON.exists():
        print("\n❌ JSON file not found!")
        print(f"   Expected at: {CHARACTERS_JSON}")
        print(f"   Base directory: {BASE_DIR}")
        sys.exit(1)
    
    print("\n2. Loading character data...")
    try:
        with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
            characters_data = json.load(f)
        print(f"   ✓ Loaded {len(characters_data)} characters from JSON")
    except Exception as e:
        print(f"   ✗ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n3. Creating lookup dictionary...")
    character_lookup = {}
    for char in characters_data:
        char_key = char.get('Character', '').strip()
        if char_key and char_key not in character_lookup:
            character_lookup[char_key] = char
    
    print(f"   ✓ Created lookup dictionary with {len(character_lookup)} entries")
    
    print("\n4. Testing search for character '爸'...")
    test_char = "爸"
    if test_char in character_lookup:
        char_data = character_lookup[test_char]
        print(f"   ✓ Found character '{test_char}'")
        print(f"   ✓ Character ID: {char_data.get('custom_id', 'N/A')}")
        print(f"   ✓ Pinyin: {char_data.get('Pinyin', 'N/A')}")
        print(f"   ✓ Radical: {char_data.get('Radical', 'N/A')}")
        print(f"   ✓ Strokes: {char_data.get('Strokes', 'N/A')}")
        print(f"   ✓ Structure: {char_data.get('Structure', 'N/A')}")
    else:
        print(f"   ✗ Character '{test_char}' NOT found in lookup!")
        print(f"   First 10 characters in lookup: {list(character_lookup.keys())[:10]}")
        sys.exit(1)
    
    print("\n5. Testing a few more characters...")
    test_chars = ["妈", "我", "大", "米", "土", "地", "马", "花"]
    all_found = True
    for char in test_chars:
        if char in character_lookup:
            char_id = character_lookup[char].get('custom_id', 'N/A')
            print(f"   ✓ Found '{char}' (ID: {char_id})")
        else:
            print(f"   ✗ '{char}' NOT found")
            all_found = False
    
    print("\n" + "=" * 60)
    if all_found:
        print("✅ All tests passed! Character data is loaded correctly.")
        print("\nThe backend should be able to find these characters.")
        print("\nNext steps:")
        print("   1. Make sure you're in the virtual environment:")
        print("      source venv/bin/activate")
        print("   2. Start the backend: python3 app.py")
        print("   3. Check the startup messages - you should see:")
        print("      ✓ Successfully loaded X characters")
        print("      ✓ Test: Character '爸' is available")
    else:
        print("⚠️  Some test characters were not found.")
        sys.exit(1)
    print("=" * 60)

if __name__ == "__main__":
    test_data_loading()
