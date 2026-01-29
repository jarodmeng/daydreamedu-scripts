#!/usr/bin/env python3
"""
Create the feng_characters table in Supabase and insert records from characters.json.

By default inserts the first 10 records (for testing). Use --all to migrate all 3000.

Requires DATABASE_URL (or SUPABASE_DB_URL) in the environment:
  postgresql://postgres.[ref]:[password]@...pooler.supabase.com:6543/postgres?sslmode=require

Run from backend/:
  python scripts/create_feng_characters_table.py          # first 10 only
  python scripts/create_feng_characters_table.py --all    # all characters
  python scripts/create_feng_characters_table.py --dry-run
"""

import json
import os
import sys
from pathlib import Path

# Load backend .env.local if present (so DATABASE_URL is available when run from backend/)
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


# Path to characters.json: from backend/scripts/ go up to chinese_chr_app (outer) / data
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
DATA_DIR = OUTER_APP_DIR / "data"
CHARACTERS_JSON = DATA_DIR / "characters.json"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS feng_characters (
    character text NOT NULL,
    index text NOT NULL,
    zibiao_index integer,
    pinyin jsonb,
    radical text,
    strokes integer,
    structure text,
    sentence text,
    words jsonb,
    PRIMARY KEY (character, index)
);

-- Optional: indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_feng_characters_character ON feng_characters(character);
CREATE INDEX IF NOT EXISTS idx_feng_characters_zibiao_index ON feng_characters(zibiao_index) WHERE zibiao_index IS NOT NULL;
"""


def get_connection():
    pg = _import_psycopg()
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print(
            "Set DATABASE_URL or SUPABASE_DB_URL to your Supabase Postgres connection string.\n"
            "Example: postgresql://postgres.[ref]:[password]@...pooler.supabase.com:6543/postgres?sslmode=require"
        )
        sys.exit(1)
    return pg.connect(url)


def parse_strokes(value) -> int | None:
    """Parse Strokes from JSON (string like '8') to int."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def row_from_json(entry: dict):
    """Convert one characters.json entry to a row tuple (character, index, zibiao_index, pinyin, radical, strokes, structure, sentence, words). Psycopg 3 adapts list/dict to JSONB automatically."""
    return (
        entry.get("Character", "").strip(),
        entry.get("Index", "").strip(),
        entry.get("zibiao_index"),
        entry.get("Pinyin") or [],
        (entry.get("Radical") or "").strip() or None,
        parse_strokes(entry.get("Strokes")),
        (entry.get("Structure") or "").strip() or None,
        (entry.get("Sentence") or "").strip() or None,
        entry.get("Words") or [],
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Create feng_characters table and insert records from characters.json."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate paths and print row count (no DB connection).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrate all characters (default: first 10 only).",
    )
    args = parser.parse_args()

    if not CHARACTERS_JSON.exists():
        print(f"characters.json not found at {CHARACTERS_JSON}")
        sys.exit(1)

    with open(CHARACTERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    to_insert = data if args.all else data[:10]
    if not to_insert:
        print("No records in characters.json")
        sys.exit(1)

    if args.dry_run:
        print(f"Dry run: would insert {len(to_insert)} rows (--all={args.all}).")
        for i, e in enumerate(to_insert[:5]):
            row = row_from_json(e)
            print(f"  {row[0]}  index={row[1]}  zibiao_index={row[2]}  strokes={row[5]}  radical={row[4]}")
        if len(to_insert) > 5:
            print(f"  ... and {len(to_insert) - 5} more")
        print("Set DATABASE_URL or SUPABASE_DB_URL and run without --dry-run to apply.")
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            conn.commit()
        print("Table feng_characters created (or already exists).")

        batch_size = 500
        total = len(to_insert)
        for offset in range(0, total, batch_size):
            batch = to_insert[offset : offset + batch_size]
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO feng_characters
                    (character, index, zibiao_index, pinyin, radical, strokes, structure, sentence, words)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (character, index) DO UPDATE SET
                        zibiao_index = EXCLUDED.zibiao_index,
                        pinyin = EXCLUDED.pinyin,
                        radical = EXCLUDED.radical,
                        strokes = EXCLUDED.strokes,
                        structure = EXCLUDED.structure,
                        sentence = EXCLUDED.sentence,
                        words = EXCLUDED.words
                    """,
                    [row_from_json(e) for e in batch],
                )
                conn.commit()
            print(f"  Inserted/upserted {offset + len(batch)} / {total}")

        print(f"Done. Inserted/upserted {total} records.")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM feng_characters")
            count = cur.fetchone()[0]
        print(f"Total rows in feng_characters: {count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
