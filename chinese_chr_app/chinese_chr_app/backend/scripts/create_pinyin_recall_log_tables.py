#!/usr/bin/env python3
"""
Create the two pinyin recall log tables in Supabase (two-table design).

- pinyin_recall_item_presented: when a character is shown (user_id, session_id, character, prompt_type, correct_choice, choices)
- pinyin_recall_item_answered: when user submits an answer (user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before, score_after)

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python scripts/create_pinyin_recall_log_tables.py
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


CREATE_ITEM_PRESENTED_SQL = """
CREATE TABLE IF NOT EXISTS pinyin_recall_item_presented (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL,
    session_id text NOT NULL,
    character text NOT NULL,
    prompt_type text NOT NULL,
    correct_choice text NOT NULL,
    choices jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pinyin_recall_item_presented_user_created
    ON pinyin_recall_item_presented (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pinyin_recall_item_presented_session
    ON pinyin_recall_item_presented (session_id, created_at);
"""

CREATE_ITEM_ANSWERED_SQL = """
CREATE TABLE IF NOT EXISTS pinyin_recall_item_answered (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL,
    session_id text NOT NULL,
    character text NOT NULL,
    selected_choice text,
    correct boolean NOT NULL,
    latency_ms integer,
    i_dont_know boolean NOT NULL,
    score_before integer,
    score_after integer,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pinyin_recall_item_answered_user_created
    ON pinyin_recall_item_answered (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pinyin_recall_item_answered_session
    ON pinyin_recall_item_answered (session_id, created_at);
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
            cur.execute(CREATE_ITEM_PRESENTED_SQL)
            cur.execute(CREATE_ITEM_ANSWERED_SQL)
        conn.commit()
        print("pinyin_recall_item_presented and pinyin_recall_item_answered tables created (or already exist).")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
