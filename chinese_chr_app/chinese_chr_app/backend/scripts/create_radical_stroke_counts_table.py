#!/usr/bin/env python3
"""
Create the radical_stroke_counts table in Supabase and insert records from
radical_stroke_counts.json.

Table: radical_stroke_counts (radical text PRIMARY KEY, stroke_count integer NOT NULL)

Requires DATABASE_URL (or SUPABASE_DB_URL) in the environment.

Run from backend/:
  python scripts/create_radical_stroke_counts_table.py
  python scripts/create_radical_stroke_counts_table.py --dry-run
"""

import json
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


def _import_psycopg():
    try:
        import psycopg
        return psycopg
    except ImportError:
        print("psycopg is required. Install with: pip install 'psycopg[binary]>=3.1'")
        sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
DATA_DIR = OUTER_APP_DIR / "data"
RADICAL_STROKE_JSON = DATA_DIR / "radical_stroke_counts.json"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS radical_stroke_counts (
    radical text NOT NULL PRIMARY KEY,
    stroke_count integer NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_radical_stroke_counts_stroke_count
    ON radical_stroke_counts(stroke_count);
"""


def get_connection():
    pg = _import_psycopg()
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print(
            "Set DATABASE_URL or SUPABASE_DB_URL to your Supabase Postgres connection string."
        )
        sys.exit(1)
    return pg.connect(url)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Create radical_stroke_counts table and insert from radical_stroke_counts.json."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate paths and print row count (no DB connection).",
    )
    args = parser.parse_args()

    if not RADICAL_STROKE_JSON.exists():
        print(f"radical_stroke_counts.json not found at {RADICAL_STROKE_JSON}")
        sys.exit(1)

    with open(RADICAL_STROKE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print("Expected radical_stroke_counts.json to be a JSON object (radical -> stroke_count).")
        sys.exit(1)

    rows = []
    for radical, stroke_count in data.items():
        radical = (radical or "").strip()
        if not radical:
            continue
        if not isinstance(stroke_count, int):
            try:
                stroke_count = int(stroke_count)
            except (TypeError, ValueError):
                continue
        rows.append((radical, stroke_count))

    if not rows:
        print("No valid (radical, stroke_count) entries in JSON.")
        sys.exit(1)

    if args.dry_run:
        print(f"Dry run: would insert {len(rows)} rows.")
        for r in rows[:10]:
            print(f"  {r[0]!r} -> {r[1]}")
        if len(rows) > 10:
            print(f"  ... and {len(rows) - 10} more")
        print("Set DATABASE_URL or SUPABASE_DB_URL and run without --dry-run to apply.")
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            conn.commit()
        print("Table radical_stroke_counts created (or already exists).")

        batch_size = 500
        total = len(rows)
        for offset in range(0, total, batch_size):
            batch = rows[offset : offset + batch_size]
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO radical_stroke_counts (radical, stroke_count)
                    VALUES (%s, %s)
                    ON CONFLICT (radical) DO UPDATE SET stroke_count = EXCLUDED.stroke_count
                    """,
                    batch,
                )
                conn.commit()
            if total > batch_size:
                print(f"  Inserted/upserted {min(offset + batch_size, total)} / {total}")
        print(f"Done. Inserted/upserted {len(rows)} records.")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT radical, stroke_count FROM radical_stroke_counts ORDER BY stroke_count, radical LIMIT 10"
            )
            sample = cur.fetchall()
        print("Sample rows in radical_stroke_counts:")
        for r in sample:
            print(f"  {r[0]!r}  stroke_count={r[1]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
