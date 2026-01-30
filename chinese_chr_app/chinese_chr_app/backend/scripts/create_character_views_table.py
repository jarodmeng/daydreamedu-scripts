#!/usr/bin/env python3
"""
Create the character_views table in Supabase for logging which characters
logged-in users view on the Search page (user_id, character, viewed_at, display_name).

Requires DATABASE_URL (or SUPABASE_DB_URL) in the environment.
Backend must have USE_DATABASE=true for the log endpoint to write to this table.

Run from backend/:
  python scripts/create_character_views_table.py
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
CREATE TABLE IF NOT EXISTS character_views (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL,
    character text NOT NULL,
    viewed_at timestamptz NOT NULL DEFAULT now(),
    display_name text
);

CREATE INDEX IF NOT EXISTS idx_character_views_user_viewed
    ON character_views (user_id, viewed_at DESC);
"""

# Add display_name to existing tables (run after CREATE; ignore if column already exists)
ALTER_ADD_DISPLAY_NAME_SQL = "ALTER TABLE character_views ADD COLUMN display_name text;"


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
        print("character_views table created (or already exists).")
    except Exception as e:
        conn.rollback()
        if "already exists" not in str(e).lower():
            raise
        print("character_views table already exists.")
    try:
        with conn.cursor() as cur:
            cur.execute(ALTER_ADD_DISPLAY_NAME_SQL)
        conn.commit()
        print("character_views: display_name column added.")
    except Exception as e:
        conn.rollback()
        if "already exists" not in str(e).lower() and "duplicate_column" not in str(e).lower():
            raise
        print("character_views: display_name column already present.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
