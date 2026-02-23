#!/usr/bin/env python3
"""
Add batch_id column to pinyin_recall_item_presented.

Allows grouping presented items by batch (each session/next-batch call = one batch).
Existing rows get batch_id = NULL.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/add_pinyin_recall_batch_id_column.py
  python3 scripts/add_pinyin_recall_batch_id_column.py --dry-run
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
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("Dry run: no changes applied.")

    try:
        import psycopg
    except ImportError:
        print("psycopg required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    if dry_run:
        print("Would run: ALTER TABLE pinyin_recall_item_presented ADD COLUMN IF NOT EXISTS batch_id uuid;")
        return

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                ALTER TABLE pinyin_recall_item_presented
                ADD COLUMN IF NOT EXISTS batch_id uuid;
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pinyin_recall_item_presented_batch_id
                ON pinyin_recall_item_presented (batch_id)
                WHERE batch_id IS NOT NULL;
                """
            )
        conn.commit()
        print("Added batch_id column and index to pinyin_recall_item_presented.")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
