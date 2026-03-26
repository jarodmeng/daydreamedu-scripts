#!/usr/bin/env python3
"""
Query live DB stats for polyphonic characters and show real examples.

Usage (run from backend/):
  python3 scripts/utils/query_polyphonic_character_stats.py
  python3 scripts/utils/query_polyphonic_character_stats.py --examples 和 行 乐 长

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

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


STATS_SQL = """
WITH per_char AS (
    SELECT
        h.character,
        NULLIF(BTRIM(h."index"), '') AS feng_index,
        COALESCE(h.pinyin, '[]'::jsonb) AS pinyin,
        (
            SELECT COUNT(DISTINCT BTRIM(elem))
            FROM jsonb_array_elements_text(COALESCE(h.pinyin, '[]'::jsonb)) AS e(elem)
            WHERE BTRIM(elem) <> ''
        ) AS reading_count,
        (
            SELECT COUNT(DISTINCT BTRIM(sense->>'读音'))
            FROM jsonb_array_elements(COALESCE(h.basic_meanings, '[]'::jsonb)) AS s(sense)
            WHERE BTRIM(sense->>'读音') <> ''
        ) AS sense_reading_count
    FROM hwxnet_characters h
)
SELECT
    COUNT(*) AS total_characters,
    COUNT(*) FILTER (WHERE reading_count > 1) AS polyphonic_characters,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE reading_count > 1) / NULLIF(COUNT(*), 0),
        2
    ) AS polyphonic_pct,
    COUNT(*) FILTER (WHERE reading_count > 1 AND feng_index IS NOT NULL) AS polyphonic_feng_characters,
    SUM(reading_count) FILTER (WHERE reading_count > 1) AS polyphonic_reading_units,
    SUM(reading_count - 1) FILTER (WHERE reading_count > 1) AS extra_reading_units,
    COUNT(*) FILTER (WHERE reading_count > 1 AND sense_reading_count > 1) AS polyphonic_with_multi_reading_senses,
    COUNT(*) FILTER (WHERE reading_count > 1 AND sense_reading_count = 1) AS polyphonic_with_single_reading_sense,
    COUNT(*) FILTER (WHERE reading_count > 1 AND sense_reading_count = 0) AS polyphonic_with_no_reading_sense
FROM per_char
"""


DISTRIBUTION_SQL = """
WITH per_char AS (
    SELECT
        h.character,
        (
            SELECT COUNT(DISTINCT BTRIM(elem))
            FROM jsonb_array_elements_text(COALESCE(h.pinyin, '[]'::jsonb)) AS e(elem)
            WHERE BTRIM(elem) <> ''
        ) AS reading_count
    FROM hwxnet_characters h
)
SELECT reading_count, COUNT(*) AS character_count
FROM per_char
WHERE reading_count > 1
GROUP BY reading_count
ORDER BY reading_count
"""


TOP_POLYPHONIC_SQL = """
WITH per_char AS (
    SELECT
        h.character,
        COALESCE(h.pinyin, '[]'::jsonb) AS pinyin,
        COALESCE(h.pinyin, '[]'::jsonb)::text AS pinyin_text,
        (
            SELECT COUNT(DISTINCT BTRIM(elem))
            FROM jsonb_array_elements_text(COALESCE(h.pinyin, '[]'::jsonb)) AS e(elem)
            WHERE BTRIM(elem) <> ''
        ) AS reading_count
    FROM hwxnet_characters h
)
SELECT character, pinyin, reading_count
FROM per_char
WHERE reading_count > 1
ORDER BY reading_count DESC, character ASC
LIMIT %s
"""


BANK_STATS_SQL = """
WITH per_char AS (
    SELECT
        h.character,
        (
            SELECT COUNT(DISTINCT BTRIM(elem))
            FROM jsonb_array_elements_text(COALESCE(h.pinyin, '[]'::jsonb)) AS e(elem)
            WHERE BTRIM(elem) <> ''
        ) AS reading_count
    FROM hwxnet_characters h
)
SELECT
    COUNT(*) AS bank_rows,
    COUNT(DISTINCT b.user_id) AS users,
    COUNT(DISTINCT b.character) AS distinct_characters,
    SUM(p.reading_count) AS expanded_rows_if_split,
    SUM(p.reading_count - 1) AS extra_rows_if_split
FROM pinyin_recall_character_bank b
JOIN per_char p
  ON p.character = b.character
