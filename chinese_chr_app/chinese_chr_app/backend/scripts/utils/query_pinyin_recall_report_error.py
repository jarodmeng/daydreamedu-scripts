#!/usr/bin/env python3
"""
Query recent rows from pinyin_recall_report_error, excluding local-dev and genrong.meng@gmail.com.

Usage (run from backend/):
  python3 scripts/utils/query_pinyin_recall_report_error.py [--limit 50]

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.

Note: Of the remaining reports, 玄 is considered a misreport. Reports to address: 沈 (stem/多音字),
卢 (例词 from 基本字义 citation instead of 常用词组).
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
        description="List recent pinyin_recall_report_error rows (excluding local-dev and genrong.meng@gmail.com).",
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
                  AND (r.user_id NOT IN (SELECT id::text FROM auth.users WHERE email = 'genrong.meng@gmail.com'))
                ORDER BY r.reported_at DESC
                LIMIT %s
                """,
                (args.limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("No recent error reports (excluding local-dev and genrong.meng@gmail.com).")
        return

    print(f"Recent error reports (excluding local-dev and genrong.meng@gmail.com), newest first (limit {args.limit}):\n")
    for r in rows:
        print(f"  {r['reported_at']}  user={r['user_id'][:8]}…  char={r['character']}  page={r['page']}  session={r['session_id'][:8]}…")
    print(f"\nTotal: {len(rows)} row(s).")


if __name__ == "__main__":
    main()
