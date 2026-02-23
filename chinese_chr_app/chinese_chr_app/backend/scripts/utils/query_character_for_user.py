#!/usr/bin/env python3
"""
Query Supabase for a character's bank row and answer history for a given user.

Usage (run from backend/):
  python3 scripts/query_character_for_user.py --email "emma@example.com" [--character 亚]
  python3 scripts/query_character_for_user.py --user-id "uuid-here" [--character 亚]

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
Uses auth.users to resolve --email to user_id (Supabase Postgres).
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


def get_user_id_by_email(cur, email: str) -> Optional[str]:
    """Resolve user_id from auth.users by email. Returns None if not found."""
    cur.execute(
        "SELECT id FROM auth.users WHERE email = %s LIMIT 1",
        (email.strip(),),
    )
    row = cur.fetchone()
    return str(row["id"]) if row and row.get("id") else None


def main():
    parser = argparse.ArgumentParser(
        description="Query Supabase for a character's bank row and answer history for a user.",
    )
    parser.add_argument(
        "--character",
        default="亚",
        help="Character to look up (default: 亚)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--email", help="User email (e.g. Emma's) to resolve to user_id")
    group.add_argument("--user-id", help="User UUID (from Supabase Auth)")
    args = parser.parse_args()

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    character = args.character.strip()
    user_id = args.user_id
    if args.email:
        with conn.cursor() as cur:
            user_id = get_user_id_by_email(cur, args.email)
        if not user_id:
            print(f"No user found for email: {args.email!r}")
            sys.exit(1)
        print(f"Resolved email to user_id: {user_id}\n")

    try:
        with conn.cursor() as cur:
            # 1) Bank row
            cur.execute(
                """
                SELECT user_id, character, score, stage, next_due_utc,
                       first_seen_at, last_answered_at,
                       total_correct, total_wrong, total_i_dont_know
                FROM pinyin_recall_character_bank
                WHERE user_id = %s AND character = %s
                """,
                (user_id.strip(), character),
            )
            bank = cur.fetchone()

            # 2) Answer history
            cur.execute(
                """
                SELECT id, session_id, character, selected_choice, correct, latency_ms,
                       i_dont_know, score_before, score_after, category, created_at
                FROM pinyin_recall_item_answered
                WHERE user_id = %s AND character = %s
                ORDER BY created_at ASC
                """,
                (user_id.strip(), character),
            )
            answered = cur.fetchall()

        print("=== pinyin_recall_character_bank ===")
        if bank:
            for k, v in bank.items():
                print(f"  {k}: {v}")
        else:
            print("  (no row)")

        print("\n=== pinyin_recall_item_answered ===")
        if answered:
            for i, row in enumerate(answered, 1):
                print(f"  --- answer {i} ---")
                for k, v in row.items():
                    print(f"    {k}: {v}")
        else:
            print("  (no rows)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
