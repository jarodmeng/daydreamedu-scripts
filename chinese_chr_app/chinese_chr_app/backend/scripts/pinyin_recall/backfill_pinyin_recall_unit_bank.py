#!/usr/bin/env python3
"""
Backfill pinyin_recall_unit_bank from legacy pinyin_recall_character_bank.

Migration rule:
- Monophonic characters map to their sole unit.
- Polyphonic characters map to the primary unit only (first reading / is_primary).

Creates backup tables before modifying unless --no-backup is passed.

Run from backend/:
  python3 scripts/pinyin_recall/backfill_pinyin_recall_unit_bank.py
  python3 scripts/pinyin_recall/backfill_pinyin_recall_unit_bank.py --dry-run
  python3 scripts/pinyin_recall/backfill_pinyin_recall_unit_bank.py --no-backup
"""

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
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    backend_dir = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(backend_dir))
    from pinyin_recall import build_reading_units_for_character  # type: ignore

    dry_run = "--dry-run" in sys.argv
    no_backup = "--no-backup" in sys.argv

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    hwxnet_lookup, feng_lookup = _load_lookup_json()

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, character, score, stage, next_due_utc, first_seen_at, last_answered_at,
                       total_correct, total_wrong, total_i_dont_know
                FROM pinyin_recall_character_bank
                ORDER BY user_id, character
                """
            )
            rows = cur.fetchall()

        inserts = []
        skipped = []
        for row in rows:
            character = (row.get("character") or "").strip()
            hwxnet_entry = hwxnet_lookup.get(character)
            if not hwxnet_entry:
                skipped.append((row.get("user_id"), character, "missing_hwxnet"))
                continue
            units = build_reading_units_for_character(character, hwxnet_entry, feng_lookup.get(character))
            primary = next((unit for unit in units if unit.get("is_primary")), None)
            if not primary:
                skipped.append((row.get("user_id"), character, "missing_primary_unit"))
                continue
            inserts.append((
                (row.get("user_id") or "").strip(),
                primary["unit_id"],
                character,
                primary["reading_key"],
                primary["reading_display"],
                int(row.get("score") or 0),
                int(row.get("stage") or 0),
                row.get("next_due_utc"),
                row.get("first_seen_at"),
                row.get("last_answered_at"),
                int(row.get("total_correct") or 0),
                int(row.get("total_wrong") or 0),
                int(row.get("total_i_dont_know") or 0),
            ))

        if dry_run:
            print(f"[dry-run] Would insert/update {len(inserts)} unit_bank rows.")
            print(f"[dry-run] Would skip {len(skipped)} rows.")
            for sample in skipped[:10]:
                print("  skip:", sample)
            return

        with conn.cursor() as cur:
            if not no_backup:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                legacy_backup = f"pinyin_recall_character_bank_backup_{ts}"
                unit_backup = f"pinyin_recall_unit_bank_backup_{ts}"
                cur.execute(f'CREATE TABLE "{legacy_backup}" AS SELECT * FROM pinyin_recall_character_bank')
                cur.execute("SELECT to_regclass('public.pinyin_recall_unit_bank') AS exists_name")
                if cur.fetchone().get("exists_name"):
                    cur.execute(f'CREATE TABLE "{unit_backup}" AS SELECT * FROM pinyin_recall_unit_bank')
                print("Backup tables created:", legacy_backup, unit_backup)

            cur.executemany(
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
                inserts,
            )
        conn.commit()
        print(f"Backfilled pinyin_recall_unit_bank rows: {len(inserts)}")
        if skipped:
            print(f"Skipped rows: {len(skipped)}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
