#!/usr/bin/env python3
"""
Sync one character's pinyin and searchable_pinyin in hwxnet_characters from
extracted_characters_hwxnet.json.

Use after editing the JSON to set primary pinyin (reorder "拼音" so the desired
reading is first). This script pushes that character's pinyin and recomputed
searchable_pinyin to Supabase.

Run from backend/: python3 scripts/characters/update_hwxnet_primary_pinyin.py <character>
Example: python3 scripts/characters/update_hwxnet_primary_pinyin.py 囤

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
"""

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
except ImportError:
    print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from add_searchable_pinyin_column import compute_searchable_pinyin_for_row

BACKEND_DIR = SCRIPT_DIR.parent.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
HWXNET_JSON = OUTER_APP_DIR / "data" / "extracted_characters_hwxnet.json"


def main():
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print("Usage: python3 scripts/characters/update_hwxnet_primary_pinyin.py <character>")
        sys.exit(1)
    char = sys.argv[1].strip()
    if len(char) != 1:
        print("Character must be exactly one Hanzi.")
        sys.exit(1)

    if not HWXNET_JSON.exists():
        print(f"JSON not found: {HWXNET_JSON}")
        sys.exit(1)
    with open(HWXNET_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    if char not in data:
        print(f"Character {char} not found in JSON")
        sys.exit(1)
    pinyin_list = data[char].get("拼音") or []
    if not pinyin_list:
        print(f"No 拼音 for {char} in JSON")
        sys.exit(1)

    searchable = compute_searchable_pinyin_for_row(pinyin_list)
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE hwxnet_characters
                SET pinyin = %s::jsonb, searchable_pinyin = %s::jsonb
                WHERE character = %s
                """,
                (json.dumps(pinyin_list), json.dumps(searchable), char),
            )
            if cur.rowcount == 0:
                print(f"No row updated for character {char}")
                sys.exit(1)
        conn.commit()
        print(f"Updated hwxnet_characters for {char}: pinyin={pinyin_list}, searchable_pinyin={searchable}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
