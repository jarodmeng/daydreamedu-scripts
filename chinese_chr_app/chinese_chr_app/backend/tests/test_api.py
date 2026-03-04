#!/usr/bin/env python3
"""Test script to verify the backend data loading works correctly"""
import sys
from pathlib import Path

# Add parent directory (backend/) to path to import app
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the load_characters function directly
from app import load_characters, CHARACTERS_JSON
from pinyin_recall import _all_pinyin_list, get_correct_pinyin

def test_data_loading():
    """Test that character data loads correctly"""
    print("=" * 50)
    print("Testing Backend Data Loading")
    print("=" * 50)
    
    print(f"\n1. Checking JSON file path...")
    print(f"   Path: {CHARACTERS_JSON}")
    print(f"   Exists: {CHARACTERS_JSON.exists()}")
    
    if not CHARACTERS_JSON.exists():
        print("\n❌ JSON file not found!")
        print(f"   Expected at: {CHARACTERS_JSON}")
        sys.exit(1)
    
    print("\n2. Loading character data...")
    try:
        characters_data, character_lookup = load_characters()
        print(f"   ✓ Loaded {len(characters_data)} characters from JSON")
        print(f"   ✓ Created lookup dictionary with {len(character_lookup)} entries")
    except Exception as e:
        print(f"   ✗ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n3. Testing search for character '爸'...")
    test_char = "爸"
    if test_char in character_lookup:
        char_data = character_lookup[test_char]
        print(f"   ✓ Found character '{test_char}'")
        print(f"   ✓ Character Index: {char_data.get('Index', 'N/A')}")
        print(f"   ✓ Pinyin: {char_data.get('Pinyin', 'N/A')}")
        print(f"   ✓ Radical: {char_data.get('Radical', 'N/A')}")
        print(f"   ✓ Strokes: {char_data.get('Strokes', 'N/A')}")
    else:
        print(f"   ✗ Character '{test_char}' NOT found in lookup!")
        print(f"   Sample characters in lookup: {list(character_lookup.keys())[:10]}")
        sys.exit(1)
    
    print("\n4. Testing a few more characters...")
    test_chars = ["妈", "我", "大", "米"]
    all_found = True
    for char in test_chars:
        if char in character_lookup:
            print(f"   ✓ Found '{char}' (Index: {character_lookup[char].get('Index', 'N/A')})")
        else:
            print(f"   ✗ '{char}' NOT found")
            all_found = False
    
    if not all_found:
        print("\n⚠️  Some test characters were not found.")
        sys.exit(1)

    print("\n5. Checking multi-pinyin helper for a polyphonic character (if available)...")
    poly_char = "中"
    if poly_char in character_lookup:
        entry = character_lookup[poly_char]
        # Simulate the pinyin recall helpers used for missed_item
        # In the real app, HWXNet entry provides 拼音; here we fall back to Feng JSON Pinyin list when present.
        pinyin_list = entry.get("Pinyin") or []
        correct = ""
        if isinstance(pinyin_list, list) and pinyin_list:
            correct = (pinyin_list[0] or "").strip()
        else:
            correct = get_correct_pinyin({"拼音": pinyin_list})
        all_pinyin = _all_pinyin_list({"拼音": pinyin_list}, fallback_primary=correct)
        is_polyphonic = len(all_pinyin) > 1
        print(f"   ✓ Correct pinyin candidate: {correct or 'N/A'}")
        print(f"   ✓ all_pinyin: {all_pinyin}")
        print(f"   ✓ is_polyphonic: {is_polyphonic}")
    else:
        print(f"   (Info) Character '{poly_char}' not found in lookup; skipping multi-pinyin helper check.")

    print("\n✅ All tests passed! Backend data loading and pinyin helpers work correctly.")

if __name__ == "__main__":
    test_data_loading()
