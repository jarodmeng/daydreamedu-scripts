#!/usr/bin/env python3
"""
Delete all rows where user_id = 'local-dev' from Supabase tables that have user_id.

Tables: character_views, pinyin_recall_character_bank, pinyin_recall_item_presented,
pinyin_recall_item_answered, pinyin_recall_events (if exists).

Creates backup tables of the deleted rows (e.g. character_views_local_dev_backup_YYYYMMDD_HHMMSS)
before deleting. Use --no-backup to skip.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python scripts/delete_local_dev_rows.py
  python scripts/delete_local_dev_rows.py --dry-run
  python scripts/delete_local_dev_rows.py --no-backup
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

USER_ID = "local-dev"

TABLES = [
    "character_views",
    "pinyin_recall_character_bank",
    "pinyin_recall_item_presented",
    "pinyin_recall_item_answered",
    "pinyin_recall_events",
]


def main():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg is required. Install with: pip install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    no_backup = "--no-backup" in sys.argv

    if dry_run:
        print("Dry run: no deletes applied.")
    elif no_backup:
        print("--no-backup: skipping backup table creation.")

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        for table in TABLES:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s) AS ok",
                    (table,),
                )
                if not cur.fetchone()["ok"]:
                    if dry_run:
                        print(f"  {table}: table does not exist, skip")
                    continue

                cur.execute(f'SELECT COUNT(*) AS n FROM "{table}" WHERE user_id = %s', (USER_ID,))
                count = cur.fetchone()["n"]

            if dry_run:
                print(f"  {table}: {count} rows would be deleted")
                continue

            if count == 0:
                print(f"  {table}: 0 rows (skip)")
                continue

            if not no_backup:
                backup_name = f"{table}_local_dev_backup_{ts}"
                with conn.cursor() as cur:
                    cur.execute(
                        f'CREATE TABLE "{backup_name}" AS SELECT * FROM "{table}" WHERE user_id = %s',
                        (USER_ID,),
                    )
                conn.commit()
                print(f"  {table}: backup {backup_name} ({count} rows)")

            with conn.cursor() as cur:
                cur.execute(f'DELETE FROM "{table}" WHERE user_id = %s', (USER_ID,))
                deleted = cur.rowcount
            conn.commit()
            print(f"  {table}: deleted {deleted} rows")

    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
