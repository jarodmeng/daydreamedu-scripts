#!/usr/bin/env python3
"""
Backfill batch_id for pinyin_recall_item_presented using created_at clustering.

Rows in the same batch are inserted within ~1 second. Gaps between batches are
typically 20+ seconds (user answering questions). We cluster by session_id and
created_at: when the gap to the previous row exceeds GAP_THRESHOLD_SECONDS, we
start a new batch.

Creates backup table pinyin_recall_item_presented_backup_YYYYMMDD_HHMMSS before
modifying. Use --no-backup to skip.

Requires batch_id column to exist. Run add_pinyin_recall_batch_id_column.py first.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/backfill_pinyin_recall_batch_id.py
  python3 scripts/backfill_pinyin_recall_batch_id.py --dry-run
  python3 scripts/backfill_pinyin_recall_batch_id.py --gap 10   # seconds between batches
  python3 scripts/backfill_pinyin_recall_batch_id.py --no-backup   # skip backup table
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

GAP_THRESHOLD_SECONDS = 5


def main():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    no_backup = "--no-backup" in sys.argv
    gap_sec = GAP_THRESHOLD_SECONDS
    for i, arg in enumerate(sys.argv):
        if arg == "--gap" and i + 1 < len(sys.argv):
            try:
                gap_sec = int(sys.argv[i + 1])
            except ValueError:
                print("--gap must be an integer (seconds)")
                sys.exit(1)
            break

    if dry_run:
        print("Dry run: no updates applied.")
    elif no_backup:
        print("--no-backup: skipping backup table creation.")
    print(f"Gap threshold: {gap_sec} seconds (rows within this = same batch)")

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, session_id, created_at
                FROM pinyin_recall_item_presented
                WHERE batch_id IS NULL
                ORDER BY session_id, created_at
                """
            )
            rows = cur.fetchall()

        if not rows:
            print("No rows with batch_id IS NULL. Nothing to backfill.")
            return

        print(f"Found {len(rows)} rows with batch_id IS NULL")

        # Cluster into batches: same session_id, gap <= threshold
        batches_to_update = []
        current_batch_ids = []
        prev_row = None

        for row in rows:
            row_id = row["id"]
            session_id = row["session_id"]
            created_at = row["created_at"]

            if prev_row is None:
                current_batch_ids = [row_id]
            elif prev_row["session_id"] != session_id:
                batches_to_update.append(current_batch_ids)
                current_batch_ids = [row_id]
            else:
                gap = (created_at - prev_row["created_at"]).total_seconds()
                if gap > gap_sec:
                    batches_to_update.append(current_batch_ids)
                    current_batch_ids = [row_id]
                else:
                    current_batch_ids.append(row_id)

            prev_row = row

        if current_batch_ids:
            batches_to_update.append(current_batch_ids)

        print(f"Inferred {len(batches_to_update)} batches")

        if dry_run:
            sample = batches_to_update[:5]
            for i, ids in enumerate(sample):
                print(f"  Batch {i + 1}: {len(ids)} rows")
            if len(batches_to_update) > 5:
                print(f"  ... and {len(batches_to_update) - 5} more")
            return

        # Create backup table before modifying in-place
        if not no_backup:
            backup_name = f"pinyin_recall_item_presented_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            with conn.cursor() as cur:
                cur.execute(f'CREATE TABLE "{backup_name}" AS SELECT * FROM pinyin_recall_item_presented')
            conn.commit()
            print(f"Backup table created: {backup_name}")

        updated = 0
        with conn.cursor() as cur:
            for batch_ids in batches_to_update:
                batch_uuid = str(uuid.uuid4())
                cur.execute(
                    """
                    UPDATE pinyin_recall_item_presented
                    SET batch_id = %s::uuid
                    WHERE id = ANY(%s)
                    """,
                    (batch_uuid, batch_ids),
                )
                updated += cur.rowcount

        conn.commit()
        print(f"Updated {updated} rows with batch_id.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
