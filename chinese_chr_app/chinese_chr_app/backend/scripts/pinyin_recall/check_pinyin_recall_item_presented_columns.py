#!/usr/bin/env python3
"""
Check columns on pinyin_recall_item_presented in Supabase/Postgres.

Reports whether batch_mode and batch_character_category exist (and lists all columns).
Useful to verify migration (add_pinyin_recall_batch_columns.py) has been run.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/check_pinyin_recall_item_presented_columns.py
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
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'pinyin_recall_item_presented'
                ORDER BY ordinal_position;
                """
            )
            rows = cur.fetchall()
        if not rows:
            print("Table pinyin_recall_item_presented not found.")
            sys.exit(1)

        names = [r["column_name"] for r in rows]
        print("Columns on pinyin_recall_item_presented:")
        for r in rows:
            nullable = "NULL" if r["is_nullable"] == "YES" else "NOT NULL"
            print(f"  {r['column_name']}: {r['data_type']} ({nullable})")

        print()
        missing = [c for c in ("batch_mode", "batch_character_category") if c not in names]
        if not missing:
            print("  ✓ batch_mode and batch_character_category exist")
        else:
            for c in ("batch_mode", "batch_character_category"):
                status = "✓ exists" if c in names else "✗ missing"
                print(f"  {status}: {c}")
            print("  → python3 scripts/add_pinyin_recall_batch_columns.py")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
