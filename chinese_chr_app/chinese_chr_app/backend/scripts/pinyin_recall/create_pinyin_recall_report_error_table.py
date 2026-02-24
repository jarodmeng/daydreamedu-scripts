#!/usr/bin/env python3
"""
Create the pinyin_recall_report_error table in Supabase.

Stores user reports when they click "报错" in the pinyin recall game.
Columns: user_id, session_id, batch_id (nullable), character, page (question/wrong/correct), reported_at (default now()).

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/pinyin_recall/create_pinyin_recall_report_error_table.py
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


CREATE_REPORT_ERROR_SQL = """
CREATE TABLE IF NOT EXISTS pinyin_recall_report_error (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL,
    session_id text NOT NULL,
    batch_id uuid,
    character text NOT NULL,
    page text,
    reported_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pinyin_recall_report_error_user_reported
    ON pinyin_recall_report_error (user_id, reported_at DESC);
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
            cur.execute(CREATE_REPORT_ERROR_SQL)
        conn.commit()
        print("pinyin_recall_report_error table created (or already exists).")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
