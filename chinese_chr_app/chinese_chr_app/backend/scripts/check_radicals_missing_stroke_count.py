#!/usr/bin/env python3
"""
Check for radicals that appear in character tables (feng_characters, hwxnet_characters)
but are not in radical_stroke_counts.

Run from backend/:
  python3 scripts/check_radicals_missing_stroke_count.py

Requires DATABASE_URL or SUPABASE_DB_URL.
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


def _import_psycopg():
    try:
        import psycopg
        return psycopg
    except ImportError:
        print("psycopg is required. Install with: pip install 'psycopg[binary]>=3.1'")
        sys.exit(1)


def get_connection():
    pg = _import_psycopg()
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL.")
        sys.exit(1)
    return pg.connect(url)


SQL_RADICALS_IN_CHARS_NOT_IN_STROKE = """
WITH char_radicals AS (
    SELECT DISTINCT trim(radical) AS r
    FROM feng_characters
    WHERE radical IS NOT NULL AND trim(radical) != ''
    UNION
    SELECT DISTINCT trim(radical) AS r
    FROM hwxnet_characters
    WHERE radical IS NOT NULL AND trim(radical) != ''
)
SELECT r AS radical
FROM char_radicals
EXCEPT
SELECT radical FROM radical_stroke_counts
ORDER BY radical;
"""


def main():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_RADICALS_IN_CHARS_NOT_IN_STROKE)
            missing = [row[0] for row in cur.fetchall()]
        if not missing:
            print("All radicals from character tables exist in radical_stroke_counts.")
            return
        print(f"Radicals in character tables but NOT in radical_stroke_counts: {len(missing)}")
        for r in missing:
            print(f"  {r!r}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