WHERE p.reading_count > 1
"""


ANSWER_STATS_SQL = """
WITH per_char AS (
    SELECT
        h.character,
        (
            SELECT COUNT(DISTINCT BTRIM(elem))
            FROM jsonb_array_elements_text(COALESCE(h.pinyin, '[]'::jsonb)) AS e(elem)
            WHERE BTRIM(elem) <> ''
        ) AS reading_count
    FROM hwxnet_characters h
)
SELECT
    COUNT(*) AS answer_rows,
    COUNT(DISTINCT a.user_id) AS users,
    COUNT(DISTINCT a.character) AS distinct_characters
FROM pinyin_recall_item_answered a
JOIN per_char p
  ON p.character = a.character
WHERE p.reading_count > 1
"""


TOP_ANSWERED_POLYPHONIC_SQL = """
WITH per_char AS (
    SELECT
        h.character,
        COALESCE(h.pinyin, '[]'::jsonb)::text AS pinyin_text,
        (
            SELECT COUNT(DISTINCT BTRIM(elem))
            FROM jsonb_array_elements_text(COALESCE(h.pinyin, '[]'::jsonb)) AS e(elem)
            WHERE BTRIM(elem) <> ''
        ) AS reading_count
    FROM hwxnet_characters h
)
SELECT
    a.character,
    COUNT(*) AS answer_rows,
    COUNT(DISTINCT a.user_id) AS users,
    MAX(p.reading_count) AS reading_count,
    MIN(p.pinyin_text) AS pinyin
FROM pinyin_recall_item_answered a
JOIN per_char p
  ON p.character = a.character
