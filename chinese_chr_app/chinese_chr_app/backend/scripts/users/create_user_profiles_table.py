#!/usr/bin/env python3
"""
Create the user_profiles table in Supabase for storing per-user profile data
currently limited to display_name used on the 我的 (Profile) page.

Schema:
  user_profiles (
      user_id    text primary key,
      display_name text not null,
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now()
  )

Requires DATABASE_URL (or SUPABASE_DB_URL) in the environment.

Run from backend/:
  python3 scripts/users/create_user_profiles_table.py
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
  # dotenv is optional; fall back to plain env
  pass


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id text PRIMARY KEY,
    display_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""

ALTER_ADD_COLUMNS_SQL = """
ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS display_name text NOT NULL DEFAULT 'User',
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
"""


def main() -> None:
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
    print("user_profiles table created (or already exists).")
  except Exception as e:
    conn.rollback()
    # If table already exists, continue to ALTER step; otherwise re-raise.
    if "already exists" not in str(e).lower():
      raise
    print("user_profiles table already exists.")

  try:
    with conn.cursor() as cur:
      cur.execute(ALTER_ADD_COLUMNS_SQL)
    conn.commit()
    print("user_profiles: columns ensured (display_name, created_at, updated_at).")
  except Exception as e:
    conn.rollback()
    # On older Postgres, IF NOT EXISTS may not be supported; warn but don't fail hard.
    if "already exists" not in str(e).lower() and "duplicate_column" not in str(e).lower():
      print(f"user_profiles: ALTER TABLE failed: {e}")
      raise
    print("user_profiles: columns already present.")
  finally:
    conn.close()


if __name__ == "__main__":
  main()

