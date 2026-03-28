#!/usr/bin/env python3
"""
Backfill one pinyin_recall_unit_bank row from legacy pinyin_recall_character_bank.

Creates backup tables before modifying unless --no-backup is passed.

Run from backend/:
  python3 scripts/pinyin_recall/backfill_single_pinyin_recall_unit_bank_row.py --user-id <uuid> --character 蟀
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv

    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


def _load_lookup_json() -> tuple[dict, dict]:
    root = Path(__file__).resolve().parents[4]
    hwxnet_path = root / "data" / "extracted_characters_hwxnet.json"
    feng_path = root / "data" / "characters.json"
    hwxnet = json.loads(hwxnet_path.read_text(encoding="utf-8"))
    feng_rows = json.loads(feng_path.read_text(encoding="utf-8"))
    feng_lookup = {
        (row.get("Character") or "").strip(): row
        for row in feng_rows
        if (row.get("Character") or "").strip()
    }
    return hwxnet, feng_lookup


def main():
    parser = argparse.ArgumentParser(description="Backfill one pinyin_recall_unit_bank row from legacy character bank.")
    parser.add_argument("--user-id", required=True, help="User ID from pinyin_recall_character_bank.")
    parser.add_argument("--character", required=True, help="Single Chinese character from legacy bank.")
    parser.add_argument("--dry-run", action="store_true", help="Print the derived insert payload without writing to DB.")
    parser.add_argument("--no-backup", action="store_true", help="Do not create backup tables before modifying bank tables.")
    args = parser.parse_args()

    user_id = (args.user_id or "").strip()
    character = (args.character or "").strip()
    if not user_id:
        print("--user-id is required.")
        sys.exit(1)
    if len(character) != 1:
        print("--character must be exactly one Chinese character.")
        sys.exit(1)

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    backend_dir = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(backend_dir))
    from pinyin_recall import build_reading_units_for_character  # type: ignore

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    hwxnet_lookup, feng_lookup = _load_lookup_json()
    hwxnet_entry = hwxnet_lookup.get(character)
    if not hwxnet_entry:
        print(f"No HWXNet JSON entry found for {character}.")
        sys.exit(1)

    units = build_reading_units_for_character(character, hwxnet_entry, feng_lookup.get(character))
    primary = next((unit for unit in units if unit.get("is_primary")), None)
    if not primary:
        print(f"No primary reading unit could be derived for {character}.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, character, score, stage, next_due_utc, first_seen_at, last_answered_at,
                       total_correct, total_wrong, total_i_dont_know
                FROM pinyin_recall_character_bank
                WHERE user_id = %s AND character = %s
                """,
                (user_id, character),
            )
            legacy = cur.fetchone()

            if not legacy:
                print(f"No legacy character-bank row found for user_id={user_id} character={character}.")
                sys.exit(1)

            insert_payload = {
                "user_id": user_id,
                "unit_id": primary["unit_id"],
                "character": character,
                "reading_key": primary["reading_key"],
                "reading_display": primary["reading_display"],
                "score": int(legacy.get("score") or 0),
                "stage": int(legacy.get("stage") or 0),
                "next_due_utc": legacy.get("next_due_utc"),
                "first_seen_at": legacy.get("first_seen_at"),
                "last_answered_at": legacy.get("last_answered_at"),
                "total_correct": int(legacy.get("total_correct") or 0),
                "total_wrong": int(legacy.get("total_wrong") or 0),
                "total_i_dont_know": int(legacy.get("total_i_dont_know") or 0),
            }

            print(json.dumps(insert_payload, ensure_ascii=False, indent=2, default=str))
            if args.dry_run:
                return

            if not args.no_backup:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                legacy_backup = f"pinyin_recall_character_bank_backup_{ts}"
                unit_backup = f"pinyin_recall_unit_bank_backup_{ts}"
                cur.execute(f'CREATE TABLE "{legacy_backup}" AS SELECT * FROM pinyin_recall_character_bank')
                cur.execute(f'CREATE TABLE "{unit_backup}" AS SELECT * FROM pinyin_recall_unit_bank')
                print("Backup tables created:", legacy_backup, unit_backup)

            cur.execute(
                """
                INSERT INTO pinyin_recall_unit_bank (
                    user_id, unit_id, character, reading_key, reading_display,
                    score, stage, next_due_utc, first_seen_at, last_answered_at,
                    total_correct, total_wrong, total_i_dont_know
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, unit_id) DO UPDATE SET
                    character = EXCLUDED.character,
                    reading_key = EXCLUDED.reading_key,
                    reading_display = EXCLUDED.reading_display,
                    score = EXCLUDED.score,
                    stage = EXCLUDED.stage,
                    next_due_utc = EXCLUDED.next_due_utc,
                    first_seen_at = EXCLUDED.first_seen_at,
                    last_answered_at = EXCLUDED.last_answered_at,
                    total_correct = EXCLUDED.total_correct,
                    total_wrong = EXCLUDED.total_wrong,
                    total_i_dont_know = EXCLUDED.total_i_dont_know
                """,
                (
                    insert_payload["user_id"],
                    insert_payload["unit_id"],
                    insert_payload["character"],
                    insert_payload["reading_key"],
                    insert_payload["reading_display"],
                    insert_payload["score"],
                    insert_payload["stage"],
                    insert_payload["next_due_utc"],
                    insert_payload["first_seen_at"],
                    insert_payload["last_answered_at"],
                    insert_payload["total_correct"],
                    insert_payload["total_wrong"],
                    insert_payload["total_i_dont_know"],
                ),
            )
        conn.commit()
    finally:
        conn.close()

    print(f"Backfilled pinyin_recall_unit_bank for user_id={user_id} character={character} -> {primary['unit_id']}")


if __name__ == "__main__":
    main()
