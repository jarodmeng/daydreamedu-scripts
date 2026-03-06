#!/usr/bin/env python3
"""
Query recent rows from pinyin_recall_report_error, excluding local-dev.

Usage (run from backend/):
  python3 scripts/utils/query_pinyin_recall_report_error.py [--days 2] [--limit 50]

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
"""

import argparse
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

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="List recent pinyin_recall_report_error rows (excluding local-dev).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=2,
        help="Only include reports from the last N days (default: 2)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max rows to return (default: 50)",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, session_id, batch_id, character, page, reported_at
                FROM pinyin_recall_report_error r
                WHERE r.user_id != 'local-dev'
                  AND r.reported_at >= now() - interval '1 day' * %s
                ORDER BY r.reported_at DESC
                LIMIT %s
                """,
                (args.days, args.limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print(f"No report errors in the last {args.days} day(s) (excluding local-dev).")
        return

    print(f"Report errors in the last {args.days} day(s), excluding local-dev, newest first (limit {args.limit}):\n")
    for r in rows:
        print(f"  {r['reported_at']}  user={r['user_id'][:8]}…  char={r['character']}  page={r['page']}  session={r['session_id'][:8]}…")
    print(f"\nTotal: {len(rows)} row(s).")


if __name__ == "__main__":
    main()
