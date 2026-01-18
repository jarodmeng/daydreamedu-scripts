from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Paths configuration
# Backend is at: chinese_chr_app/chinese_chr_app/backend/app.py
# JSON is at: chinese_chr_app/data/characters.json
# Use absolute path resolution to avoid issues
_backend_dir = Path(__file__).resolve().parent
BASE_DIR = _backend_dir.parent.parent  # Go up to chinese_chr_app level
DATA_DIR = BASE_DIR / "data"  # Data directory for character files
CHARACTERS_JSON = DATA_DIR / "characters.json"
RADICALS_JSON = DATA_DIR / "characters_by_radicals.json"
PNG_BASE_DIR = Path("/Users/jarodm/Library/CloudStorage/GoogleDrive-winston.ry.meng@gmail.com/My Drive/冯氏早教识字卡/png")
LOGS_DIR = _backend_dir / "logs"
EDIT_LOG_FILE = LOGS_DIR / "character_edits.log"
BACKUP_DIR = DATA_DIR / "backups"

# Load character data into memory
characters_data = None
character_lookup = {}  # Map character -> character data for fast lookup

# Load radicals data into memory
radicals_data = None  # Array of {radical, characters}
radicals_lookup = {}  # Map radical -> {radical, characters} for fast lookup

# Setup logging
LOGS_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
edit_logger = logging.getLogger('character_edits')
edit_logger.setLevel(logging.INFO)
if not edit_logger.handlers:
    file_handler = logging.FileHandler(EDIT_LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    edit_logger.addHandler(file_handler)

def reload_characters():
    """Force reload characters from file (used after updates)"""
    global characters_data, character_lookup
    characters_data = None
    character_lookup = {}
    load_characters()

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

def validate_field_value(field: str, value: Any) -> Tuple[bool, Optional[str]]:
    """
    Validate a field value based on its expected type and format.
    Returns (is_valid, error_message)
    """
    if field == 'Pinyin':
        if not isinstance(value, list):
            return False, "Pinyin must be an array"
        if len(value) == 0:
            return False, "Pinyin cannot be empty"
        for item in value:
            if not isinstance(item, str) or len(item.strip()) == 0:
                return False, "Pinyin items must be non-empty strings"
        return True, None
    
    elif field == 'Words':
        if not isinstance(value, list):
            return False, "Words must be an array"
        # Words can be empty array
        for item in value:
            if not isinstance(item, str):
                return False, "Words items must be strings"
        return True, None
    
    elif field == 'Radical':
        if not isinstance(value, str):
            return False, "Radical must be a string"
        return True, None
    
    elif field == 'Strokes':
        if not isinstance(value, str):
            return False, "Strokes must be a string"
        # Remove (dictionary) marker if present for validation
        strokes_clean = value.replace(' (dictionary)', '').strip()
        if not strokes_clean.isdigit():
            return False, "Strokes must be a number"
        return True, None
    
    elif field == 'Structure':
        if not isinstance(value, str):
            return False, "Structure must be a string"
        # Common structures
        valid_structures = ['左右结构', '上下结构', '半包围结构', '全包围结构', '独体结构', '左中右结构', '上中下结构']
        if value not in valid_structures:
            # Allow other structures too, just warn
            pass
        return True, None
    
    elif field == 'Sentence':
        if not isinstance(value, str):
            return False, "Sentence must be a string"
        # Sentence can be empty
        return True, None
    
    else:
        return False, f"Unknown field: {field}"

def log_character_edit(custom_id: str, field: str, old_value: Any, new_value: Any):
    """Log a character edit to the log file"""
    try:
        # Get character name for logging
        _, lookup = load_characters()
        character_name = "unknown"
        for char_data in characters_data:
            if char_data.get('custom_id') == custom_id:
                character_name = char_data.get('Character', 'unknown')
                break
        
        # Get client IP if available
        client_ip = request.remote_addr if request else "unknown"
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "character_index": custom_id,
            "character": character_name,
            "field": field,
            "old_value": str(old_value) if not isinstance(old_value, (list, dict)) else json.dumps(old_value, ensure_ascii=False),
            "new_value": str(new_value) if not isinstance(new_value, (list, dict)) else json.dumps(new_value, ensure_ascii=False),
            "user": client_ip
        }
        
        # Write as JSON line
        edit_logger.info(json.dumps(log_entry, ensure_ascii=False))
    except Exception as e:
        # Don't fail the update if logging fails
        print(f"Warning: Failed to log edit: {e}")

