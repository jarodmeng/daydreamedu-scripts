#!/usr/bin/env python3
"""
Add priority metadata columns to pinyin_recall_item_presented.

Columns:
- from_user_priority: whether the served item matched an active user priority row
- priority_label: human-readable serve-time priority label
- priority_source: machine-readable serve-time priority source

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/pinyin_recall/add_pinyin_recall_priority_columns.py
  python3 scripts/pinyin_recall/add_pinyin_recall_priority_columns.py --dry-run
"""

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Add priority metadata columns to pinyin_recall_item_presented.")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL without executing it.")
    args = parser.parse_args()

    sql = """
    ALTER TABLE pinyin_recall_item_presented
        ADD COLUMN IF NOT EXISTS from_user_priority boolean,
        ADD COLUMN IF NOT EXISTS priority_label text,
        ADD COLUMN IF NOT EXISTS priority_source text;
    """

    if args.dry_run:
        print("Would run:")
        print(sql.strip())
        return

    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("Added priority metadata columns to pinyin_recall_item_presented.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
