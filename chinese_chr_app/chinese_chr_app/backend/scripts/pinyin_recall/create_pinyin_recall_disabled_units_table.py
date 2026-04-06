#!/usr/bin/env python3
"""
Create the pinyin_recall_disabled_units table in Supabase.

Stores globally disabled reading units for Pinyin Recall. A real-user report can
disable a unit so it no longer appears in future queues or enabled-unit totals.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python3 scripts/pinyin_recall/create_pinyin_recall_disabled_units_table.py
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


CREATE_DISABLED_UNITS_SQL = """
CREATE TABLE IF NOT EXISTS pinyin_recall_disabled_units (
    unit_id text PRIMARY KEY,
    character text NOT NULL,
    disabled_reason text NOT NULL,
    disabled_source text NOT NULL,
    triggering_report_error_id uuid REFERENCES pinyin_recall_report_error (id) ON DELETE SET NULL,
    disabled_by_user_id text NOT NULL,
    disabled_at timestamptz NOT NULL DEFAULT now(),
    notes text
);

CREATE INDEX IF NOT EXISTS idx_pinyin_recall_disabled_units_disabled_at
    ON pinyin_recall_disabled_units (disabled_at DESC);
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
            cur.execute(CREATE_DISABLED_UNITS_SQL)
        conn.commit()
        print("pinyin_recall_disabled_units table created (or already exists).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