def cleanup_old_backups(max_backups: int = 200):
    """
    Remove old backup files, keeping only the most recent N backups.
    
    Args:
        max_backups: Maximum number of backup files to keep (default: 200)
    """
    try:
        if not BACKUP_DIR.exists():
            return
        
        # Find all backup JSON files (they have timestamps)
        backup_files = []
        for file in BACKUP_DIR.glob("characters_*.json"):
            # Extract timestamp from filename: characters_YYYYMMDD_HHMMSS.json
            try:
                timestamp_str = file.stem.replace("characters_", "")
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                backup_files.append((timestamp, file))
            except ValueError:
                # Skip files that don't match the expected format
                continue
        
        # Sort by timestamp (newest first)
        backup_files.sort(key=lambda x: x[0], reverse=True)
        
        # If we have more than max_backups, delete the oldest ones
        if len(backup_files) > max_backups:
            files_to_delete = backup_files[max_backups:]
            deleted_count = 0
            for timestamp, json_file in files_to_delete:
                try:
                    json_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Warning: Failed to delete {json_file}: {e}")
            
            if deleted_count > 0:
                print(f"✓ Cleaned up {deleted_count} old backup(s), keeping {max_backups} most recent")
    except Exception as e:
        # Don't fail backup if cleanup fails
        print(f"Warning: Failed to cleanup old backups: {e}")

def backup_character_files(max_backups: int = 200) -> Tuple[bool, Optional[str]]:
    """
    Create timestamped backup of characters.json before editing.
    Automatically cleans up old backups to limit disk usage.
    
    Args:
        max_backups: Maximum number of backup files to keep (default: 200)
                     Each backup is ~1.1MB, so 200 backups = ~220MB
    
    Returns:
        (success, backup_path_or_error_message)
    """
    try:
        # Generate timestamp for backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create backup filename
        json_backup = BACKUP_DIR / f"characters_{timestamp}.json"
        
        # Backup JSON file
        if CHARACTERS_JSON.exists():
            shutil.copy2(CHARACTERS_JSON, json_backup)
            print(f"✓ Backed up JSON to: {json_backup}")
        else:
            return False, f"Source JSON file not found: {CHARACTERS_JSON}"
        
        # Clean up old backups (after creating new one)
        cleanup_old_backups(max_backups)
        
        return True, str(BACKUP_DIR)
    except Exception as e:
        error_msg = f"Failed to create backup: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg

