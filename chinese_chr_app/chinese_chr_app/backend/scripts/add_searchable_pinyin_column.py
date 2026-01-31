#!/usr/bin/env python3
"""
Add searchable_pinyin column to hwxnet_characters and backfill from pinyin.

This script only sets the searchable_pinyin column. It does not modify any other
column in the table (pinyin, character, radical, strokes, index, etc.).

Maps each pinyin reading (e.g. "bà", "wŏ") to searchable forms: base (e.g. "ba", "wo")
and base + tone digit (e.g. "ba4", "wo3"). Neutral tone produces both "ma0" and "ma5".
ü/ǖ/ǘ/ǚ/ǜ normalize to v in base. Supports breve variants (ă ĕ ŏ ĭ ŭ) as 3rd tone.

Before modifying the table, the script creates a backup table
hwxnet_characters_backup_YYYYMMDD_HHMMSS. Use --no-backup to skip.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python scripts/add_searchable_pinyin_column.py
  python scripts/add_searchable_pinyin_column.py --dry-run   # no DB writes, print sample
  python scripts/add_searchable_pinyin_column.py --no-backup   # skip backup table
  python scripts/add_searchable_pinyin_column.py --skip-filled   # only fill rows where searchable_pinyin IS NULL
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

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


# Accented vowel -> (base_letter, tone). Tone: 1-4, 0 = neutral. ü/ǖ/ǘ/ǚ/ǜ -> v
_ACCENT_TO_BASE_AND_TONE = {
    "ā": ("a", 1), "á": ("a", 2), "ǎ": ("a", 3), "à": ("a", 4), "ă": ("a", 3),
    "ē": ("e", 1), "é": ("e", 2), "ě": ("e", 3), "è": ("e", 4), "ĕ": ("e", 3),
    "ī": ("i", 1), "í": ("i", 2), "ǐ": ("i", 3), "ì": ("i", 4), "ĭ": ("i", 3),
    "ō": ("o", 1), "ó": ("o", 2), "ǒ": ("o", 3), "ò": ("o", 4), "ŏ": ("o", 3),
    "ū": ("u", 1), "ú": ("u", 2), "ǔ": ("u", 3), "ù": ("u", 4), "ŭ": ("u", 3),
    "ǖ": ("v", 1), "ǘ": ("v", 2), "ǚ": ("v", 3), "ǜ": ("v", 4),
    "ü": ("v", 0),
}
# Plain vowels (no accent) -> neutral
_PLAIN_VOWELS = set("aeiouv")


def _pinyin_to_base_and_tone(s: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Normalize pinyin string to (base_syllable, tone).
    base_syllable uses v for ü. tone is 1-4 or 0 for neutral.
    Returns (None, None) if no vowel with tone found (invalid).
    """
    if not s or not s.strip():
        return None, None
    s = s.strip().lower()
    base_chars = []
    tone = 0  # neutral by default
    for c in s:
        if c in _ACCENT_TO_BASE_AND_TONE:
            b, t = _ACCENT_TO_BASE_AND_TONE[c]
            base_chars.append(b)
            tone = t
        elif c in _PLAIN_VOWELS:
            base_chars.append(c)
        elif c == "v" and "v" in _PLAIN_VOWELS:
            base_chars.append("v")
        else:
            base_chars.append(c)
    base = "".join(base_chars)
    return base if base else None, tone


def pinyin_to_searchable_forms(pinyin_str: str) -> List[str]:
    """
    Convert one pinyin string (e.g. "bà", "wŏ", "ma") to list of searchable keys.
    Returns e.g. ["ba", "ba4"] for "bà", ["wo", "wo3"] for "wŏ", ["ma", "ma0", "ma5"] for neutral.
    """
    base, tone = _pinyin_to_base_and_tone(pinyin_str)
    if base is None:
        return []
    out = [base]
    if tone == 0:
        out.append(f"{base}0")
        out.append(f"{base}5")
    else:
        out.append(f"{base}{tone}")
    return out


def compute_searchable_pinyin_for_row(pinyin_list: list) -> List[str]:
    """
    Given pinyin column value (list of strings like ["bà", "wŏ"]), return
    sorted list of unique searchable keys (e.g. ["ba", "ba4", "wo", "wo3"]).
    """
    if not pinyin_list:
        return []
    seen = set()
    for s in pinyin_list:
        if isinstance(s, str):
            for key in pinyin_to_searchable_forms(s):
                seen.add(key)
        elif isinstance(s, (list, tuple)):
            for item in s:
                if isinstance(item, str):
                    for key in pinyin_to_searchable_forms(item):
                        seen.add(key)
    return sorted(seen)


def get_connection():
    pg = _import_psycopg()
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL to your Supabase Postgres connection string.")
        sys.exit(1)
    return pg.connect(url)


ADD_COLUMN_SQL = """
ALTER TABLE hwxnet_characters
ADD COLUMN IF NOT EXISTS searchable_pinyin jsonb;
"""

