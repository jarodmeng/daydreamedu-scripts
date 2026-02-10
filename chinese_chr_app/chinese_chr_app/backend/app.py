from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import json
import logging
import re
import shutil
import os
import urllib.request
import urllib.parse
import ssl
import certifi
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from collections import defaultdict

from pinyin_search import parse_pinyin_query, compute_searchable_pinyin_for_entry
from pinyin_recall import (
    build_session_queue,
    update_learning_state,
    get_stem_words,
    get_correct_pinyin,
)
import uuid

# Load environment variables from .env file if it exists (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv('.env.local')
except ImportError:
    pass  # python-dotenv not installed, skip

app = Flask(__name__)

# Paths configuration - use environment variables with fallbacks
# Backend is at: chinese_chr_app/chinese_chr_app/backend/app.py
# JSON is at: chinese_chr_app/data/characters.json
_backend_dir = Path(__file__).resolve().parent
BASE_DIR = _backend_dir.parent.parent  # Go up to chinese_chr_app level

# Data directory - default to /app/data in container, or relative path for local dev
# In Docker container, files are at /app/data/, so use that as default
# For local development, calculate relative to BASE_DIR
if os.getenv('DATA_DIR'):
    DATA_DIR = Path(os.getenv('DATA_DIR'))
elif Path('/app/data').exists():
    # Running in container - data is at /app/data
    DATA_DIR = Path('/app/data')
else:
    # Local development - data is relative to BASE_DIR
    DATA_DIR = BASE_DIR / "data"
CHARACTERS_JSON = DATA_DIR / "characters.json"
HWXNET_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
RADICAL_STROKE_JSON = DATA_DIR / "radical_stroke_counts.json"
BACKUP_DIR = DATA_DIR / "backups"
HANZI_WRITER_CACHE_DIR = DATA_DIR / "temp" / "hanzi_writer"

# PNG directory - use GCS in production, local path for development
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', '')
# Default to data/png/ relative to BASE_DIR (chinese_chr_app/data/png/)
# Can be overridden via PNG_BASE_DIR environment variable
PNG_BASE_DIR = Path(os.getenv('PNG_BASE_DIR', str(DATA_DIR / "png")))

# Logs directory (local: chinese_chr_app/chinese_chr_app/backend/logs/; override with LOGS_DIR)
LOGS_DIR = Path(os.getenv('LOGS_DIR', str(_backend_dir / "logs")))
EDIT_LOG_FILE = LOGS_DIR / "character_edits.log"
PINYIN_RECALL_LOG_FILE = LOGS_DIR / "pinyin_recall.log"

# Use Supabase tables instead of JSON files when set (e.g. USE_DATABASE=true)
USE_DATABASE = os.environ.get('USE_DATABASE', '').strip().lower() in ('1', 'true', 'yes')

# CORS configuration - allow multiple origins
# Automatically allow all netlify.app subdomains
CORS_ORIGINS_RAW = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_RAW]

# Use regex pattern for netlify.app and daydreamedu.org subdomains + explicit origins
# Flask-CORS supports regex patterns in the origins list
CORS_ORIGINS_WITH_WILDCARD = CORS_ORIGINS.copy()
if not any('netlify.app' in o for o in CORS_ORIGINS):
    CORS_ORIGINS_WITH_WILDCARD.append(r'https://.*\.netlify\.app')
if not any('daydreamedu.org' in o for o in CORS_ORIGINS):
    CORS_ORIGINS_WITH_WILDCARD.append(r'https://.*\.daydreamedu\.org')

CORS(app, origins=CORS_ORIGINS_WITH_WILDCARD, supports_credentials=True)

# In-memory profile store (display_name by user_id). Resets on backend restart.
_profile_display_names = {}

# Load character data into memory
characters_data = None
character_lookup = {}  # Map character -> character data for fast lookup

# Load radicals data into memory
radicals_data = None  # Array of {radical, characters}
radicals_lookup = {}  # Map radical -> {radical, characters} for fast lookup

# Radical -> stroke count (for sort by radical stroke count). DB primary, JSON fallback.
radical_stroke_counts_map = None

# Load stroke-counts data into memory
stroke_counts_data = None  # Array of {count, character_count}
stroke_counts_lookup = {}  # Map count(int) -> list of character entries

# Load dictionary (hwxnet) data into memory
hwxnet_data = None      # Raw dict loaded from JSON
hwxnet_lookup = {}      # Map character -> hwxnet entry