WHERE p.reading_count > 1
GROUP BY a.character
ORDER BY answer_rows DESC, a.character ASC
LIMIT %s
"""


def _format_list(values: List[str]) -> str:
    return ", ".join(v for v in values if v) if values else "(none)"


def _load_backend_modules():
    backend_dir = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(backend_dir))
    import database as db  # type: ignore
    from pinyin_recall import get_correct_pinyin, get_stem_words  # type: ignore

    return db, get_correct_pinyin, get_stem_words


def _example_payload(
    character: str,
    hwxnet_lookup: Dict[str, Dict[str, Any]],
    feng_lookup: Dict[str, Dict[str, Any]],
    get_correct_pinyin,
    get_stem_words,
) -> Dict[str, Any]:
    entry = hwxnet_lookup.get(character)
    if not entry:
        return {"character": character, "missing": True}

    all_pinyin = [p.strip() for p in (entry.get("拼音") or []) if isinstance(p, str) and p.strip()]
    generic_stems = get_stem_words(character, feng_lookup, hwxnet_lookup, max_words=5)

    by_reading: List[Dict[str, Any]] = []
    for sense in entry.get("基本字义解释") or []:
        reading = (sense.get("读音") or "").strip()
        if not reading:
            continue
        examples: List[str] = []
        meanings: List[str] = []
        for definition in sense.get("释义") or []:
            explanation = (definition.get("解释") or "").strip()
            if explanation and explanation not in meanings:
                meanings.append(explanation)
            for ex in definition.get("例词") or []:
                if isinstance(ex, str):
                    ex_str = ex.strip()
                    if ex_str and ex_str not in examples:
                        examples.append(ex_str)
        existing = next((row for row in by_reading if row["reading"] == reading), None)
        if existing is None:
            by_reading.append(
                {
                    "reading": reading,
                    "meanings": meanings[:2],
                    "examples": examples[:5],
                }
            )
        else:
            for meaning in meanings:
                if meaning not in existing["meanings"]:
                    existing["meanings"].append(meaning)
            for example in examples:
                if example not in existing["examples"]:
                    existing["examples"].append(example)
            existing["meanings"] = existing["meanings"][:2]
            existing["examples"] = existing["examples"][:5]

    return {
        "character": character,
        "missing": False,
        "all_pinyin": all_pinyin,
        "current_correct_choice": get_correct_pinyin(entry),
        "generic_stems": generic_stems,
        "by_reading": by_reading,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Query live DB stats for polyphonic characters and show real examples.",
    )
    parser.add_argument(
        "--examples",
        nargs="+",
        default=["和", "行", "乐", "长", "觉", "得"],
        help="Characters to inspect in detail (default: 和 行 乐 长 觉 得)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="How many top rows to show in summary tables (default: 15)",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(STATS_SQL)
            stats = cur.fetchone()

            cur.execute(DISTRIBUTION_SQL)
            distribution = cur.fetchall()

            cur.execute(TOP_POLYPHONIC_SQL, (args.top,))
            top_polyphonic = cur.fetchall()

            cur.execute(BANK_STATS_SQL)
            bank_stats = cur.fetchone()

            cur.execute(ANSWER_STATS_SQL)
            answer_stats = cur.fetchone()

            cur.execute(TOP_ANSWERED_POLYPHONIC_SQL, (args.top,))
            top_answered = cur.fetchall()
    finally:
        conn.close()

    db, get_correct_pinyin, get_stem_words = _load_backend_modules()
    hwxnet_lookup = db.get_hwxnet_lookup()
    feng_rows = db.get_feng_characters()
    feng_lookup = {
        row["Character"]: row
        for row in feng_rows
        if row.get("Character")
    }

    print("Polyphonic character stats")
    print("==========================")
    print(f"Total HWXNet characters: {stats['total_characters']}")
    print(
        "Polyphonic characters (>1 distinct pinyin): "
        f"{stats['polyphonic_characters']} ({stats['polyphonic_pct']}%)"
    )
    print(f"Polyphonic characters also in Feng set: {stats['polyphonic_feng_characters']}")
    print(f"Reading-level units for those polyphonic chars: {stats['polyphonic_reading_units']}")
    print(f"Extra learning units vs current character-only model: {stats['extra_reading_units']}")
    print(
        "Polyphonic chars with >1 reading explicitly represented in basic_meanings: "
        f"{stats['polyphonic_with_multi_reading_senses']}"
    )
    print(
        "Polyphonic chars with only 1 reading tagged in basic_meanings: "
        f"{stats['polyphonic_with_single_reading_sense']}"
    )
    print(
        "Polyphonic chars with no reading-tagged senses in basic_meanings: "
        f"{stats['polyphonic_with_no_reading_sense']}"
    )
    print()

    print("Distribution by number of readings")
    print("----------------------------------")
    for row in distribution:
        print(f"{row['reading_count']} readings: {row['character_count']} characters")
    print()

    print("Most polyphonic characters in the pool")
    print("--------------------------------------")
    for row in top_polyphonic:
        print(
            f"{row['character']}  readings={row['reading_count']}  pinyin={row['pinyin']}"
        )
    print()

    print("Current pinyin_recall_character_bank impact")
    print("-------------------------------------------")
    print(f"Bank rows on polyphonic characters: {bank_stats['bank_rows']}")
    print(f"Users with polyphonic-character progress: {bank_stats['users']}")
    print(f"Distinct polyphonic characters seen in bank: {bank_stats['distinct_characters']}")
    print(f"Expanded bank rows if split by reading: {bank_stats['expanded_rows_if_split']}")
    print(f"Extra bank rows if split by reading: {bank_stats['extra_rows_if_split']}")
    print()

    print("Current pinyin_recall_item_answered impact")
    print("------------------------------------------")
    print(f"Answer rows on polyphonic characters: {answer_stats['answer_rows']}")
    print(f"Users with such answers: {answer_stats['users']}")
    print(f"Distinct polyphonic characters answered: {answer_stats['distinct_characters']}")
    print()

    print("Most answered polyphonic characters")
    print("-----------------------------------")
    for row in top_answered:
        print(
            f"{row['character']}  answers={row['answer_rows']}  users={row['users']}  "
            f"readings={row['reading_count']}  pinyin={row['pinyin']}"
        )
    print()

    print("Detailed examples")
    print("-----------------")
    for character in args.examples:
        payload = _example_payload(
            character,
            hwxnet_lookup,
            feng_lookup,
            get_correct_pinyin,
            get_stem_words,
        )
        if payload["missing"]:
            print(f"{character}: no HWXNet entry found")
            print()
            continue
        print(f"{payload['character']}")
        print(f"  all pinyin: {_format_list(payload['all_pinyin'])}")
        print(f"  current correct choice: {payload['current_correct_choice'] or '(none)'}")
        print(f"  current generic stems: {_format_list(payload['generic_stems'])}")
        if not payload["by_reading"]:
            print("  reading-specific senses: (none)")
        for row in payload["by_reading"]:
            print(f"  proposed unit {payload['character']}|{row['reading']}")
            print(f"    meanings: {_format_list(row['meanings'])}")
            print(f"    examples: {_format_list(row['examples'])}")
        print()


if __name__ == "__main__":
    main()
