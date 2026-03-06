#!/usr/bin/env python3
"""
Verify pinyin and searchable_pinyin in hwxnet_characters match
extracted_characters_hwxnet.json for the given character(s).

Recomputes expected searchable_pinyin from the JSON 拼音 using the same
logic as add_searchable_pinyin_column and compares to the DB. Use after
a primary pinyin update to confirm the table is in sync with the JSON.

Run from backend/:
  python3 scripts/characters/verify_hwxnet_pinyin.py <character>
  python3 scripts/characters/verify_hwxnet_pinyin.py --all

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
"""

import argparse
import json
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

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from add_searchable_pinyin_column import compute_searchable_pinyin_for_row

BACKEND_DIR = SCRIPT_DIR.parent.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
HWXNET_JSON = OUTER_APP_DIR / "data" / "extracted_characters_hwxnet.json"


def main():
    parser = argparse.ArgumentParser(
        description="Verify hwxnet_characters pinyin and searchable_pinyin match extracted_characters_hwxnet.json.",
    )
    parser.add_argument(
        "character",
        nargs="?",
        default=None,
        help="Single Hanzi to verify (omit if using --all).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Verify all characters present in the JSON.",
    )
    args = parser.parse_args()

    if args.all and args.character:
        print("Use either <character> or --all, not both.", file=sys.stderr)
        sys.exit(1)
    if not args.all and not (args.character and args.character.strip()):
        parser.print_help()
        sys.exit(1)

    if not HWXNET_JSON.exists():
        print(f"JSON not found: {HWXNET_JSON}", file=sys.stderr)
        sys.exit(1)
    with open(HWXNET_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    if args.all:
        chars_to_check = list(data.keys())
    else:
        char = args.character.strip()
        if len(char) != 1:
            print("Character must be exactly one Hanzi.", file=sys.stderr)
            sys.exit(1)
        if char not in data:
            print(f"Character {char} not found in JSON.", file=sys.stderr)
            sys.exit(1)
        chars_to_check = [char]

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT character, pinyin, searchable_pinyin
                FROM hwxnet_characters
                WHERE character = ANY(%s)
                """,
                (chars_to_check,),
            )
            rows = {r["character"]: r for r in cur.fetchall()}
    finally:
        conn.close()

    errors = []
    for ch in chars_to_check:
        entry = data.get(ch)
        if not entry:
            continue
        pinyin_list = entry.get("拼音") or []
        expected_searchable = sorted(compute_searchable_pinyin_for_row(pinyin_list)) if pinyin_list else []
        row = rows.get(ch)
        if not row:
            errors.append(f"{ch}: no row in hwxnet_characters")
            continue
        db_pinyin = row.get("pinyin")
        if isinstance(db_pinyin, str):
            try:
                db_pinyin = json.loads(db_pinyin) if db_pinyin.strip() else []
            except Exception:
                db_pinyin = [db_pinyin] if db_pinyin.strip() else []
        if not isinstance(db_pinyin, list):
            db_pinyin = list(db_pinyin) if db_pinyin else []
        db_searchable = row.get("searchable_pinyin")
        if isinstance(db_searchable, str):
            try:
                db_searchable = json.loads(db_searchable) if db_searchable.strip() else []
            except Exception:
                db_searchable = []
        if not isinstance(db_searchable, list):
            db_searchable = list(db_searchable) if db_searchable else []
        db_searchable = sorted(db_searchable)

        if pinyin_list != db_pinyin:
            errors.append(f"{ch}: pinyin mismatch  JSON={pinyin_list}  DB={db_pinyin}")
        if expected_searchable != db_searchable:
            errors.append(f"{ch}: searchable_pinyin mismatch  expected={expected_searchable}  DB={db_searchable}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)

    if args.all:
        print(f"Verified: pinyin and searchable_pinyin match JSON for {len(chars_to_check)} character(s).")
    else:
        print(f"Verified: {chars_to_check[0]} pinyin and searchable_pinyin match JSON.")


if __name__ == "__main__":
    main()
