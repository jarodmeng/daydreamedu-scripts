#!/usr/bin/env python3
"""
Create the hwxnet_characters table in Supabase and insert records from
extracted_characters_hwxnet.json.

By default inserts the first 10 records (for testing). Use --all to migrate all.

Requires DATABASE_URL (or SUPABASE_DB_URL) in the environment.

Run from backend/:
  python scripts/create_hwxnet_characters_table.py          # first 10 only
  python scripts/create_hwxnet_characters_table.py --all   # all entries
  python scripts/create_hwxnet_characters_table.py --dry-run
"""

import json
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


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
DATA_DIR = OUTER_APP_DIR / "data"
HWXNET_JSON = DATA_DIR / "extracted_characters_hwxnet.json"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS hwxnet_characters (
    character text NOT NULL,
    zibiao_index integer NOT NULL,
    index text,
    source_url text,
    classification jsonb,
    pinyin jsonb,
    radical text,
    strokes integer,
    basic_meanings jsonb,
    english_translations jsonb,
    PRIMARY KEY (character, zibiao_index)
);

CREATE INDEX IF NOT EXISTS idx_hwxnet_characters_character ON hwxnet_characters(character);
CREATE INDEX IF NOT EXISTS idx_hwxnet_characters_index ON hwxnet_characters(index) WHERE index IS NOT NULL;
"""


def get_connection():
    pg = _import_psycopg()
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print(
            "Set DATABASE_URL or SUPABASE_DB_URL to your Supabase Postgres connection string."
        )
        sys.exit(1)
    return pg.connect(url)


def row_from_entry(entry: dict):
    """Convert one hwxnet entry to a row tuple. Psycopg 3 adapts list/dict to JSONB automatically."""
    index_val = entry.get("index")
    if index_val is not None:
        index_val = str(index_val).strip() or None
    zibiao = entry.get("zibiao_index")
    if zibiao is not None and not isinstance(zibiao, int):
        try:
            zibiao = int(zibiao)
        except (TypeError, ValueError):
            zibiao = None
    strokes_val = entry.get("总笔画")
    if strokes_val is not None and not isinstance(strokes_val, int):
        try:
            strokes_val = int(strokes_val)
        except (TypeError, ValueError):
            strokes_val = None
    return (
        (entry.get("character") or "").strip(),
        zibiao,
        index_val,
        (entry.get("source_url") or "").strip() or None,
        entry.get("分类") or [],
        entry.get("拼音") or [],
        (entry.get("部首") or "").strip() or None,
        strokes_val,
        entry.get("基本字义解释") or [],
        entry.get("英文翻译") or [],
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Create hwxnet_characters table and insert records from extracted_characters_hwxnet.json."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate paths and print row count (no DB connection).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrate all entries (default: first 10 only).",
    )
    args = parser.parse_args()

    if not HWXNET_JSON.exists():
        print(f"extracted_characters_hwxnet.json not found at {HWXNET_JSON}")
        sys.exit(1)

    with open(HWXNET_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Dict keyed by character; preserve order (Python 3.7+) and take first N
    items = list(data.items())
    if not items:
        print("No entries in extracted_characters_hwxnet.json")
        sys.exit(1)

    limit = None if args.all else 10
    selected = items[:limit] if limit else items
    to_insert = [v for _k, v in selected]

    # Require zibiao_index for each row
    to_insert = [e for e in to_insert if e.get("zibiao_index") is not None]
    if not to_insert:
        print("No entries with zibiao_index found")
        sys.exit(1)

    if args.dry_run:
        print(f"Dry run: would insert {len(to_insert)} rows (--all={args.all}).")
        for i, e in enumerate(to_insert[:5]):
            row = row_from_entry(e)
            print(f"  {row[0]}  zibiao_index={row[1]}  index={row[2]}  strokes={row[7]}  radical={row[6]}")
        if len(to_insert) > 5:
            print(f"  ... and {len(to_insert) - 5} more")
        print("Set DATABASE_URL or SUPABASE_DB_URL and run without --dry-run to apply.")
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            conn.commit()
        print("Table hwxnet_characters created (or already exists).")

        batch_size = 500
        total = len(to_insert)
        for offset in range(0, total, batch_size):
            batch = to_insert[offset : offset + batch_size]
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO hwxnet_characters
                    (character, zibiao_index, index, source_url, classification, pinyin, radical, strokes, basic_meanings, english_translations)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (character, zibiao_index) DO UPDATE SET
                        index = EXCLUDED.index,
                        source_url = EXCLUDED.source_url,
                        classification = EXCLUDED.classification,
                        pinyin = EXCLUDED.pinyin,
                        radical = EXCLUDED.radical,
                        strokes = EXCLUDED.strokes,
                        basic_meanings = EXCLUDED.basic_meanings,
                        english_translations = EXCLUDED.english_translations
                    """,
                    [row_from_entry(e) for e in batch],
                )
                conn.commit()
            if total > 10:
                print(f"  Inserted/upserted {min(offset + batch_size, total)} / {total}")
        print(f"Done. Inserted/upserted {len(to_insert)} records.")

        with conn.cursor() as cur:
            cur.execute("SELECT character, zibiao_index, index, strokes, radical FROM hwxnet_characters ORDER BY zibiao_index LIMIT 10")
            rows = cur.fetchall()
        print("Sample rows in hwxnet_characters:")
        for r in rows:
            print(f"  {r[0]}  zibiao_index={r[1]}  index={r[2]}  strokes={r[3]}  radical={r[4]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
