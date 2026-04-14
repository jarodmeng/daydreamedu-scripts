#!/usr/bin/env python3
"""
Generate the current missing reading-level priorities for one user.

Usage (run from backend/):
  python3 scripts/pinyin_recall/generate_missing_user_priorities_from_readings.py \
    --email <user@example.com> \
    --readings-json ../../../ai_study_buddy/docs/notes/p4_4a_dictation_2026_category_ii_readings.json \
    --output-json /tmp/emma_priorities.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from dotenv import load_dotenv

    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from pinyin_recall import pinyin_to_numbered  # noqa: E402


ROOT = Path(__file__).resolve().parents[4]
HWXNET_JSON = ROOT / "data" / "extracted_characters_hwxnet.json"


def get_user_id_by_email(cur, email: str) -> Optional[str]:
    cur.execute(
        "SELECT id FROM auth.users WHERE email = %s LIMIT 1",
        (email.strip(),),
    )
    row = cur.fetchone()
    return str(row["id"]) if row and row.get("id") else None


def _load_hwxnet_lookup() -> Dict[str, Any]:
    return json.loads(HWXNET_JSON.read_text(encoding="utf-8"))


def _build_canonical_readings_lookup(hwxnet_lookup: Dict[str, Any]) -> Dict[str, List[str]]:
    lookup: Dict[str, List[str]] = {}
    for character, entry in hwxnet_lookup.items():
        if not isinstance(entry, dict):
            continue
        readings = [
            str(reading).strip()
            for reading in (entry.get("拼音") or [])
            if isinstance(reading, str) and str(reading).strip()
        ]
        if readings:
            lookup[character] = readings
    return lookup


def _load_source_pairs(path: Path) -> List[Tuple[str, str]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Source readings JSON must be a list.")
    pairs: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"row {index + 1}: expected object")
        character = str(row.get("character") or "").strip()
        reading = str(row.get("reading") or "").strip()
        if len(character) != 1 or not reading:
            raise ValueError(f"row {index + 1}: invalid character/reading {row!r}")
        key = (character, pinyin_to_numbered(reading))
        if not key[1] or key in seen:
            continue
        seen.add(key)
        pairs.append((character, reading))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate current missing user priorities from a readings JSON.")
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--email", help="Supabase auth email")
    identity.add_argument("--user-id", help="Supabase auth user id")
    parser.add_argument("--readings-json", required=True, help="Path to source reading pairs JSON")
    parser.add_argument("--output-json", required=True, help="Where to write the generated priority JSON")
    parser.add_argument("--label", default="听写二", help="Label to attach to generated rows")
    parser.add_argument("--source", default="p4_4a_dictation_2026_category_ii", help="Source tag to attach")
    parser.add_argument("--priority-start", type=int, default=0, help="Starting priority number")
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
    user_id = args.user_id
    try:
        if args.email:
            with conn.cursor() as cur:
                user_id = get_user_id_by_email(cur, args.email)
            if not user_id:
                print(f"No user found for email: {args.email!r}")
                sys.exit(1)

        source_pairs = _load_source_pairs(Path(args.readings_json))
        canonical_readings_lookup = _build_canonical_readings_lookup(_load_hwxnet_lookup())

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT unit_id
                FROM pinyin_recall_unit_bank
                WHERE user_id = %s
                """,
                (user_id.strip(),),
            )
            learned_rows = cur.fetchall()

        learned_unit_ids = {
            str(row.get("unit_id") or "").strip()
            for row in learned_rows
            if str(row.get("unit_id") or "").strip()
        }

        output_rows: List[Dict[str, Any]] = []
        normalized_readings: List[Dict[str, str]] = []
        skipped_unsupported: List[Dict[str, str]] = []
        for offset, (character, reading) in enumerate(source_pairs):
            canonical_reading = reading
            valid_readings = canonical_readings_lookup.get(character, [])
            valid_numbered = {pinyin_to_numbered(value): value for value in valid_readings}
            reading_numbered = pinyin_to_numbered(reading)
            if reading_numbered not in valid_numbered:
                if len(valid_readings) == 1:
                    canonical_reading = valid_readings[0]
                    normalized_readings.append(
                        {
                            "character": character,
                            "from": reading,
                            "to": canonical_reading,
                        }
                    )
                else:
                    skipped_unsupported.append(
                        {
                            "character": character,
                            "reading": reading,
                        }
                    )
                    continue
            else:
                canonical_reading = valid_numbered[reading_numbered]

            unit_id = f"{character}|{pinyin_to_numbered(canonical_reading)}"
            if unit_id in learned_unit_ids:
                continue
            output_rows.append(
                {
                    "character": character,
                    "reading": canonical_reading,
                    "priority": args.priority_start + len(output_rows),
                    "label": args.label,
                    "source": args.source,
                }
            )

        output_path = Path(args.output_json)
        output_path.write_text(json.dumps(output_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "user_id": user_id.strip(),
                    "source_pairs": len(source_pairs),
                    "learned_unit_ids": len(learned_unit_ids),
                    "generated_missing_rows": len(output_rows),
                    "normalized_readings": normalized_readings,
                    "skipped_unsupported": skipped_unsupported,
                    "output_json": str(output_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