CREATE_GIN_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_hwxnet_searchable_pinyin
ON hwxnet_characters USING GIN (searchable_pinyin);
"""


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Add searchable_pinyin to hwxnet_characters and backfill from pinyin."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not connect or write to DB; only print sample normalizations.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup table before modifying hwxnet_characters.",
    )
    parser.add_argument(
        "--skip-filled",
        action="store_true",
        help="Only backfill rows where searchable_pinyin IS NULL; do not overwrite existing values.",
    )
    args = parser.parse_args()

    if args.dry_run:
        # Sample from HWXNet JSON to show normalization
        SCRIPT_DIR = Path(__file__).resolve().parent
        BACKEND_DIR = SCRIPT_DIR.parent
        OUTER_APP_DIR = BACKEND_DIR.parent.parent
        DATA_DIR = OUTER_APP_DIR / "data"
        HWXNET_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
        if not HWXNET_JSON.exists():
            print(f"Dry run: {HWXNET_JSON} not found; showing built-in samples only.")
            samples = [("bà",), ("wŏ",), ("mā",), ("lǚ",), ("ma",), ("dà", "dài")]
        else:
            with open(HWXNET_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = list(data.items())[:12]
            samples = [tuple(entry.get("拼音") or []) for _k, entry in items]
        print("Dry run: sample pinyin -> searchable_pinyin")
        for py_list in samples:
            if not py_list:
                continue
            keys = compute_searchable_pinyin_for_row(list(py_list))
            print(f"  {list(py_list)} -> {keys}")
        print("Set DATABASE_URL and run without --dry-run to add column and backfill.")
        return

    conn = get_connection()
    try:
        if not args.no_backup:
            backup_name = f"hwxnet_characters_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            with conn.cursor() as cur:
                cur.execute(f'CREATE TABLE {backup_name} AS SELECT * FROM hwxnet_characters')
                conn.commit()
            print(f"Backup table created: {backup_name}")

        with conn.cursor() as cur:
            cur.execute(ADD_COLUMN_SQL)
            conn.commit()
        print("Column searchable_pinyin added (or already exists).")

        with conn.cursor() as cur:
            if args.skip_filled:
                cur.execute(
                    "SELECT character, zibiao_index, pinyin FROM hwxnet_characters WHERE searchable_pinyin IS NULL ORDER BY zibiao_index"
                )
            else:
                cur.execute(
                    "SELECT character, zibiao_index, pinyin FROM hwxnet_characters ORDER BY zibiao_index"
                )
            rows = cur.fetchall()

        updated = 0
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            with conn.cursor() as cur:
                for r in batch:
                    ch, zibiao, pinyin_raw = r[0], r[1], r[2]
                    if isinstance(pinyin_raw, list):
                        pinyin_list = pinyin_raw
                    elif isinstance(pinyin_raw, str):
                        try:
                            pinyin_list = json.loads(pinyin_raw) if pinyin_raw.strip() else []
                        except Exception:
                            pinyin_list = [pinyin_raw] if pinyin_raw.strip() else []
                    else:
                        pinyin_list = [pinyin_raw] if pinyin_raw else []
                    searchable = compute_searchable_pinyin_for_row(pinyin_list)
                    cur.execute(
                        "UPDATE hwxnet_characters SET searchable_pinyin = %s::jsonb WHERE character = %s AND zibiao_index = %s",
                        (json.dumps(searchable) if searchable else None, ch, zibiao),
                    )
                    updated += 1
            conn.commit()
            if len(rows) > batch_size:
                print(f"  Updated {min(i + batch_size, len(rows))} / {len(rows)}")

        if args.skip_filled:
            print(f"Backfilled searchable_pinyin for {updated} rows (only rows where searchable_pinyin was NULL).")
        else:
            print(f"Backfilled searchable_pinyin for {updated} rows.")

        with conn.cursor() as cur:
            cur.execute(CREATE_GIN_INDEX_SQL)
            conn.commit()
        print("GIN index idx_hwxnet_searchable_pinyin created (or already exists).")

        # Show database results: sample rows with searchable_pinyin
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT character, zibiao_index, pinyin, searchable_pinyin
                FROM hwxnet_characters
                ORDER BY zibiao_index
                LIMIT 15
                """
            )
            sample_rows = cur.fetchall()
        print("\nSample rows (character, zibiao_index, pinyin, searchable_pinyin):")
        for r in sample_rows:
            ch, zibiao, pinyin, searchable = r[0], r[1], r[2], r[3]
            print(f"  {ch}  zibiao={zibiao}  pinyin={pinyin}  searchable_pinyin={searchable}")

        # Count non-null and sample a character with multiple readings
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM hwxnet_characters WHERE searchable_pinyin IS NOT NULL"
            )
            non_null_count = cur.fetchone()[0]
            cur.execute(
                "SELECT character, pinyin, searchable_pinyin FROM hwxnet_characters WHERE jsonb_array_length(searchable_pinyin) > 2 ORDER BY zibiao_index LIMIT 5"
            )
            multi = cur.fetchall()
        print(f"\nRows with non-null searchable_pinyin: {non_null_count}")
        print("Sample rows with multiple searchable keys (e.g. multiple readings):")
        for r in multi:
            print(f"  {r[0]}  pinyin={r[1]}  searchable_pinyin={r[2]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