def update_character_field(custom_id: str, field: str, new_value: Any) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Update a character field in the JSON file.
    Returns (success, error_message, updated_character)
    """
    global characters_data
    
    try:
        # Reload data to get latest version
        data, lookup = load_characters()
        
        # Find the character
        character = None
        char_index = None
        for i, char in enumerate(data):
            if char.get('custom_id') == custom_id or char.get('Index') == custom_id:
                character = char
                char_index = i
                break
        
        if not character:
            return False, f"Character with index {custom_id} not found", None
        
        # Get old value
        old_value = character.get(field)
        
        # Validate new value
        is_valid, error_msg = validate_field_value(field, new_value)
        if not is_valid:
            return False, error_msg, None
        
        # Create backup before making any changes
        backup_success, backup_result = backup_character_files()
        if not backup_success:
            # Backup failed - this is critical, so we should abort the update
            return False, f"Cannot proceed without backup: {backup_result}", None
        
        # Update the character data
        character[field] = new_value
        
        # Update in-memory data
        data[char_index] = character
        characters_data = data
        
        # Update lookup if this is the Character field
        if field == 'Character':
            # Remove old character from lookup
            old_char_key = character.get('Character', '').strip()
            if old_char_key and old_char_key in character_lookup:
                del character_lookup[old_char_key]
            # Add new character to lookup
            char_key = new_value.strip()
            if char_key:
                character_lookup[char_key] = character
        
        # Write updated JSON back to file
        with open(CHARACTERS_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Log the change
        log_character_edit(custom_id, field, old_value, new_value)
        
        # Return the updated character
        return True, None, character
        
    except Exception as e:
        return False, f"Error updating character: {str(e)}", None

@app.route('/api/characters/<custom_id>/update', methods=['PUT'])
def update_character(custom_id):
    """Update a character field"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        field = data.get('field')
        new_value = data.get('value')
        
        if not field:
            return jsonify({'error': 'Field name is required'}), 400
        
        if new_value is None:
            return jsonify({'error': 'Value is required'}), 400
        
        # Handle array fields (Pinyin, Words) - parse from string if needed
        if field in ['Pinyin', 'Words']:
            if isinstance(new_value, str):
                try:
                    new_value = json.loads(new_value)
                except json.JSONDecodeError:
                    # Try comma-separated parsing
                    if field == 'Pinyin':
                        new_value = [p.strip() for p in new_value.split(',') if p.strip()]
                    elif field == 'Words':
                        new_value = [w.strip() for w in new_value.split(',') if w.strip()]
        
        # Update the field
        success, error_msg, updated_character = update_character_field(custom_id, field, new_value)
        
        if success:
            return jsonify({
                'success': True,
                'character': updated_character
            })
        else:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

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

def load_radicals():
    """Load radicals data from JSON file"""
    global radicals_data, radicals_lookup
    if radicals_data is None:
        print(f"Loading radicals from: {RADICALS_JSON}")
        print(f"File exists: {RADICALS_JSON.exists()}")
        if not RADICALS_JSON.exists():
            raise FileNotFoundError(f"Radicals data file not found at: {RADICALS_JSON}")
        with open(RADICALS_JSON, 'r', encoding='utf-8') as f:
            radicals_data = json.load(f)
        # Create lookup dictionary for fast search
        radicals_lookup = {entry['radical']: entry for entry in radicals_data}
        print(f"Loaded {len(radicals_data)} radicals")
    return radicals_data, radicals_lookup

@app.route('/api/radicals', methods=['GET'])
def get_radicals():
    """Get all radicals sorted by number of characters"""
    radicals_list, _ = load_radicals()
    
    # Convert to list with character count and sort by character count (descending)
    radicals_with_count = [
        {
            'radical': entry['radical'],
            'character_count': len(entry['characters'])
        }
        for entry in radicals_list
    ]
    radicals_with_count.sort(key=lambda x: x['character_count'], reverse=True)
    
    # Calculate total characters
    total_characters = sum(len(entry['characters']) for entry in radicals_list)
    
    return jsonify({
        'radicals': radicals_with_count,
        'total_radicals': len(radicals_list),
        'total_characters': total_characters
    })

@app.route('/api/radicals/<radical>', methods=['GET'])
def get_radical_detail(radical):
    """Get all characters for a specific radical"""
    _, lookup = load_radicals()
    
    # Decode the radical from URL
    decoded_radical = radical
    
    # Find the radical in lookup
    if decoded_radical in lookup:
        entry = lookup[decoded_radical]
        return jsonify({
            'radical': entry['radical'],
            'characters': entry['characters'],
            'count': len(entry['characters'])
        })
    
    # If not found, return 404
    return jsonify({
        'radical': decoded_radical,
        'characters': [],
        'count': 0,
        'error': f'No characters found for radical "{decoded_radical}"'
    }), 404

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
    # Pre-load characters and radicals on startup
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
    
    try:
        load_radicals()
        print(f"✓ Successfully loaded {len(radicals_lookup)} radicals")
    except Exception as e:
        print(f"✗ Error loading radicals: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nStarting Flask server on http://localhost:5001")
    print(f"API endpoint: http://localhost:5001/api/characters/search?q=<character>")
    print(f"Radicals endpoint: http://localhost:5001/api/radicals")
    app.run(debug=True, port=5001)
