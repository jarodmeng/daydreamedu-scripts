#!/usr/bin/env python3
"""
Add page column to pinyin_recall_report_error.

page: which screen the report came from — question, wrong, or correct.
Existing rows get page = NULL.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/pinyin_recall/add_pinyin_recall_report_error_page_column.py
  python3 scripts/pinyin_recall/add_pinyin_recall_report_error_page_column.py --dry-run
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


def main():
    parser = argparse.ArgumentParser(description="Add page column to pinyin_recall_report_error")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL only, do not run")
    args = parser.parse_args()

    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    if args.dry_run:
        print("  ALTER TABLE pinyin_recall_report_error ADD COLUMN IF NOT EXISTS page text;")
        return

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE pinyin_recall_report_error
                ADD COLUMN IF NOT EXISTS page text;
            """)
        conn.commit()
        print("Added page column to pinyin_recall_report_error.")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
