#!/usr/bin/env python3
"""
Add batch_mode and batch_character_category columns to pinyin_recall_item_presented.

- batch_mode: queue mode for the batch (expansion, consolidation, or rescue; Issue #12).
- batch_character_category: character's five-band category at batch creation (new, hard, learning_normal, learned_normal, mastered).

Existing rows get NULL for both. Safe to run multiple times (ADD COLUMN IF NOT EXISTS).

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python scripts/add_pinyin_recall_batch_columns.py
  python scripts/add_pinyin_recall_batch_columns.py --dry-run
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
        print("psycopg required. Install with: pip install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    if dry_run:
        print("Would run:")
        print("  ALTER TABLE pinyin_recall_item_presented ADD COLUMN IF NOT EXISTS batch_mode text;")
        print("  ALTER TABLE pinyin_recall_item_presented ADD COLUMN IF NOT EXISTS batch_character_category text;")
        return

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                ALTER TABLE pinyin_recall_item_presented
                ADD COLUMN IF NOT EXISTS batch_mode text;
                """
            )
            cur.execute(
                """
                ALTER TABLE pinyin_recall_item_presented
                ADD COLUMN IF NOT EXISTS batch_character_category text;
                """
            )
        conn.commit()
        print("Added batch_mode and batch_character_category columns to pinyin_recall_item_presented.")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
