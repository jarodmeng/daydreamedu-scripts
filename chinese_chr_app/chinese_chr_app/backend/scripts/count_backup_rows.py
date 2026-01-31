#!/usr/bin/env python3
"""Print row counts for hwxnet_characters and all hwxnet_characters_backup_* tables."""

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

def get_connection():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg required: pip install 'psycopg[binary]>=3.1'")
        sys.exit(1)
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL")
        sys.exit(1)
    return psycopg.connect(url, row_factory=dict_row)

def main():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('hwxnet_characters')
                   OR (table_name LIKE 'hwxnet_characters_backup_%')
                ORDER BY table_name
            """)
            tables = [r["table_name"] for r in cur.fetchall()]
        for name in tables:
            with conn.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) AS n FROM "{name}"')
                n = cur.fetchone()["n"]
            print(f"{name}: {n} rows")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
