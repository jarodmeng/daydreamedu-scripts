#!/usr/bin/env python3
"""
Add common_phrases column to hwxnet_characters and backfill from extracted_characters_hwxnet.json.

This script only adds/updates the common_phrases column. It does not modify any other
column (character, pinyin, english_translations, basic_meanings, etc.).

Reads 常用词组 from the JSON (array of strings per character) and updates the DB column.
Before modifying the table, the script creates a backup table
hwxnet_characters_backup_YYYYMMDD_HHMMSS. Use --no-backup to skip.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/characters/add_common_phrases_column.py
  python3 scripts/characters/add_common_phrases_column.py --dry-run   # no DB writes, print sample
  python3 scripts/characters/add_common_phrases_column.py --no-backup   # skip backup table
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


def _import_psycopg():
    try:
        import psycopg
        return psycopg
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)


def get_connection():
    pg = _import_psycopg()
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL to your Supabase Postgres connection string.")
        sys.exit(1)
    return pg.connect(url)


ADD_COLUMN_SQL = """
ALTER TABLE hwxnet_characters
ADD COLUMN IF NOT EXISTS common_phrases jsonb;
"""


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Add common_phrases to hwxnet_characters and backfill from extracted_characters_hwxnet.json."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not connect or write to DB; only print sample from JSON.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup table before modifying hwxnet_characters.",
    )
    parser.add_argument(
        "--data-json",
        type=Path,
        default=None,
        help="Path to extracted_characters_hwxnet.json (default: chinese_chr_app/data/...).",
    )
    args = parser.parse_args()

    # Resolve JSON path (same layout as add_searchable_pinyin_column)
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent.parent
    outer_app_dir = backend_dir.parent.parent
    data_dir = outer_app_dir / "data"
    default_json = data_dir / "extracted_characters_hwxnet.json"
    json_path = args.data_json or default_json

    if not json_path.exists():
        print(f"Error: {json_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        hwxnet_data = json.load(f)

    # Build character -> 常用词组 (list of strings)
    common_phrases_by_char = {}
    for ch, entry in hwxnet_data.items():
        phrases = entry.get("常用词组")
        if isinstance(phrases, list):
            common_phrases_by_char[ch] = [str(p).strip() for p in phrases if p]
        else:
            common_phrases_by_char[ch] = []

    if args.dry_run:
        print("Dry run: sample 常用词组 from JSON")
        for i, (ch, phrases) in enumerate(list(common_phrases_by_char.items())[:15]):
            print(f"  {ch}: {phrases[:5]}{' ...' if len(phrases) > 5 else ''}")
        print(f"Total characters in JSON: {len(common_phrases_by_char)}")
        non_empty = sum(1 for p in common_phrases_by_char.values() if p)
        print(f"Characters with non-empty 常用词组: {non_empty}")
        print("Set DATABASE_URL and run without --dry-run to add column and backfill.")
        return

    conn = get_connection()
    try:
        if not args.no_backup:
            backup_name = f"hwxnet_characters_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            with conn.cursor() as cur:
                cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM hwxnet_characters")
                conn.commit()
            print(f"Backup table created: {backup_name}")

        with conn.cursor() as cur:
            cur.execute(ADD_COLUMN_SQL)
            conn.commit()
        print("Column common_phrases added (or already exists).")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT character, zibiao_index FROM hwxnet_characters ORDER BY zibiao_index"
            )
            rows = cur.fetchall()

        updated = 0
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            with conn.cursor() as cur:
                for r in batch:
                    ch, zibiao = r[0], r[1]
                    phrases = common_phrases_by_char.get(ch, [])
                    # Only set common_phrases; no other columns are touched.
                    cur.execute(
                        "UPDATE hwxnet_characters SET common_phrases = %s::jsonb WHERE character = %s AND zibiao_index = %s",
                        (json.dumps(phrases) if phrases else None, ch, zibiao),
                    )
                    updated += 1
            conn.commit()
            if len(rows) > batch_size:
                print(f"  Updated {min(i + batch_size, len(rows))} / {len(rows)}")

        print(f"Backfilled common_phrases for {updated} rows.")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM hwxnet_characters WHERE common_phrases IS NOT NULL AND jsonb_array_length(common_phrases) > 0"
            )
            non_empty_count = cur.fetchone()[0]
        print(f"Rows with non-empty common_phrases: {non_empty_count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
