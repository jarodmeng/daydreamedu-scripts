#!/usr/bin/env python3
"""
Create the pinyin_recall_events table in Supabase (LEGACY — single table).

**Deprecated:** Prefer the two-table design: use scripts/create_pinyin_recall_log_tables.py
to create pinyin_recall_item_presented and pinyin_recall_item_answered. The app and
upload script now use the two tables. This script remains for reference or if you
need to create the old table (e.g. before running migrate_pinyin_recall_events_to_two_tables.py).

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python scripts/create_pinyin_recall_events_table.py
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


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pinyin_recall_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event text NOT NULL,
    user_id text NOT NULL,
    session_id text,
    character text,
    prompt_type text,
    correct_choice text,
    choices jsonb,
    selected_choice text,
    correct boolean,
    latency_ms integer,
    i_dont_know boolean,
    score_before integer,
    score_after integer,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pinyin_recall_events_user_created
    ON pinyin_recall_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pinyin_recall_events_session
    ON pinyin_recall_events (session_id, created_at);
"""


def main():
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
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("pinyin_recall_events table created (or already exists).")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
