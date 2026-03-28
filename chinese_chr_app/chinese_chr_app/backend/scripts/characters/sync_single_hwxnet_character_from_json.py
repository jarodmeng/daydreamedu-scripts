#!/usr/bin/env python3
"""
Sync one hwxnet_characters row from data/extracted_characters_hwxnet.json.

Creates a backup table before modifying unless --no-backup is passed.

Run from backend/:
  python3 scripts/characters/sync_single_hwxnet_character_from_json.py --character 蟀
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

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:
    print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
HWXNET_JSON = OUTER_APP_DIR / "data" / "extracted_characters_hwxnet.json"

sys.path.insert(0, str(SCRIPT_DIR))
from add_searchable_pinyin_column import compute_searchable_pinyin_for_row
from create_hwxnet_characters_table import row_from_entry


def load_entry(character: str) -> dict:
    if not HWXNET_JSON.exists():
        print(f"Not found: {HWXNET_JSON}")
        sys.exit(1)

    data = json.loads(HWXNET_JSON.read_text(encoding="utf-8"))
    entry = data.get(character)
    if not entry:
        print(f'Character "{character}" not found in {HWXNET_JSON}')
        sys.exit(1)
    return entry


def _has_column(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def main():
    parser = argparse.ArgumentParser(description="Sync one hwxnet_characters row from extracted_characters_hwxnet.json.")
    parser.add_argument("--character", required=True, help="Single Chinese character to sync.")
    parser.add_argument("--dry-run", action="store_true", help="Print the payload without writing to DB.")
    parser.add_argument("--no-backup", action="store_true", help="Do not create a backup table before modifying hwxnet_characters.")
    args = parser.parse_args()

    character = (args.character or "").strip()
    if len(character) != 1:
        print("--character must be exactly one Chinese character.")
        sys.exit(1)

    entry = load_entry(character)
    row = row_from_entry(entry)
    payload = {
        "character": row[0],
        "zibiao_index": row[1],
        "index": row[2],
        "source_url": row[3],
        "classification": entry.get("分类") or [],
        "pinyin": entry.get("拼音") or [],
        "searchable_pinyin": compute_searchable_pinyin_for_row(entry.get("拼音") or []),
        "radical": row[6],
        "strokes": row[7],
        "basic_meanings": entry.get("基本字义解释") or [],
        "english_translations": entry.get("英文翻译") or [],
        "english_translations_by_pinyin": entry.get("英文解释按拼音") or [],
        "common_phrases": entry.get("常用词组") or [],
        "common_phrases_by_pinyin": entry.get("常用词组按拼音") or [],
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.dry_run:
        return

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            if not args.no_backup:
                backup_name = f'hwxnet_characters_backup_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}'
                cur.execute(f'CREATE TABLE "{backup_name}" AS SELECT * FROM hwxnet_characters')
                print(f"Backup table created: {backup_name}")

            has_searchable = _has_column(cur, "hwxnet_characters", "searchable_pinyin")
            update_sql = """
                UPDATE hwxnet_characters
                SET index = %s,
                    source_url = %s,
                    classification = %s,
                    pinyin = %s,
                    radical = %s,
                    strokes = %s,
                    basic_meanings = %s,
                    english_translations = %s,
                    english_translations_by_pinyin = %s,
                    common_phrases = %s,
                    common_phrases_by_pinyin = %s
            """
            params = [
                payload["index"],
                payload["source_url"],
                Jsonb(payload["classification"]),
                Jsonb(payload["pinyin"]),
                payload["radical"],
                payload["strokes"],
                Jsonb(payload["basic_meanings"]),
                Jsonb(payload["english_translations"]),
                Jsonb(payload["english_translations_by_pinyin"]),
                Jsonb(payload["common_phrases"]),
                Jsonb(payload["common_phrases_by_pinyin"]),
            ]
            if has_searchable:
                update_sql += ", searchable_pinyin = %s"
                params.append(Jsonb(payload["searchable_pinyin"]))
            update_sql += """
                WHERE character = %s AND zibiao_index = %s
                RETURNING character, zibiao_index, pinyin, basic_meanings,
                          common_phrases_by_pinyin, english_translations_by_pinyin
            """
            params.extend([payload["character"], payload["zibiao_index"]])
            cur.execute(update_sql, params)
            updated = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    if not updated:
        print(f'No row updated for character="{payload["character"]}" zibiao_index="{payload["zibiao_index"]}".')
        sys.exit(1)

    print("Updated row:")
    print(json.dumps(updated, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
