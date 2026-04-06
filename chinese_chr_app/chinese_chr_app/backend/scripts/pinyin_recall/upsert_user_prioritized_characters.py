#!/usr/bin/env python3
"""
Upsert per-user Pinyin Recall priority targets into user_prioritized_characters.

Usage (run from backend/):
  python3 scripts/pinyin_recall/upsert_user_prioritized_characters.py \
    --user-id <uuid> \
    --json-file /tmp/priorities.json \
    --replace

The input JSON should be a list of objects with:
  - character (required)
  - reading (optional, accented pinyin)
  - priority (optional)
  - label / source / expires_at / active / note (optional)
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv

    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from pinyin_recall import pinyin_to_numbered  # noqa: E402


HWXNET_JSON = ROOT / "data" / "extracted_characters_hwxnet.json"


def _load_hwxnet_lookup() -> Dict[str, Any]:
    return json.loads(HWXNET_JSON.read_text(encoding="utf-8"))


def _build_valid_readings_lookup(hwxnet_lookup: Dict[str, Any]) -> Dict[str, set[str]]:
    valid: Dict[str, set[str]] = {}
    for character, entry in hwxnet_lookup.items():
        if not isinstance(entry, dict):
            continue
        readings = entry.get("拼音") or []
        buckets = set()
        for reading in readings:
            if not isinstance(reading, str):
                continue
            reading_text = reading.strip()
            if not reading_text:
                continue
            buckets.add(reading_text)
            numbered = pinyin_to_numbered(reading_text)
            if numbered:
                buckets.add(numbered)
        if buckets:
            valid[character] = buckets
    return valid


def _normalize_input_rows(
    rows: List[Any],
    *,
    priority_start: int,
    default_label: Optional[str],
    default_source: Optional[str],
    default_expires_at: Optional[str],
    valid_readings_lookup: Dict[str, set[str]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    normalized: List[Dict[str, Any]] = []
    errors: List[str] = []

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {index + 1}: expected object, got {type(row).__name__}")
            continue

        character = str(row.get("character") or "").strip()
        if len(character) != 1:
            errors.append(f"row {index + 1}: character must be length 1, got {character!r}")
            continue

        reading = str(row.get("reading") or "").strip() or None
        if reading:
            valid_readings = valid_readings_lookup.get(character, set())
            numbered = pinyin_to_numbered(reading)
            if reading not in valid_readings and numbered not in valid_readings:
                errors.append(
                    f"row {index + 1}: reading {reading!r} is not valid for character {character!r}"
                )
                continue

        priority_value = row.get("priority")
        if priority_value in (None, ""):
            priority = priority_start + len(normalized)
        else:
            try:
                priority = int(priority_value)
            except (TypeError, ValueError):
                errors.append(f"row {index + 1}: invalid priority {priority_value!r}")
                continue

        normalized.append(
            {
                "character": character,
                "reading": reading,
                "priority": priority,
                "label": str(row.get("label") or default_label or "").strip() or None,
                "source": str(row.get("source") or default_source or "").strip() or None,
                "note": str(row.get("note") or "").strip() or None,
                "active": bool(True if row.get("active") is None else row.get("active")),
                "expires_at": str(row.get("expires_at") or default_expires_at or "").strip() or None,
            }
        )

    return (normalized, errors)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upsert rows into user_prioritized_characters.",
    )
    parser.add_argument("--user-id", required=True, help="Supabase auth user id")
    parser.add_argument("--json-file", required=True, help="Path to input JSON list")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--merge", action="store_true", help="Upsert only listed rows")
    mode.add_argument("--replace", action="store_true", help="Replace all rows for this user")
    parser.add_argument("--label", help="Default label applied when row.label is absent")
    parser.add_argument("--source", help="Default source applied when row.source is absent")
    parser.add_argument("--priority-start", type=int, default=0, help="Default starting priority")
    parser.add_argument("--expires-at", help="Default expires_at applied when row.expires_at is absent")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print summary without writing")
    args = parser.parse_args()

    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    input_rows = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    if not isinstance(input_rows, list):
        print("Input JSON must be a list of row objects.")
        sys.exit(1)

    valid_readings_lookup = _build_valid_readings_lookup(_load_hwxnet_lookup())
    normalized_rows, errors = _normalize_input_rows(
        input_rows,
        priority_start=args.priority_start,
        default_label=args.label,
        default_source=args.source,
        default_expires_at=args.expires_at,
        valid_readings_lookup=valid_readings_lookup,
    )
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    if args.dry_run:
        mode_name = "replace" if args.replace else "merge"
        print(
            json.dumps(
                {
                    "user_id": args.user_id.strip(),
                    "mode": mode_name,
                    "rows": len(normalized_rows),
                    "first_rows": normalized_rows[:5],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url)
    inserted = 0
    updated = 0
    try:
        with conn.cursor() as cur:
            if args.replace:
                cur.execute(
                    "DELETE FROM user_prioritized_characters WHERE user_id = %s",
                    (args.user_id.strip(),),
                )

            for row in normalized_rows:
                cur.execute(
                    """
                    INSERT INTO user_prioritized_characters (
                        user_id,
                        character,
                        reading,
                        priority,
                        label,
                        source,
                        note,
                        active,
                        expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, character, reading) DO UPDATE SET
                        priority = EXCLUDED.priority,
                        label = EXCLUDED.label,
                        source = EXCLUDED.source,
                        note = EXCLUDED.note,
                        active = EXCLUDED.active,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = now()
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (
                        args.user_id.strip(),
                        row["character"],
                        row["reading"],
                        row["priority"],
                        row["label"],
                        row["source"],
                        row["note"],
                        row["active"],
                        row["expires_at"],
                    ),
                )
                result = cur.fetchone()
                inserted_flag = False
                if isinstance(result, dict):
                    inserted_flag = bool(result.get("inserted"))
                elif isinstance(result, tuple):
                    inserted_flag = bool(result[0]) if result else False
                elif result is not None:
                    inserted_flag = bool(result)
                if inserted_flag:
                    inserted += 1
                else:
                    updated += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(
        json.dumps(
            {
                "user_id": args.user_id.strip(),
                "mode": "replace" if args.replace else "merge",
                "rows_written": len(normalized_rows),
                "inserted": inserted,
                "updated": updated,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
