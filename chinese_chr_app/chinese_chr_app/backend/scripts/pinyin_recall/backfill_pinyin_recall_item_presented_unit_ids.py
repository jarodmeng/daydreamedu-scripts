#!/usr/bin/env python3
"""
Backfill unit-aware columns for legacy pinyin_recall_item_presented rows.

Derivation rule:
- reading_display = correct_choice
- reading_key = numbered(correct_choice)
- unit_id = f"{character}|{reading_key}"

Only updates rows where unit_id IS NULL. Validates the derived unit against the
current reading-unit builder for that character. If the historical target
reading no longer exists in the current builder, fall back to the current
primary reading for that character and rewrite correct_choice accordingly.

Creates a backup table before modifying unless --no-backup is passed.

Run from backend/:
  python3 scripts/pinyin_recall/backfill_pinyin_recall_item_presented_unit_ids.py
  python3 scripts/pinyin_recall/backfill_pinyin_recall_item_presented_unit_ids.py --dry-run
  python3 scripts/pinyin_recall/backfill_pinyin_recall_item_presented_unit_ids.py --no-backup
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
    from pinyin_recall import build_reading_units_for_character, pinyin_to_numbered  # type: ignore

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
                SELECT user_id, session_id, character, correct_choice, created_at
                FROM pinyin_recall_item_presented
                WHERE unit_id IS NULL
                ORDER BY created_at ASC
                """
            )
            rows = cur.fetchall()

        updates = []
        skipped = []
        for row in rows:
            character = (row.get("character") or "").strip()
            correct_choice = (row.get("correct_choice") or "").strip()
            if not character:
                skipped.append((row.get("session_id"), character, "missing_character"))
                continue
            if not correct_choice:
                skipped.append((row.get("session_id"), character, "missing_correct_choice"))
                continue

            hwxnet_entry = hwxnet_lookup.get(character)
            if not hwxnet_entry:
                skipped.append((row.get("session_id"), character, "missing_hwxnet"))
                continue

            reading_key = pinyin_to_numbered(correct_choice)
            unit_id = f"{character}|{reading_key}"
            units = build_reading_units_for_character(character, hwxnet_entry, feng_lookup.get(character))
            matched_unit = next(
                ((unit or {}) for unit in units if (unit.get("unit_id") or "").strip() == unit_id),
                None,
            )
            if matched_unit is None:
                matched_unit = next((unit for unit in units if unit.get("is_primary")), None)
            if matched_unit is None:
                skipped.append((row.get("session_id"), character, f"unit_not_found:{unit_id}"))
                continue

            updates.append((
                matched_unit["unit_id"],
                matched_unit["reading_key"],
                matched_unit["reading_display"],
                matched_unit["reading_display"],
                (row.get("user_id") or "").strip(),
                (row.get("session_id") or "").strip(),
                character,
                row.get("created_at"),
            ))

        if dry_run:
            print(f"[dry-run] Would update {len(updates)} item_presented rows.")
            print(f"[dry-run] Would skip {len(skipped)} rows.")
            for sample in skipped[:20]:
                print("  skip:", sample)
            return

        with conn.cursor() as cur:
            if not no_backup:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                backup = f"pinyin_recall_item_presented_backup_{ts}"
                cur.execute(f'CREATE TABLE "{backup}" AS SELECT * FROM pinyin_recall_item_presented')
                print("Backup table created:", backup)

            cur.executemany(
                """
                UPDATE pinyin_recall_item_presented
                SET unit_id = %s,
                    reading_key = %s,
                    reading_display = %s,
                    correct_choice = %s
                WHERE user_id = %s
                  AND session_id = %s
                  AND character = %s
                  AND created_at = %s
                  AND unit_id IS NULL
                """,
                updates,
            )
        conn.commit()
        print(f"Backfilled item_presented rows: {len(updates)}")
        if skipped:
            print(f"Skipped rows: {len(skipped)}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
