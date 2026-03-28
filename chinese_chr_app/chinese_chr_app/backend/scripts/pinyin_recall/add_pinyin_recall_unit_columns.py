#!/usr/bin/env python3
"""
Add unit-aware columns to pinyin_recall log/report tables.

Tables modified:
- pinyin_recall_item_presented
- pinyin_recall_item_answered
- pinyin_recall_report_error

Creates backup tables before modifying unless --no-backup is passed.

Run from backend/:
  python3 scripts/pinyin_recall/add_pinyin_recall_unit_columns.py
  python3 scripts/pinyin_recall/add_pinyin_recall_unit_columns.py --dry-run
  python3 scripts/pinyin_recall/add_pinyin_recall_unit_columns.py --no-backup
"""

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


ALTERS = [
    "ALTER TABLE pinyin_recall_item_presented ADD COLUMN IF NOT EXISTS unit_id text",
    "ALTER TABLE pinyin_recall_item_presented ADD COLUMN IF NOT EXISTS reading_key text",
    "ALTER TABLE pinyin_recall_item_presented ADD COLUMN IF NOT EXISTS reading_display text",
    "CREATE INDEX IF NOT EXISTS idx_pinyin_recall_item_presented_user_unit ON pinyin_recall_item_presented (user_id, unit_id) WHERE unit_id IS NOT NULL",
    "ALTER TABLE pinyin_recall_item_answered ADD COLUMN IF NOT EXISTS unit_id text",
    "ALTER TABLE pinyin_recall_item_answered ADD COLUMN IF NOT EXISTS reading_key text",
    "ALTER TABLE pinyin_recall_item_answered ADD COLUMN IF NOT EXISTS reading_display text",
    "CREATE INDEX IF NOT EXISTS idx_pinyin_recall_item_answered_user_unit ON pinyin_recall_item_answered (user_id, unit_id, created_at) WHERE unit_id IS NOT NULL",
    "ALTER TABLE pinyin_recall_report_error ADD COLUMN IF NOT EXISTS unit_id text",
]


def main():
    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    no_backup = "--no-backup" in sys.argv

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    if dry_run:
        print("Dry run: no schema changes applied.")
    elif no_backup:
        print("--no-backup: skipping backup table creation.")

    if dry_run:
        if not no_backup:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            print(f'Would create backup: pinyin_recall_item_presented_backup_{ts}')
            print(f'Would create backup: pinyin_recall_item_answered_backup_{ts}')
            print(f'Would create backup: pinyin_recall_report_error_backup_{ts}')
        for stmt in ALTERS:
            print(f"Would run: {stmt};")
        return

    conn = psycopg.connect(url)
    try:

        with conn.cursor() as cur:
            if not no_backup:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                backups = {
                    "pinyin_recall_item_presented": f"pinyin_recall_item_presented_backup_{ts}",
                    "pinyin_recall_item_answered": f"pinyin_recall_item_answered_backup_{ts}",
                    "pinyin_recall_report_error": f"pinyin_recall_report_error_backup_{ts}",
                }
                for table, backup in backups.items():
                    cur.execute(f'CREATE TABLE "{backup}" AS SELECT * FROM {table}')
                print("Backup tables created:", ", ".join(backups.values()))

            for stmt in ALTERS:
                cur.execute(stmt)
        conn.commit()
        print("Added unit-aware columns to pinyin_recall log/report tables.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
