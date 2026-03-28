#!/usr/bin/env python3
"""
Create the pinyin_recall_unit_bank table for reading-unit persistence.

Stores per-user, per-unit: score, stage, next_due_utc, timestamps, and counts.
Used for queue building and persistence after the polyphonic reading-unit cutover.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/pinyin_recall/create_pinyin_recall_unit_bank_table.py
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


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pinyin_recall_unit_bank (
    user_id text NOT NULL,
    unit_id text NOT NULL,
    character text NOT NULL,
    reading_key text NOT NULL,
    reading_display text NOT NULL,
    score integer NOT NULL DEFAULT 0,
    stage integer NOT NULL DEFAULT 0,
    next_due_utc bigint,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_answered_at timestamptz NOT NULL DEFAULT now(),
    total_correct integer NOT NULL DEFAULT 0,
    total_wrong integer NOT NULL DEFAULT 0,
    total_i_dont_know integer NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, unit_id)
);

CREATE INDEX IF NOT EXISTS idx_pinyin_recall_unit_bank_user_next_due
    ON pinyin_recall_unit_bank (user_id, next_due_utc);

CREATE INDEX IF NOT EXISTS idx_pinyin_recall_unit_bank_user_character
    ON pinyin_recall_unit_bank (user_id, character);
"""


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
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("pinyin_recall_unit_bank table created (or already exists).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