# Setup logging
LOGS_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
edit_logger = logging.getLogger('character_edits')
edit_logger.setLevel(logging.INFO)
if not edit_logger.handlers:
    file_handler = logging.FileHandler(EDIT_LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    edit_logger.addHandler(file_handler)

pinyin_recall_logger = logging.getLogger('pinyin_recall')
pinyin_recall_logger.setLevel(logging.INFO)
if not pinyin_recall_logger.handlers:
    pinyin_handler = logging.FileHandler(PINYIN_RECALL_LOG_FILE, encoding='utf-8')
    pinyin_handler.setFormatter(logging.Formatter('%(message)s'))
    pinyin_recall_logger.addHandler(pinyin_handler)

def reload_characters():
    """Force reload characters from file (used after updates)"""
    global characters_data, character_lookup
    characters_data = None
    character_lookup = {}
    load_characters()

def load_hwxnet():
    """Load hwxnet dictionary data from JSON file or Supabase (when USE_DATABASE)."""
    global hwxnet_data, hwxnet_lookup
    if hwxnet_data is None:
        if USE_DATABASE:
            try:
                import database as db
                hwxnet_lookup = db.get_hwxnet_lookup()
                hwxnet_data = hwxnet_lookup
                print(f"Loaded hwxnet entries for {len(hwxnet_lookup)} characters (from database)")
            except Exception as e:
                print(f"Warning: Failed to load hwxnet from database: {e}")
                hwxnet_data = {}
                hwxnet_lookup = {}
            return hwxnet_data, hwxnet_lookup
        print(f"Loading hwxnet dictionary data from: {HWXNET_JSON}")
        print(f"File exists: {HWXNET_JSON.exists()}")
        if not HWXNET_JSON.exists():
            print(f"Warning: hwxnet data file not found at: {HWXNET_JSON}")
            hwxnet_data = {}
            hwxnet_lookup = {}
            return hwxnet_data, hwxnet_lookup
        with open(HWXNET_JSON, 'r', encoding='utf-8') as f:
            hwxnet_data = json.load(f)
        # hwxnet JSON is expected to be a dict keyed by character
        if isinstance(hwxnet_data, dict):
            hwxnet_lookup = hwxnet_data
        else:
            # Fallback: build lookup if data is a list
            hwxnet_lookup = {}
            for entry in hwxnet_data:
                char = entry.get('character') or entry.get('Character')
                if char:
                    hwxnet_lookup[char] = entry
        print(f"Loaded hwxnet entries for {len(hwxnet_lookup)} characters")
    return hwxnet_data, hwxnet_lookup

def load_characters():
    """Load character data from JSON file or Supabase (when USE_DATABASE)."""
    global characters_data, character_lookup
    if characters_data is None:
        if USE_DATABASE:
            try:
                import database as db
                characters_data = db.get_feng_characters()
                character_lookup = {}
                for char in characters_data:
                    char_key = char.get('Character', '').strip()
                    if char_key:
                        character_lookup[char_key] = char
                print(f"Loaded {len(characters_data)} characters (from database)")
                print(f"Lookup dictionary has {len(character_lookup)} entries")
                if '爸' in character_lookup:
                    print(f"✓ Character '爸' found in lookup: {character_lookup['爸']['Index']}")
            except Exception as e:
                raise FileNotFoundError(f"Failed to load characters from database: {e}") from e
            return characters_data, character_lookup
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
            print(f"✓ Character '爸' found in lookup: {character_lookup['爸']['Index']}")
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

def log_character_edit(index: str, field: str, old_value: Any, new_value: Any):
    """Log a character edit to the log file"""
    try:
        character_name = "unknown"
        if USE_DATABASE:
            try:
                import database as db
                row = db.get_feng_character_by_index(index)
                if row:
                    character_name = row.get('Character', 'unknown')
            except Exception:
                pass
        else:
            _, _lookup = load_characters()
            for char_data in (characters_data or []):
                if char_data.get('Index') == index:
                    character_name = char_data.get('Character', 'unknown')
                    break
        
        # Get client IP if available
        client_ip = request.remote_addr if request else "unknown"
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "character_index": index,
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
    Create timestamped backup of character data before editing.
    When USE_DATABASE: export feng_characters from DB to JSON.
    Otherwise: copy characters.json.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_backup = BACKUP_DIR / f"characters_{timestamp}.json"

        if USE_DATABASE:
            import database as db
            rows = db.get_feng_characters()
            with open(json_backup, 'w', encoding='utf-8') as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            print(f"✓ Backed up feng_characters to: {json_backup}")
        else:
            if not CHARACTERS_JSON.exists():
                return False, f"Source JSON file not found: {CHARACTERS_JSON}"
            shutil.copy2(CHARACTERS_JSON, json_backup)
            print(f"✓ Backed up JSON to: {json_backup}")

        cleanup_old_backups(max_backups)
        return True, str(BACKUP_DIR)
    except Exception as e:
        error_msg = f"Failed to create backup: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg

def update_character_field(index: str, field: str, new_value: Any) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Update a character field (in JSON file or Supabase when USE_DATABASE).
    Returns (success, error_message, updated_character)
    """
    global characters_data

    if USE_DATABASE:
        try:
            import database as db
            current = db.get_feng_character_by_index(index)
            if not current:
                return False, f"Character with index {index} not found", None
            old_value = current.get(field)
            is_valid, error_msg = validate_field_value(field, new_value)
            if not is_valid:
                return False, error_msg, None
            backup_success, backup_result = backup_character_files()
            if not backup_success:
                return False, f"Cannot proceed without backup: {backup_result}", None
            success, err, updated = db.update_feng_character(index, field, new_value)
            if not success:
                return False, err or "Update failed", None
            log_character_edit(index, field, old_value, new_value)
            reload_characters()
            reload_radicals()
            reload_structures()
            return True, None, updated
        except Exception as e:
            return False, f"Error updating character: {str(e)}", None

    try:
        data, lookup = load_characters()
        character = None
        char_index = None
        for i, char in enumerate(data):
            if char.get('Index') == index:
                character = char
                char_index = i
                break
        if not character:
            return False, f"Character with index {index} not found", None
        old_value = character.get(field)
        is_valid, error_msg = validate_field_value(field, new_value)
        if not is_valid:
            return False, error_msg, None
        backup_success, backup_result = backup_character_files()
        if not backup_success:
            return False, f"Cannot proceed without backup: {backup_result}", None
        character[field] = new_value
        data[char_index] = character
        characters_data = data
        if field == 'Character':
            old_char_key = character.get('Character', '').strip()
            if old_char_key and old_char_key in character_lookup:
                del character_lookup[old_char_key]
            char_key = new_value.strip()
            if char_key:
                character_lookup[char_key] = character
        with open(CHARACTERS_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log_character_edit(index, field, old_value, new_value)
        reload_radicals()
        reload_structures()
        return True, None, character
    except Exception as e:
        return False, f"Error updating character: {str(e)}", None

@app.route('/api/characters/<index>/update', methods=['PUT'])
def update_character(index):
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
        success, error_msg, updated_character = update_character_field(index, field, new_value)
        
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
    try:
        query = request.args.get('q', '').strip()

        if not query:
            return jsonify({'error': 'Please provide a character to search'}), 400

        # Only allow single character
        if len(query) != 1:
            return jsonify({'error': 'Please enter exactly one Chinese character'}), 400

        _, lookup = load_characters()
        _, hwx_lookup = load_hwxnet()

        # Debug: log the query and lookup info
        print(f"Searching for character: '{query}' (repr: {repr(query)})")
        print(f"Query length: {len(query)}")
        print(f"Query bytes: {query.encode('utf-8')}")
        print(f"Lookup dictionary size: {len(lookup)}")
        print(f"Character in lookup: {query in lookup}")

        # Try exact match in characters.json first
        if query in lookup:
            print(f"Found character data: {lookup[query]}")
            character = lookup[query]

            # Attach dictionary (hwxnet) data if available
            dictionary = hwx_lookup.get(query)

            return jsonify({
                'found': True,
                'character': character,
                'dictionary': dictionary
            })

        # Fallback: dictionary-only match (character not in characters.json)
        if query in hwx_lookup:
            dictionary = hwx_lookup.get(query)
            return jsonify({
                'found': True,
                'character': None,
                'dictionary': dictionary
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
            'error': f'未在数据库中找到"{query}"这个简体字'
        })
    except Exception as e:
        print(f"Search error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'服务器错误: {str(e)}',
            'detail': str(e)
        }), 500


def _pinyin_search_in_memory(search_keys: List[str]) -> List[Dict[str, Any]]:
    """Look up characters by search keys using in-memory hwxnet_lookup (no DB)."""
    _, hwx_lookup = load_hwxnet()
    if not hwx_lookup:
        return []
    # Build index: search_key -> list of (character, entry)
    key_to_entries: Dict[str, List[Tuple[str, Dict]]] = defaultdict(list)
    for ch, entry in hwx_lookup.items():
        if not isinstance(entry, dict):
            continue
        pinyin_list = entry.get('拼音') or []
        if isinstance(pinyin_list, str):
            pinyin_list = [pinyin_list]
        for key in compute_searchable_pinyin_for_entry(pinyin_list):
            key_to_entries[key].append((ch, entry))
    # Collect all characters that match any key
    seen = set()
    candidates = []
    for key in search_keys:
        for ch, entry in key_to_entries.get(key, []):
            if ch in seen:
                continue
            seen.add(ch)
            strokes = entry.get('总笔画')
            zibiao = entry.get('zibiao_index')
            candidates.append({
                'character': ch,
                'radical': (entry.get('部首') or '').strip() or '',
                'pinyin': entry.get('拼音') or [],
                'strokes': strokes,
                'zibiao_index': zibiao,
                'index': entry.get('index'),
            })
    # Sort by 总笔画 ASC, then zibiao_index ASC
    def _sort_key(x):
        s = x.get('strokes')
        z = x.get('zibiao_index')
        strokes_val = s if isinstance(s, (int, float)) else (int(s) if s is not None and str(s).strip().isdigit() else 999)
        zibiao_val = z if isinstance(z, (int, float)) else (999999 if z is None else z)
        return (strokes_val, zibiao_val)
    candidates.sort(key=_sort_key)
    return candidates


@app.route('/api/pinyin-search', methods=['GET'])
def pinyin_search():
    """Search characters by pinyin (e.g. ke3, ma, nǐ). Returns list sorted by stroke count, then zibiao_index."""
    query = (request.args.get('q') or '').strip()
    is_valid, err_msg, search_keys = parse_pinyin_query(query)
    if not is_valid or search_keys is None:
        return jsonify({'error': err_msg or '拼音输入格式错误'}), 400
    try:
        if USE_DATABASE:
            try:
                from database import get_characters_by_pinyin_search_keys
                characters = get_characters_by_pinyin_search_keys(search_keys)
            except Exception as e:
                print(f"Pinyin search DB error: {e}", flush=True)
                characters = _pinyin_search_in_memory(search_keys)
        else:
            characters = _pinyin_search_in_memory(search_keys)
        if not characters:
            return jsonify({
                'found': False,
                'query': query,
                'error': '未找到该拼音的汉字',
                'characters': [],
            })
        return jsonify({
            'found': True,
            'query': query,
            'characters': characters,
        })
    except Exception as e:
        print(f"Pinyin search error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'服务器错误: {str(e)}', 'detail': str(e)}), 500


@app.route('/api/images/<index>/<page>', methods=['GET'])
def get_image(index, page):
    """Serve character card images from GCS or local filesystem"""
    if page not in ['page1', 'page2']:
        return jsonify({'error': 'Invalid page. Use page1 or page2'}), 400

    blob_path = f"png/{index}/{page}.png"

    # Try GCS first if bucket is configured (production)
    if GCS_BUCKET_NAME:
        try:
            from google.cloud import storage
            storage_client = storage.Client()
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(blob_path)
            if blob.exists():
                image_bytes = blob.download_as_bytes()
                from io import BytesIO
                return send_file(BytesIO(image_bytes), mimetype='image/png')
            # GCS is configured but blob missing - don't fall back to local (container has no PNGs)
            print(f"GCS blob not found: gs://{GCS_BUCKET_NAME}/{blob_path}", flush=True)
            return jsonify({'error': 'Image not found in GCS', 'path': blob_path}), 404
        except ImportError:
            print("Warning: google-cloud-storage not installed, falling back to local filesystem", flush=True)
        except Exception as e:
            print(f"Error loading from GCS: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return jsonify({'error': 'Image storage unavailable', 'detail': str(e)}), 503

    # Local filesystem (development)
    image_path = PNG_BASE_DIR / index / f"{page}.png"
    if not image_path.exists():
        return jsonify({'error': 'Image not found', 'path': str(image_path)}), 404
    return send_file(str(image_path), mimetype='image/png')


@app.route('/api/strokes', methods=['GET'])
def get_hanzi_writer_strokes():
    """
    Proxy HanziWriter stroke JSON (makemeahanzi) through our backend.
    This avoids client-side CDN/adblock/CORS issues and caches locally.
    """
    ch = request.args.get('char', '').strip()
    if not ch or len(ch) != 1:
        return jsonify({'error': 'Please provide exactly one character via ?char='}), 400

    HANZI_WRITER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = HANZI_WRITER_CACHE_DIR / f"{ord(ch):x}.json"

    # Serve cached if available
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        except Exception:
            # If cache is corrupted, fall through to refetch
            try:
                cache_file.unlink()
            except Exception:
                pass

    encoded = urllib.parse.quote(ch)
    urls = [
        f"https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0.1/{encoded}.json",
        f"https://unpkg.com/hanzi-writer-data@2.0.1/{encoded}.json",
    ]

    # Use certifi CA bundle to avoid local truststore issues
    # (common on some macOS/Python setups).
    verify_ssl = os.getenv('HW_STROKES_VERIFY_SSL', '').strip().lower() not in ('0', 'false', 'no', 'off')
    ssl_context = ssl.create_default_context(cafile=certifi.where()) if verify_ssl else ssl._create_unverified_context()

    last_err = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20, context=ssl_context) as resp:
                if getattr(resp, 'status', 200) != 200:
                    raise Exception(f"HTTP {getattr(resp, 'status', 'unknown')}")
                raw = resp.read().decode('utf-8')
                data = json.loads(raw)
            # Cache best-effort (Cloud Run FS is ephemeral; permission errors shouldn't break the response)
            try:
                with open(cache_file, 'w', encoding='utf-8', newline='\n') as f:
                    json.dump(data, f, ensure_ascii=False)
                    f.write('\n')
            except Exception as cache_err:
                print(f"Warning: failed to write stroke cache {cache_file}: {cache_err}")
            return jsonify(data)
        except Exception as e:
            last_err = e
            continue

    return jsonify({'error': f'Failed to load stroke data for {ch}: {last_err}'}), 502

def generate_radicals_data(characters_data: List[Dict], hwxnet_lookup: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Generate radicals data for the Radicals pages.

    Preferred source: HWXNet dictionary data (covers 3664 characters).
    Fallback: characters.json (covers 3000 characters).

    Returns:
        List of {radical, characters} dictionaries where each character entry has:
          - Character
          - Pinyin (array)
          - Strokes (string)
          - (optional) Index/Structure when available
    """
    radical_dict = defaultdict(list)

    # Use HWXNet dictionary data if available (includes the extra 664 chars)
    if isinstance(hwxnet_lookup, dict) and hwxnet_lookup:
        for ch, entry in hwxnet_lookup.items():
            if not isinstance(entry, dict):
                continue
            radical = str(entry.get('部首') or '').strip()
            if not radical or radical == '—':
                continue

            pinyin = entry.get('拼音')
            pinyin_list = pinyin if isinstance(pinyin, list) else ([pinyin] if isinstance(pinyin, str) and pinyin else [])

            strokes = entry.get('总笔画')
            strokes_str = str(strokes) if strokes is not None else ''

            character_info = {
                'Character': ch,
                'Pinyin': pinyin_list,
                'Strokes': strokes_str,
            }

            # Preserve these fields when present (for 3000 characters sourced from characters.json)
            if 'index' in entry:
                character_info['Index'] = entry.get('index')
            if 'zibiao_index' in entry:
                character_info['zibiao_index'] = entry.get('zibiao_index')

            radical_dict[radical].append(character_info)
    else:
        # Fallback: derive radicals from characters.json
        for char in characters_data:
            radical = char.get('Radical', '').strip()
            # Remove dictionary markers if present
            if ' (dictionary)' in radical:
                radical = radical.replace(' (dictionary)', '')

            if radical:
                character_info = {
                    'Character': char.get('Character', ''),
                    'Index': char.get('Index', ''),
                    'Pinyin': char.get('Pinyin', []),
                    'Strokes': char.get('Strokes', ''),
                    'Structure': char.get('Structure', '')
                }
                radical_dict[radical].append(character_info)

    # Convert to the desired format
    result = []
    for radical, chars in sorted(radical_dict.items()):
        result.append({
            'radical': radical,
            'characters': chars
        })

    return result

def reload_radicals():
    """Force regenerate radicals data (used after character updates)"""
    global radicals_data, radicals_lookup
    radicals_data = None
    radicals_lookup = {}
    load_radicals()

def load_radicals():
    """Load/generate radicals data from characters_data (cached in memory)"""
    global radicals_data, radicals_lookup
    if radicals_data is None:
        # Prefer HWXNet dictionary (covers 3664 characters)
        print("Generating radicals data from hwxnet dictionary...")
        characters, _ = load_characters()
        _, hwx_lookup = load_hwxnet()
        radicals_data = generate_radicals_data(characters, hwxnet_lookup=hwx_lookup)
        # Create lookup dictionary for fast search
        radicals_lookup = {entry['radical']: entry for entry in radicals_data}
        # Note: hwxnet_lookup includes 3664 chars; characters.json includes 3000
        print(f"✓ Generated {len(radicals_data)} radicals from hwxnet dictionary ({len(hwx_lookup)} characters)")
    return radicals_data, radicals_lookup


def load_radical_stroke_counts() -> Dict[str, int]:
    """Load radical -> stroke_count. DB primary when USE_DATABASE; JSON fallback."""
    global radical_stroke_counts_map
    if radical_stroke_counts_map is not None:
        return radical_stroke_counts_map
    if USE_DATABASE:
        try:
            import database as db
            radical_stroke_counts_map = db.get_radical_stroke_counts()
            if radical_stroke_counts_map:
                print(f"✓ Loaded {len(radical_stroke_counts_map)} radical stroke counts from database")
            return radical_stroke_counts_map
        except Exception as e:
            logging.warning("Failed to load radical_stroke_counts from database: %s; falling back to JSON", e)
            radical_stroke_counts_map = None  # allow JSON fallback below
    # JSON fallback
    if not RADICAL_STROKE_JSON.exists():
        logging.warning("radical_stroke_counts.json not found at %s", RADICAL_STROKE_JSON)
        radical_stroke_counts_map = {}
        return radical_stroke_counts_map
    try:
        with open(RADICAL_STROKE_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        radical_stroke_counts_map = {str(k).strip(): int(v) for k, v in (data or {}).items() if k and str(k).strip() and isinstance(v, (int, float))}
        if radical_stroke_counts_map:
            print(f"✓ Loaded {len(radical_stroke_counts_map)} radical stroke counts from JSON")
        return radical_stroke_counts_map
    except Exception as e:
        logging.warning("Failed to load radical_stroke_counts from JSON: %s", e)
        radical_stroke_counts_map = {}
        return radical_stroke_counts_map


def generate_stroke_counts_data(hwxnet_lookup: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[int, List[Dict[str, Any]]]]:
    """
    Generate stroke-counts data from HWXNet dictionary entries.

    Returns:
        - stroke_counts: list of {count, character_count}, sorted by count asc
        - lookup: map count(int) -> list of {character, pinyin, radical, strokes, zibiao_index}
    """
    by_count: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

    for ch, entry in (hwxnet_lookup or {}).items():
        if not isinstance(entry, dict):
            continue

        strokes_raw = entry.get('总笔画')
        if strokes_raw is None:
            continue

        try:
            strokes_int = int(str(strokes_raw).strip())
        except Exception:
            continue

        if strokes_int <= 0:
            continue

        radical = str(entry.get('部首') or '').strip()
        if radical == '—':
            radical = ''

        pinyin = entry.get('拼音')
        pinyin_list = pinyin if isinstance(pinyin, list) else ([pinyin] if isinstance(pinyin, str) and pinyin else [])

        zibiao_raw = entry.get('zibiao_index')
        try:
            zibiao_int = int(zibiao_raw) if zibiao_raw is not None else None
        except Exception:
            zibiao_int = None

        by_count[strokes_int].append({
            'character': ch,
            'pinyin': pinyin_list,
            'radical': radical,
            'strokes': strokes_int,
            'zibiao_index': zibiao_int,
        })

    # Sort characters by zibiao_index (asc; missing last), then character
    for count, chars in by_count.items():
        chars.sort(key=lambda x: (
            x['zibiao_index'] if isinstance(x.get('zibiao_index'), int) else 10**9,
            x.get('character', '')
        ))

    stroke_counts = [
        {'count': count, 'character_count': len(chars)}
        for count, chars in by_count.items()
        if len(chars) > 0
    ]
    stroke_counts.sort(key=lambda x: x['count'])

    return stroke_counts, dict(by_count)

def reload_stroke_counts():
    """Force regenerate stroke-counts data (cached in memory)"""
    global stroke_counts_data, stroke_counts_lookup
    stroke_counts_data = None
    stroke_counts_lookup = {}
    load_stroke_counts()

def load_stroke_counts():
    """Load/generate stroke-counts data from HWXNet (cached in memory)"""
    global stroke_counts_data, stroke_counts_lookup
    if stroke_counts_data is None:
        print("Generating stroke-counts data from hwxnet dictionary...")
        _, hwx_lookup = load_hwxnet()
        stroke_counts_data, stroke_counts_lookup = generate_stroke_counts_data(hwx_lookup)
        total_characters = sum(item['character_count'] for item in stroke_counts_data)
        print(f"✓ Generated {len(stroke_counts_data)} stroke counts ({total_characters} characters)")
    return stroke_counts_data, stroke_counts_lookup

@app.route('/api/radicals', methods=['GET'])
def get_radicals():
    """Get all radicals; optional sort=character_count (default) or sort=stroke_count."""
    radicals_list, _ = load_radicals()
    sort_param = (request.args.get('sort') or 'character_count').strip().lower()
    sort_by_stroke = sort_param == 'stroke_count'
    stroke_map = load_radical_stroke_counts()

    radicals_with_count = []
    for entry in radicals_list:
        radical = entry['radical']
        count = len(entry['characters'])
        stroke_count = stroke_map.get(radical) if stroke_map else None
        radicals_with_count.append({
            'radical': radical,
            'character_count': count,
            'radical_stroke_count': stroke_count
        })

    if sort_by_stroke:
        # Ascending by radical_stroke_count; nulls last, then by character_count desc for stable order
        radicals_with_count.sort(key=lambda x: (
            x['radical_stroke_count'] is None,
            x['radical_stroke_count'] if x['radical_stroke_count'] is not None else 999,
            -x['character_count'],
            x['radical']
        ))
    else:
        radicals_with_count.sort(key=lambda x: x['character_count'], reverse=True)

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

@app.route('/api/stroke-counts', methods=['GET'])
def get_stroke_counts():
    """Get all stroke counts that exist, sorted ascending"""
    stroke_counts, _ = load_stroke_counts()
    total_characters = sum(item['character_count'] for item in stroke_counts)
    return jsonify({
        'stroke_counts': stroke_counts,
        'total_counts': len(stroke_counts),
        'total_characters': total_characters,
    })

@app.route('/api/stroke-counts/<int:count>', methods=['GET'])
def get_stroke_count_detail(count: int):
    """Get all characters for a specific stroke count"""
    _, lookup = load_stroke_counts()
    if count in lookup:
        chars = lookup[count]
        return jsonify({
            'count': count,
            'characters': chars,
            'total': len(chars),
        })

    return jsonify({
        'count': count,
        'characters': [],
        'total': 0,
        'error': f'No characters found for stroke count "{count}"'
    }), 404

def _profile_display_name_from_metadata(metadata):
    """Default display name from Supabase user_metadata."""
    if not metadata or not isinstance(metadata, dict):
        return "User"
    name = (
        metadata.get("name")
        or metadata.get("full_name")
        or metadata.get("preferred_username")
        or ""
    )
    name = " ".join((name or "").strip().split())
    name = "".join(c for c in name if c.isprintable())[:32]
    return name or "User"


def _get_profile_user():
    """Return authenticated user or None; raise nothing."""
    try:
        import auth as auth_module
        token = auth_module.extract_bearer_token(request.headers.get("Authorization"))
        if not token:
            print("[profile] No Bearer token in Authorization header", flush=True)
            return None
        return auth_module.verify_bearer_token(token)
    except Exception as e:
        print(f"[profile] Auth failed: {type(e).__name__}: {e}", flush=True)
        return None


def _get_pinyin_recall_dev_user():
    """
    For local testing only: if PINYIN_RECALL_DEV_USER is set, return a fake user with that user_id.
    Allows testing 拼音记忆 without Supabase. Do not set in production.
    """
    dev_user_id = os.getenv("PINYIN_RECALL_DEV_USER", "").strip()
    if not dev_user_id:
        return None
    return type("DevUser", (), {"user_id": dev_user_id, "user_metadata": None})()


@app.route('/api/profile', methods=['GET'])
def get_profile():
    """Get current user's profile (display_name). Requires Bearer token."""
    user = _get_profile_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401
    display_name = _profile_display_names.get(user.user_id) or _profile_display_name_from_metadata(user.user_metadata)
    return jsonify({"profile": {"display_name": display_name}}), 200


@app.route('/api/profile', methods=['PUT'])
def put_profile():
    """Update current user's display_name. Requires Bearer token."""
    user = _get_profile_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    display_name = str(data.get("display_name") or "").strip()
    display_name = " ".join(display_name.split())
    display_name = "".join(c for c in display_name if c.isprintable())[:32]
    if not display_name:
        return jsonify({"error": "display_name is required"}), 400
    _profile_display_names[user.user_id] = display_name
    return jsonify({"profile": {"display_name": display_name}}), 200


def _display_name_for_log(user, display_name_from_body: Optional[str] = None) -> str:
    """Prefer body display_name, then in-memory profile, then JWT user_metadata."""
    if display_name_from_body and display_name_from_body.strip():
        return " ".join(display_name_from_body.strip().split())[:64]
    if user and user.user_id:
        in_mem = _profile_display_names.get(user.user_id)
        if in_mem:
            return in_mem
    if user and user.user_metadata and isinstance(user.user_metadata, dict):
        for key in ("name", "full_name", "preferred_username"):
            val = user.user_metadata.get(key)
            if val and isinstance(val, str) and val.strip():
                return " ".join(val.strip().split())[:64]
        email = user.user_metadata.get("email")
        if email and isinstance(email, str) and email.strip():
            return email.strip()[:64]
    return ""


# In-memory learning state for pinyin recall (MVP1): user_id -> character -> { stage, next_due_utc }
# Resets on backend restart. Can be replaced with DB table later.
_learning_state_pinyin: Dict[str, Dict[str, Dict[str, Any]]] = {}


def _get_pinyin_recall_learning_state(user_id: str) -> Dict[str, Dict[str, Any]]:
    """Learning state for queue building: from DB when USE_DATABASE, else in-memory."""
    if USE_DATABASE:
        try:
            import database as db
            char_state = db.get_pinyin_recall_learning_state(user_id)
            return {user_id: char_state}
        except Exception as e:
            print(f"[pinyin-recall] Failed to load learning state from DB: {e}", flush=True)
    return _learning_state_pinyin


def _log_pinyin_recall_event(
    event: str,
    *,
    items: Optional[List[Dict[str, Any]]] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Write pinyin recall event to Supabase (when USE_DATABASE) or to pinyin_recall.log."""
    if USE_DATABASE:
        try:
            import database as db
            if event == "item_presented" and items is not None and user_id and session_id:
                for item in items:
                    p = {
                        "user_id": user_id,
                        "session_id": session_id,
                        "character": item.get("character"),
                        "prompt_type": item.get("prompt_type"),
                        "correct_choice": item.get("correct_pinyin"),
                        "choices": item.get("choices"),
                    }
                    db.insert_pinyin_recall_item_presented(p)
            elif event == "item_answered" and payload is not None:
                db.insert_pinyin_recall_item_answered(payload)
        except Exception as e:
            print(f"[pinyin-recall] Failed to insert event: {e}", flush=True)
    else:
        if event == "item_presented" and items is not None and user_id and session_id:
            for item in items:
                p = {
                    "event": "item_presented",
                    "user_id": user_id,
                    "session_id": session_id,
                    "character": item.get("character"),
                    "prompt_type": item.get("prompt_type"),
                    "correct_choice": item.get("correct_pinyin"),
                    "choices": item.get("choices"),
                }
                pinyin_recall_logger.info(json.dumps(p, ensure_ascii=False))
        elif event == "item_answered" and payload is not None:
            pinyin_recall_logger.info(json.dumps({**payload, "event": "item_answered"}, ensure_ascii=False))


@app.route('/api/games/pinyin-recall/session', methods=['GET'])
def pinyin_recall_session():
    """Get session queue for pinyin recall. Requires Bearer token (or PINYIN_RECALL_DEV_USER for local testing)."""
    user = _get_profile_user() or _get_pinyin_recall_dev_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        load_characters()
        load_hwxnet()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    learning_state = _get_pinyin_recall_learning_state(user.user_id)
    items = build_session_queue(
        user.user_id,
        date_str,
        learning_state,
        hwxnet_lookup,
        character_lookup,
        total_target=20,
    )
    session_id = str(uuid.uuid4())
    _log_pinyin_recall_event("item_presented", items=items, user_id=user.user_id, session_id=session_id)
    return jsonify({
        "session_id": session_id,
        "items": items,
    })


@app.route('/api/games/pinyin-recall/next-batch', methods=['POST'])
def pinyin_recall_next_batch():
    """Get next batch of 20 items for open-ended play. Requires Bearer token (or PINYIN_RECALL_DEV_USER)."""
    user = _get_profile_user() or _get_pinyin_recall_dev_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        load_characters()
        load_hwxnet()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    data = request.get_json() or {}
    session_id = (data.get("session_id") or "").strip() or str(uuid.uuid4())
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    learning_state = _get_pinyin_recall_learning_state(user.user_id)
    items = build_session_queue(
        user.user_id,
        date_str,
        learning_state,
        hwxnet_lookup,
        character_lookup,
        total_target=20,
    )
    _log_pinyin_recall_event("item_presented", items=items, user_id=user.user_id, session_id=session_id)
    return jsonify({"session_id": session_id, "items": items})


@app.route('/api/games/pinyin-recall/answer', methods=['POST'])
def pinyin_recall_answer():
    """Submit answer for one item. Requires Bearer token (or PINYIN_RECALL_DEV_USER for local testing)."""
    user = _get_profile_user() or _get_pinyin_recall_dev_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    character = (data.get("character") or "").strip()
    if not character or len(character) != 1:
        return jsonify({"error": "character must be exactly one character"}), 400
    selected_choice = (data.get("selected_choice") or "").strip()
    i_dont_know = bool(data.get("i_dont_know"))
    correct_pinyin = (data.get("correct_pinyin") or "").strip()
    if not correct_pinyin:
        return jsonify({"error": "correct_pinyin is required"}), 400
    correct = not i_dont_know and selected_choice.strip().lower() == correct_pinyin.strip().lower()
    if i_dont_know:
        correct = False
    latency_ms = data.get("latency_ms")
    score_before = None
    score_after = None
    if USE_DATABASE:
        try:
            import database as db
            score_before, score_after = db.upsert_pinyin_recall_character_bank(
                user.user_id, character, correct=correct, i_dont_know=i_dont_know
            )
        except Exception as e:
            print(f"[pinyin-recall] Failed to upsert character bank: {e}", flush=True)
    else:
        update_learning_state(
            _learning_state_pinyin,
            user.user_id,
            character,
            correct=correct,
            i_dont_know=i_dont_know,
        )
    log_payload = {
        "event": "item_answered",
        "user_id": user.user_id,
        "session_id": data.get("session_id"),
        "character": character,
        "selected_choice": selected_choice,
        "correct": correct,
        "latency_ms": latency_ms,
        "i_dont_know": i_dont_know,
    }
    if score_before is not None and score_after is not None:
        log_payload["score_before"] = score_before
        log_payload["score_after"] = score_after
    _log_pinyin_recall_event("item_answered", payload=log_payload)
    missed_item = None
    if not correct:
        load_hwxnet()
        load_characters()
        entry = (hwxnet_lookup or {}).get(character) if hwxnet_lookup else None
        feng = (character_lookup or {}).get(character) if character_lookup else None
        stem_words = get_stem_words(character, character_lookup or {}, hwxnet_lookup or {}, 3)
        correct_pinyin_val = get_correct_pinyin(entry) if entry else correct_pinyin
        # English meanings for learning screen (all 英文翻译 for English-speaking learners)
        meanings = []
        meaning_zh = None
        if entry:
            english = entry.get("英文翻译") or []
            if isinstance(english, list):
                meanings = [(e or "").strip() for e in english if (e or "").strip()]
            if not meanings:
                for sense in (entry.get("基本字义解释") or [])[:1]:
                    for defn in (sense.get("释义") or [])[:1]:
                        expl = (defn.get("解释") or "").strip()
                        if expl:
                            meaning_zh = expl
                            break
                    if meaning_zh:
                        break
        radical = ""
        strokes = None
        if entry:
            radical = (entry.get("部首") or "").strip() or ""
            strokes = entry.get("总笔画")
        if feng:
            if not radical:
                radical = (feng.get("Radical") or "").strip().replace(" (dictionary)", "").strip() or ""
            if strokes is None:
                strokes = feng.get("Strokes")
        structure = (feng.get("Structure") or "").strip() if feng else ""
        sentence = (feng.get("Sentence") or "").strip() if feng else ""
        missed_item = {
            "character": character,
            "stem_words": stem_words,
            "correct_pinyin": correct_pinyin_val,
            "meanings": meanings,
            "meaning_zh": meaning_zh,
            "radical": radical,
            "strokes": strokes,
            "structure": structure,
            "sentence": sentence,
        }
    return jsonify({
        "correct": correct,
        "i_dont_know": i_dont_know,
        "missed_item": missed_item,
    })


@app.route('/api/log-character-view', methods=['POST'])
def log_character_view():
    """Log that the current user viewed a character (Search result). Requires Bearer token and USE_DATABASE."""
    user = _get_profile_user()
    if user is None:
        return jsonify({"error": "Unauthorized"}), 401
    if not USE_DATABASE:
        return jsonify({"error": "Character view logging is only available when using the database"}), 503
    data = request.get_json() or {}
    character = (data.get("character") or "").strip()
    if not character or len(character) != 1:
        return jsonify({"error": "character must be exactly one character"}), 400
    display_name = _display_name_for_log(user, (data.get("display_name") or "").strip() or None)
    try:
        import database as db
        db.log_character_view(user.user_id, character, display_name or None)
    except Exception as e:
        print(f"[log-character-view] Failed to log: {e}", flush=True)
        return jsonify({"error": "Failed to log view"}), 500
    return "", 204


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
            print(f"✓ Test: Character '爸' is available (ID: {character_lookup['爸']['Index']})")
        else:
            print(f"✗ Warning: Character '爸' not found in lookup!")
    except Exception as e:
        print(f"✗ Error loading characters: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        load_radicals()
        print(f"✓ Successfully generated {len(radicals_lookup)} radicals")
    except Exception as e:
        print(f"✗ Error generating radicals: {e}")
        import traceback
        traceback.print_exc()

    try:
        load_radical_stroke_counts()
    except Exception as e:
        print(f"✗ Error loading radical stroke counts: {e}")
        import traceback
        traceback.print_exc()

    try:
        load_hwxnet()
        print(f"✓ Successfully loaded hwxnet dictionary data for {len(hwxnet_lookup)} characters")
    except Exception as e:
        print(f"✗ Error loading hwxnet dictionary data: {e}")
        import traceback
        traceback.print_exc()
    
    # Get port from environment variable (Cloud Run sets PORT automatically)
    port = int(os.getenv('PORT', 5001))
    host = '0.0.0.0'  # Listen on all interfaces for Cloud Run
    
    print(f"\nStarting Flask server on http://{host}:{port}")
    print(f"API endpoint: http://{host}:{port}/api/characters/search?q=<character>")
    print(f"Radicals endpoint: http://{host}:{port}/api/radicals")
    if GCS_BUCKET_NAME:
        print(f"Image storage: Google Cloud Storage bucket '{GCS_BUCKET_NAME}'")
    else:
        print(f"Image storage: Local filesystem at '{PNG_BASE_DIR}'")
    
    # Use gunicorn in production (Cloud Run), Flask dev server locally
    if os.getenv('GAE_ENV') or os.getenv('K_SERVICE'):
        # Running in Cloud Run - gunicorn will be used via Dockerfile CMD
        print("Running in Cloud Run - gunicorn will handle the server")
    else:
        # Local development
        # NOTE: Some local Python installs can crash when Werkzeug's debugger
        # initializes (e.g. ctypes import issues). Default debug to off and
        # allow enabling explicitly via FLASK_DEBUG=1.
        debug_enabled = os.getenv('FLASK_DEBUG', '').strip().lower() in ('1', 'true', 'yes', 'on')
        app.run(debug=debug_enabled, host=host, port=port)
