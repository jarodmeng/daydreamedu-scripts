#!/usr/bin/env python3
"""
Verify common_phrases in hwxnet_characters matches extracted_characters_hwxnet.json.

Compares DB common_phrases (by character) to the 常用词组 field in the JSON.
Run from backend/:
  python3 scripts/characters/verify_common_phrases.py           # verify all rows
  python3 scripts/characters/verify_common_phrases.py --limit 20 # verify first 20 rows only
"""

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

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
HWXNET_JSON = OUTER_APP_DIR / "data" / "extracted_characters_hwxnet.json"


def main():
    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(
        description="Verify hwxnet_characters.common_phrases matches extracted_characters_hwxnet.json 常用词组."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only verify first N rows by zibiao_index (default: all).",
    )
    parser.add_argument(
        "--data-json",
        type=Path,
        default=None,
        help="Path to extracted_characters_hwxnet.json (default: chinese_chr_app/data/...).",
    )
    args = parser.parse_args()

    json_path = args.data_json or HWXNET_JSON
    if not json_path.exists():
        print(f"Error: {json_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Expected: character -> list of phrase strings (normalized)
    expected = {}
    for ch, entry in data.items():
        phrases = entry.get("常用词组")
        if isinstance(phrases, list):
            expected[ch] = [str(p).strip() for p in phrases if p]
        else:
            expected[ch] = []

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL.")
        sys.exit(1)

    conn = psycopg.connect(url)
    try:
        sql = """
            SELECT character, zibiao_index, common_phrases
            FROM hwxnet_characters
            ORDER BY zibiao_index
        """
        if args.limit is not None:
            sql += f" LIMIT {int(args.limit)}"
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

        # Counts
        total = len(rows)
        non_null = sum(1 for r in rows if r[2] is not None)
        non_empty = sum(1 for r in rows if r[2] is not None and len(r[2] or []) > 0)

        print(f"Rows checked: {total}")
        print(f"  common_phrases IS NOT NULL: {non_null}")
        print(f"  common_phrases non-empty:   {non_empty}")

        mismatches = []
        for char, zibiao, db_phrases in rows:
            exp = expected.get(char, [])
            db_list = list(db_phrases) if db_phrases else []
            if db_list != exp:
                mismatches.append((char, zibiao, db_list, exp))

        if mismatches:
            print(f"\nMismatches: {len(mismatches)}")
            for char, zibiao, db_list, exp_list in mismatches[:20]:
                print(f"  {char} (zibiao={zibiao}): DB len={len(db_list)} JSON len={len(exp_list)}")
                if db_list != exp_list:
                    print(f"    DB   (first 3): {db_list[:3]}")
                    print(f"    JSON (first 3): {exp_list[:3]}")
            if len(mismatches) > 20:
                print(f"  ... and {len(mismatches) - 20} more")
            sys.exit(1)

        print("Verified: all checked rows have common_phrases matching extracted_characters_hwxnet.json 常用词组.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
