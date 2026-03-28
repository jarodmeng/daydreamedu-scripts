#!/usr/bin/env python3
"""
Backfill unit-aware columns for legacy pinyin_recall_item_answered rows.

Derivation rule:
- Join each answered row with unit_id IS NULL to the latest preceding
  pinyin_recall_item_presented row in the same (user_id, session_id, character).
- Copy unit_id, reading_key, and reading_display from that presented row.

Creates a backup table before modifying unless --no-backup is passed.

Run from backend/:
  python3 scripts/pinyin_recall/backfill_pinyin_recall_item_answered_unit_ids.py
  python3 scripts/pinyin_recall/backfill_pinyin_recall_item_answered_unit_ids.py --dry-run
  python3 scripts/pinyin_recall/backfill_pinyin_recall_item_answered_unit_ids.py --no-backup
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


def main():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    no_backup = "--no-backup" in sys.argv

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH null_answered AS (
                  SELECT a.id, a.user_id, a.session_id, a.character, a.created_at
                  FROM pinyin_recall_item_answered a
                  WHERE a.unit_id IS NULL
                ),
                matched AS (
                  SELECT
                    a.id AS answered_id,
                    p.unit_id,
                    p.reading_key,
                    p.reading_display,
                    ROW_NUMBER() OVER (
                      PARTITION BY a.id
                      ORDER BY p.created_at DESC, p.id DESC
                    ) AS rn
                  FROM null_answered a
                  LEFT JOIN pinyin_recall_item_presented p
                    ON p.user_id = a.user_id
                   AND p.session_id = a.session_id
                   AND p.character = a.character
                   AND p.created_at <= a.created_at
                )
                SELECT answered_id, unit_id, reading_key, reading_display
                FROM matched
                WHERE rn = 1
                ORDER BY answered_id
                """
            )
            rows = cur.fetchall()

        updates = []
        skipped = []
        for row in rows:
            answered_id = row.get("answered_id")
            unit_id = (row.get("unit_id") or "").strip()
            reading_key = (row.get("reading_key") or "").strip()
            reading_display = (row.get("reading_display") or "").strip()
            if not answered_id:
                continue
            if not unit_id:
                skipped.append((answered_id, "missing_presented_unit"))
                continue
            updates.append((unit_id, reading_key or None, reading_display or None, answered_id))

        if dry_run:
            print(f"[dry-run] Would update {len(updates)} item_answered rows.")
            print(f"[dry-run] Would skip {len(skipped)} rows.")
            for sample in skipped[:20]:
                print("  skip:", sample)
            return

        with conn.cursor() as cur:
            if not no_backup:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                backup = f"pinyin_recall_item_answered_backup_{ts}"
                cur.execute(f'CREATE TABLE "{backup}" AS SELECT * FROM pinyin_recall_item_answered')
                print("Backup table created:", backup)

            cur.executemany(
                """
                UPDATE pinyin_recall_item_answered
                SET unit_id = %s,
                    reading_key = %s,
                    reading_display = %s
                WHERE id = %s
                  AND unit_id IS NULL
                """,
                updates,
            )
        conn.commit()
        print(f"Backfilled item_answered rows: {len(updates)}")
        if skipped:
            print(f"Skipped rows: {len(skipped)}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
