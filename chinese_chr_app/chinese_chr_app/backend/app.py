from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import json
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Paths configuration
# Backend is at: chinese_chr_app/chinese_chr_app/backend/app.py
# JSON is at: chinese_chr_app/extract_characters_using_ai/output/characters.json
# Use absolute path resolution to avoid issues
_backend_dir = Path(__file__).resolve().parent
BASE_DIR = _backend_dir.parent.parent  # Go up to chinese_chr_app level
CHARACTERS_JSON = BASE_DIR / "extract_characters_using_ai" / "output" / "characters.json"
PNG_BASE_DIR = Path("/Users/jarodm/Library/CloudStorage/GoogleDrive-winston.ry.meng@gmail.com/My Drive/冯氏早教识字卡/png")

# Load character data into memory
characters_data = None
character_lookup = {}  # Map character -> character data for fast lookup

def load_characters():
    """Load character data from JSON file"""
    global characters_data, character_lookup
    if characters_data is None:
        print(f"Loading characters from: {CHARACTERS_JSON}")
        print(f"File exists: {CHARACTERS_JSON.exists()}")
        if not CHARACTERS_JSON.exists():
            raise FileNotFoundError(f"Character data file not found at: {CHARACTERS_JSON}")
        with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
            characters_data = json.load(f)
        # Create lookup dictionary for fast search
        # Handle potential duplicate characters by keeping the last one
        # (This ensures we get the correct entry when there are data extraction errors)
        character_lookup = {}
        for char in characters_data:
            char_key = char.get('Character', '').strip()
            if char_key:
                # Always update to keep the last occurrence (handles duplicates)
                character_lookup[char_key] = char
        print(f"Loaded {len(characters_data)} characters")
        print(f"Lookup dictionary has {len(character_lookup)} entries")
        # Check for 爸 specifically
        if '爸' in character_lookup:
            print(f"✓ Character '爸' found in lookup: {character_lookup['爸']['custom_id']}")
        else:
            print("✗ Character '爸' NOT found in lookup")
            # Show first few characters for debugging
            sample_chars = list(character_lookup.keys())[:10]
            print(f"Sample characters in lookup: {sample_chars}")
    return characters_data, character_lookup

@app.route('/api/characters/search', methods=['GET'])
def search_character():
    """Search for a character by its simplified Chinese character"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'error': 'Please provide a character to search'}), 400
    
    # Only allow single character
    if len(query) != 1:
        return jsonify({'error': 'Please enter exactly one Chinese character'}), 400
    
    _, lookup = load_characters()
    
    # Debug: log the query and lookup info
    print(f"Searching for character: '{query}' (repr: {repr(query)})")
    print(f"Query length: {len(query)}")
    print(f"Query bytes: {query.encode('utf-8')}")
    print(f"Lookup dictionary size: {len(lookup)}")
    print(f"Character in lookup: {query in lookup}")
    
    # Try exact match first
    if query in lookup:
        print(f"Found character data: {lookup[query]}")
        character = lookup[query]
        return jsonify({
            'found': True,
            'character': character
        })
    
    # If not found, show debug info
    print(f"Character '{query}' not found in lookup")
    sample_keys = list(lookup.keys())[:5] if lookup else []
    print(f"Sample keys in lookup: {sample_keys}")
    
    # Check if there are any similar characters (for debugging)
    if lookup:
        first_char = list(lookup.keys())[0]
        print(f"First character in lookup: '{first_char}' (repr: {repr(first_char)})")
        print(f"First char bytes: {first_char.encode('utf-8')}")
        print(f"Query matches first char: {query == first_char}")
    
    return jsonify({
        'found': False,
        'error': f'Character "{query}" not found in the database'
    })

@app.route('/api/images/<custom_id>/<page>', methods=['GET'])
def get_image(custom_id, page):
    """Serve character card images"""
    if page not in ['page1', 'page2']:
        return jsonify({'error': 'Invalid page. Use page1 or page2'}), 400
    
    image_path = PNG_BASE_DIR / custom_id / f"{page}.png"
    
    if not image_path.exists():
        return jsonify({'error': 'Image not found'}), 404
    
    return send_file(str(image_path), mimetype='image/png')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    _, lookup = load_characters()
    return jsonify({
        'status': 'ok',
        'characters_loaded': len(lookup),
        'test_character_爸_available': '爸' in lookup
    })

if __name__ == '__main__':
    # Pre-load characters on startup
    try:
        load_characters()
        print(f"✓ Successfully loaded {len(character_lookup)} characters into lookup dictionary")
        if '爸' in character_lookup:
            print(f"✓ Test: Character '爸' is available (ID: {character_lookup['爸']['custom_id']})")
        else:
            print(f"✗ Warning: Character '爸' not found in lookup!")
    except Exception as e:
        print(f"✗ Error loading characters: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nStarting Flask server on http://localhost:5001")
    print(f"API endpoint: http://localhost:5001/api/characters/search?q=<character>")
    app.run(debug=True, port=5001)
