#!/usr/bin/env python3
"""
Add english_translations_by_pinyin column to hwxnet_characters and backfill from extracted_characters_hwxnet.json.

This script only adds/updates the english_translations_by_pinyin column. It does not
modify any other column. Use --no-backup when you've already created a single backup
table for the whole rollout.
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
ADD COLUMN IF NOT EXISTS english_translations_by_pinyin jsonb;
"""


def _normalize_bucket(bucket):
    if not isinstance(bucket, dict):
        return None
    pinyin = bucket.get("Pinyin")
    glosses = bucket.get("Glosses")
    if not isinstance(pinyin, str) or not isinstance(glosses, list):
        return None

    out_glosses = []
    seen = set()
    for gloss in glosses:
        if not isinstance(gloss, str):
            continue
        text = gloss.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out_glosses.append(text)

    pinyin_text = pinyin.strip()
    if not pinyin_text:
        return None
    return {"Pinyin": pinyin_text, "Glosses": out_glosses}


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Add english_translations_by_pinyin to hwxnet_characters and backfill from extracted_characters_hwxnet.json."
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

    buckets_by_char = {}
    for ch, entry in hwxnet_data.items():
        raw_buckets = entry.get("英文解释按拼音")
        if isinstance(raw_buckets, list):
            buckets = []
            for bucket in raw_buckets:
                normalized = _normalize_bucket(bucket)
                if normalized:
                    buckets.append(normalized)
            buckets_by_char[ch] = buckets
        else:
            buckets_by_char[ch] = []

    if args.dry_run:
        print("Dry run: sample 英文解释按拼音 from JSON")
        for ch, buckets in list(buckets_by_char.items())[:15]:
            print(f"  {ch}: {buckets[:2]}{' ...' if len(buckets) > 2 else ''}")
        print(f"Total characters in JSON: {len(buckets_by_char)}")
        non_empty = sum(1 for buckets in buckets_by_char.values() if buckets)
        print(f"Characters with non-empty 英文解释按拼音: {non_empty}")
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
        print("Column english_translations_by_pinyin added (or already exists).")

        with conn.cursor() as cur:
            cur.execute("SELECT character, zibiao_index FROM hwxnet_characters ORDER BY zibiao_index")
            rows = cur.fetchall()

        updated = 0
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            with conn.cursor() as cur:
                for r in batch:
                    ch, zibiao = r[0], r[1]
                    buckets = buckets_by_char.get(ch, [])
                    cur.execute(
                        "UPDATE hwxnet_characters SET english_translations_by_pinyin = %s::jsonb WHERE character = %s AND zibiao_index = %s",
                        (json.dumps(buckets) if buckets else None, ch, zibiao),
                    )
                    updated += 1
            conn.commit()
            if len(rows) > batch_size:
                print(f"  Updated {min(i + batch_size, len(rows))} / {len(rows)}")

        print(f"Backfilled english_translations_by_pinyin for {updated} rows.")

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM hwxnet_characters
                WHERE english_translations_by_pinyin IS NOT NULL
                  AND jsonb_array_length(english_translations_by_pinyin) > 0
                """
            )
            non_empty_count = cur.fetchone()[0]
        print(f"Rows with non-empty english_translations_by_pinyin: {non_empty_count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
