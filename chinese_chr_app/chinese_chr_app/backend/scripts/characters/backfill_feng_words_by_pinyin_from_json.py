#!/usr/bin/env python3
"""
Backfill feng_characters.words_by_pinyin from data/characters.json.
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


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
CHARACTERS_JSON = OUTER_APP_DIR / "data" / "characters.json"


def main():
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL")
        sys.exit(1)

    if not CHARACTERS_JSON.exists():
        print(f"Not found: {CHARACTERS_JSON}")
        sys.exit(1)

    data = json.loads(CHARACTERS_JSON.read_text(encoding="utf-8"))
    rows = [
        (
            (entry.get("Index") or "").strip(),
            entry.get("WordsByPinyin") or [],
        )
        for entry in data
        if (entry.get("Index") or "").strip()
    ]

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE feng_characters ADD COLUMN IF NOT EXISTS words_by_pinyin jsonb")
            cur.executemany(
                "UPDATE feng_characters SET words_by_pinyin = %s WHERE index = %s",
                [(Jsonb(words_by_pinyin), index) for index, words_by_pinyin in rows],
            )
        conn.commit()
    finally:
        conn.close()

    print(f"Backfilled words_by_pinyin for {len(rows)} feng_characters rows from {CHARACTERS_JSON}.")


if __name__ == "__main__":
    main()
