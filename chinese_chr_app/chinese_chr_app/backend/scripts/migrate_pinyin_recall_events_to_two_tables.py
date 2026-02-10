#!/usr/bin/env python3
"""
One-off: copy existing rows from pinyin_recall_events into the two new tables.

Run after create_pinyin_recall_log_tables.py. Copies:
  - event = 'item_presented' -> pinyin_recall_item_presented
  - event = 'item_answered' -> pinyin_recall_item_answered

Then you can drop pinyin_recall_events if desired. Requires DATABASE_URL/SUPABASE_DB_URL.

Run from backend/:
  python scripts/migrate_pinyin_recall_events_to_two_tables.py
  python scripts/migrate_pinyin_recall_events_to_two_tables.py --dry-run   # no writes
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


INSERT_PRESENTED_SQL = """
INSERT INTO pinyin_recall_item_presented (user_id, session_id, character, prompt_type, correct_choice, choices, created_at)
SELECT user_id, session_id, character, prompt_type, correct_choice, choices, created_at
FROM pinyin_recall_events
WHERE event = 'item_presented';
"""

INSERT_ANSWERED_SQL = """
INSERT INTO pinyin_recall_item_answered (user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before, score_after, created_at)
SELECT user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before, score_after, created_at
FROM pinyin_recall_events
WHERE event = 'item_answered';
"""


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("Dry run: no writes.")

    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install with: pip install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            if dry_run:
                cur.execute("SELECT COUNT(*) FROM pinyin_recall_events WHERE event = 'item_presented'")
                n_p = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM pinyin_recall_events WHERE event = 'item_answered'")
                n_a = cur.fetchone()[0]
                print(f"Would copy: {n_p} item_presented, {n_a} item_answered")
            else:
                cur.execute(INSERT_PRESENTED_SQL)
                n_p = cur.rowcount
                cur.execute(INSERT_ANSWERED_SQL)
                n_a = cur.rowcount
                conn.commit()
                print(f"Copied: {n_p} item_presented, {n_a} item_answered")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
