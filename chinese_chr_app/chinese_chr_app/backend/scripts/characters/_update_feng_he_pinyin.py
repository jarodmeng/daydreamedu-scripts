#!/usr/bin/env python3
"""
One-off: sync 呵's pinyin in feng_characters from characters.json (prune to ["hē"] only).

Run from backend/: python3 scripts/characters/_update_feng_he_pinyin.py
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
except ImportError:
    print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    sys.exit(1)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
CHARACTERS_JSON = OUTER_APP_DIR / "data" / "characters.json"


def main():
    if not CHARACTERS_JSON.exists():
        print(f"JSON not found: {CHARACTERS_JSON}")
        sys.exit(1)
    with open(CHARACTERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    entry = next((e for e in data if (e.get("Character") or "").strip() == "呵"), None)
    if not entry:
        print("呵 not found in characters.json")
        sys.exit(1)
    pinyin = entry.get("Pinyin") or []
    if not isinstance(pinyin, list):
        print("Pinyin is not a list")
        sys.exit(1)
    index = (entry.get("Index") or "").strip()
    if not index:
        print("呵 has no Index in characters.json")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE feng_characters SET pinyin = %s WHERE character = %s AND index = %s",
                (json.dumps(pinyin), "呵", index),
            )
        conn.commit()
        print(f"Updated feng_characters for 呵 (index={index}): pinyin={pinyin}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
