#!/usr/bin/env python3
"""
Count hwxnet_characters rows (and distinct characters) with no English meaning.

Run from backend/: python3 scripts/characters/count_characters_no_english.py
Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
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

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    sys.exit(1)

url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
if not url:
    print("DATABASE_URL or SUPABASE_DB_URL is not set.")
    sys.exit(1)


def main():
    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            # Rows with no english: NULL or empty jsonb array
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM hwxnet_characters
                WHERE english_translations IS NULL
                   OR english_translations = '[]'::jsonb
            """)
            rows_no_english = cur.fetchone()["cnt"]

            # Total rows
            cur.execute("SELECT COUNT(*) AS cnt FROM hwxnet_characters")
            total_rows = cur.fetchone()["cnt"]

            # Distinct characters that have NO row with non-empty english_translations
            cur.execute("""
                SELECT COUNT(DISTINCT character) AS cnt
                FROM hwxnet_characters h
                WHERE NOT EXISTS (
                    SELECT 1 FROM hwxnet_characters h2
                    WHERE h2.character = h.character
                      AND h2.english_translations IS NOT NULL
                      AND h2.english_translations != '[]'::jsonb
                )
            """)
            chars_no_english = cur.fetchone()["cnt"]

            # Total distinct characters
            cur.execute("SELECT COUNT(DISTINCT character) AS cnt FROM hwxnet_characters")
            total_chars = cur.fetchone()["cnt"]

        print("hwxnet_characters — English meaning (english_translations)")
        print("=" * 56)
        print(f"  Rows with no English meaning:     {rows_no_english:,} / {total_rows:,}")
        print(f"  Distinct characters with no English: {chars_no_english:,} / {total_chars:,}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
