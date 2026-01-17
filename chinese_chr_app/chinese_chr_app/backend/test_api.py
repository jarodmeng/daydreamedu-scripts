#!/usr/bin/env python3
"""Test script to verify the backend data loading works correctly"""
import sys
from pathlib import Path

# Add parent directory to path to import app
sys.path.insert(0, str(Path(__file__).parent))

# Import the load_characters function directly
from app import load_characters, CHARACTERS_JSON

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
        print(f"   ✓ Character ID: {char_data.get('custom_id', 'N/A')}")
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
            print(f"   ✓ Found '{char}' (ID: {character_lookup[char].get('custom_id', 'N/A')})")
        else:
            print(f"   ✗ '{char}' NOT found")
            all_found = False
    
    if all_found:
        print("\n✅ All tests passed! Backend data loading works correctly.")
        print("\nNext steps:")
        print("   1. Start the backend: python3 app.py")
        print("   2. Start the frontend: cd ../frontend && npm run dev")
        print("   3. Open http://localhost:3000 in your browser")
    else:
        print("\n⚠️  Some test characters were not found.")
        sys.exit(1)

if __name__ == "__main__":
    test_data_loading()
