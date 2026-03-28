#!/usr/bin/env python3
"""
Sync one feng_characters row from data/characters.json.

Run from backend/:
  python3 scripts/characters/sync_single_feng_character_from_json.py --character 嘛

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:
    print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
CHARACTERS_JSON = OUTER_APP_DIR / "data" / "characters.json"


def load_entry(character: str):
    if not CHARACTERS_JSON.exists():
        print(f"Not found: {CHARACTERS_JSON}")
        sys.exit(1)

    data = json.loads(CHARACTERS_JSON.read_text(encoding="utf-8"))
    for entry in data:
        if (entry.get("Character") or "").strip() == character:
            return entry
    print(f'Character "{character}" not found in {CHARACTERS_JSON}')
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Sync one feng_characters row from data/characters.json.")
    parser.add_argument("--character", required=True, help="Single Chinese character to sync.")
    parser.add_argument("--dry-run", action="store_true", help="Print the payload without writing to DB.")
    args = parser.parse_args()

    character = (args.character or "").strip()
    if len(character) != 1:
        print("--character must be exactly one Chinese character.")
        sys.exit(1)

    entry = load_entry(character)
    payload = {
        "index": (entry.get("Index") or "").strip(),
        "character": character,
        "pinyin": entry.get("Pinyin") or [],
        "words": entry.get("Words") or [],
        "words_by_pinyin": entry.get("WordsByPinyin") or [],
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.dry_run:
        return

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE feng_characters ADD COLUMN IF NOT EXISTS words_by_pinyin jsonb")
            cur.execute(
                """
                UPDATE feng_characters
                SET pinyin = %s,
                    words = %s,
                    words_by_pinyin = %s
                WHERE character = %s AND index = %s
                RETURNING character, index, pinyin, words, words_by_pinyin
                """,
                (
                    Jsonb(payload["pinyin"]),
                    Jsonb(payload["words"]),
                    Jsonb(payload["words_by_pinyin"]),
                    payload["character"],
                    payload["index"],
                ),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    if not row:
        print(f'No row updated for character="{payload["character"]}" index="{payload["index"]}".')
        sys.exit(1)

    print("Updated row:")
    print(json.dumps(row, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
