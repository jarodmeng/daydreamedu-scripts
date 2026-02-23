#!/usr/bin/env python3
"""
Add category column to pinyin_recall_item_answered.

Category: 新字 (new), 巩固 (confirm), 重测 (revise) - determined at answer time.

Run backfill script after this: python3 scripts/backfill_pinyin_recall_category.py

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/add_pinyin_recall_category_column.py
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
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE pinyin_recall_item_answered
                ADD COLUMN IF NOT EXISTS category text;
            """)
        conn.commit()
        print("Added category column to pinyin_recall_item_answered.")
        print("Run: python3 scripts/backfill_pinyin_recall_category.py")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
