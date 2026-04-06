#!/usr/bin/env python3
"""
Create the user_prioritized_characters table in Supabase.

Stores per-user phase-1 Pinyin Recall priority targets used to front-load eligible
new items without changing batch slot counts.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/pinyin_recall/create_user_prioritized_characters_table.py
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


CREATE_USER_PRIORITIES_SQL = """
CREATE TABLE IF NOT EXISTS user_prioritized_characters (
    id bigserial PRIMARY KEY,
    user_id text NOT NULL,
    character text NOT NULL,
    reading text,
    priority integer NOT NULL DEFAULT 0,
    label text,
    source text,
    note text,
    active boolean NOT NULL DEFAULT TRUE,
    expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT user_prioritized_characters_target_unique
        UNIQUE NULLS NOT DISTINCT (user_id, character, reading)
);

CREATE INDEX IF NOT EXISTS idx_user_prioritized_characters_user_active
    ON user_prioritized_characters (user_id, active)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_user_prioritized_characters_user_priority
    ON user_prioritized_characters (user_id, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_user_prioritized_characters_user_character_reading
    ON user_prioritized_characters (user_id, character, reading)
    WHERE active = TRUE;
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
            cur.execute(CREATE_USER_PRIORITIES_SQL)
        conn.commit()
        print("user_prioritized_characters table created (or already exists).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
