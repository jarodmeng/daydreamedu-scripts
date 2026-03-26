#!/usr/bin/env python3
"""
Add the transition words_by_pinyin column to feng_characters if it does not exist.
"""

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


def main():
    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL")
        sys.exit(1)

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE feng_characters ADD COLUMN IF NOT EXISTS words_by_pinyin jsonb")
        conn.commit()
    finally:
        conn.close()

    print("Ensured feng_characters.words_by_pinyin exists.")


if __name__ == "__main__":
    main()
