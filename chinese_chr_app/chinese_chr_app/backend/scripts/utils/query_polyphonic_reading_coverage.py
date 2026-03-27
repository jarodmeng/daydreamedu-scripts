#!/usr/bin/env python3
"""
Compute polyphonic reading coverage from local JSON data or the live DB.

Coverage sources:
1. HWXNet basic_meanings 读音 with at least one 例词
2. HWXNet 常用词组按拼音 bucket pinyin with at least one phrase
3. Feng WordsByPinyin bucket pinyin with at least one phrase

Usage (run from backend/):
  python3 scripts/utils/query_polyphonic_reading_coverage.py
  python3 scripts/utils/query_polyphonic_reading_coverage.py --source db
  python3 scripts/utils/query_polyphonic_reading_coverage.py --compare
  python3 scripts/utils/query_polyphonic_reading_coverage.py --limit-uncovered 20
  python3 scripts/utils/query_polyphonic_reading_coverage.py --examples 和 了 哪
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

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
DATA_DIR = OUTER_APP_DIR / "data"
HWXNET_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
FENG_JSON = DATA_DIR / "characters.json"


def normalize_pinyin(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFC", value).strip()


def unique_pinyin_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        pinyin = normalize_pinyin(value)
        if pinyin and pinyin not in seen:
            out.append(pinyin)
            seen.add(pinyin)
    return out


def has_nonempty_strings(values: Any) -> bool:
    if not isinstance(values, list):
        return False
    return any(isinstance(value, str) and value.strip() for value in values)


def unique_bucket_pinyin_with_phrases(buckets: Any) -> list[str]:
    if not isinstance(buckets, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        pinyin = normalize_pinyin(bucket.get("Pinyin"))
        if not has_nonempty_strings(bucket.get("Phrases")):
            continue
        if pinyin and pinyin not in seen:
            out.append(pinyin)
            seen.add(pinyin)
    return out


def unique_basic_meaning_pinyin_with_examples(basic_meanings: Any) -> list[str]:
    if not isinstance(basic_meanings, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for sense in basic_meanings:
        if not isinstance(sense, dict):
            continue
        pinyin = normalize_pinyin(sense.get("读音"))
        definitions = sense.get("释义")
        has_examples = False
        if isinstance(definitions, list):
            for definition in definitions:
                if not isinstance(definition, dict):
                    continue
                if has_nonempty_strings(definition.get("例词")):
                    has_examples = True
                    break
        if pinyin and has_examples and pinyin not in seen:
            out.append(pinyin)
            seen.add(pinyin)
    return out


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_local_data() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    hwxnet_data = load_json(HWXNET_JSON)
    feng_data = load_json(FENG_JSON)
    if not isinstance(hwxnet_data, dict):
        raise SystemExit(f"Unexpected HWXNet JSON shape in {HWXNET_JSON}")
    return hwxnet_data, build_feng_lookup(feng_data)


def load_db_data() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    sys.path.insert(0, str(BACKEND_DIR))
    import database as db  # type: ignore

    try:
        hwxnet_data = db.get_hwxnet_lookup()
        feng_data = db.get_feng_characters()
    except Exception as exc:
        raise SystemExit(
            "Failed to load live DB data. Make sure DATABASE_URL or SUPABASE_DB_URL is set "
            f"and reachable. Original error: {exc}"
        ) from exc
    if not isinstance(hwxnet_data, dict):
        raise SystemExit("Unexpected DB HWXNet data shape from database.get_hwxnet_lookup()")
    return hwxnet_data, build_feng_lookup(feng_data)


def build_feng_lookup(rows: Any) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return lookup
    for row in rows:
        if not isinstance(row, dict):
            continue
        character = (row.get("Character") or "").strip()
        if character and character not in lookup:
            lookup[character] = row
    return lookup


def compute_coverage(hwxnet_data: dict[str, Any], feng_lookup: dict[str, dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    stats = {
        "polyphonic_chars": 0,
        "basic_full": 0,
        "basic_plus_hwxnet_phrases_full": 0,
        "basic_plus_hwxnet_plus_feng_full": 0,
        "has_hwxnet_phrase_buckets": 0,
        "has_feng_buckets": 0,
        "remaining_after_all": 0,
    }
    uncovered_rows: list[dict[str, Any]] = []

    for character, entry in hwxnet_data.items():
        if not isinstance(entry, dict):
            continue

        top_pinyin = unique_pinyin_list(entry.get("拼音") or [])
        if len(top_pinyin) <= 1:
            continue

        stats["polyphonic_chars"] += 1
        top_set = set(top_pinyin)

        basic_pinyin = unique_basic_meaning_pinyin_with_examples(entry.get("基本字义解释") or [])
        basic_set = set(basic_pinyin)

        hwxnet_phrase_pinyin = unique_bucket_pinyin_with_phrases(entry.get("常用词组按拼音") or [])
        hwxnet_phrase_set = set(hwxnet_phrase_pinyin)
        if hwxnet_phrase_pinyin:
            stats["has_hwxnet_phrase_buckets"] += 1

        feng_entry = feng_lookup.get(character) or {}
        feng_pinyin = unique_bucket_pinyin_with_phrases(feng_entry.get("WordsByPinyin") or [])
        feng_set = set(feng_pinyin)
        if feng_pinyin:
            stats["has_feng_buckets"] += 1

        coverage_basic = basic_set
        coverage_basic_hwx = basic_set | hwxnet_phrase_set
        coverage_all = basic_set | hwxnet_phrase_set | feng_set

        if coverage_basic >= top_set:
            stats["basic_full"] += 1
        if coverage_basic_hwx >= top_set:
            stats["basic_plus_hwxnet_phrases_full"] += 1
        if coverage_all >= top_set:
            stats["basic_plus_hwxnet_plus_feng_full"] += 1
        else:
            uncovered_rows.append(
                {
                    "character": character,
                    "top_pinyin": top_pinyin,
                    "basic_meanings_pinyin_with_examples": basic_pinyin,
                    "hwxnet_phrase_bucket_pinyin": hwxnet_phrase_pinyin,
                    "feng_bucket_pinyin": feng_pinyin,
                    "missing_after_all": [p for p in top_pinyin if p not in coverage_all],
                    "zibiao_index": entry.get("zibiao_index"),
                }
            )

    uncovered_rows.sort(
        key=lambda row: (
            10**9 if row.get("zibiao_index") is None else row["zibiao_index"],
            row["character"],
        )
    )
    stats["remaining_after_all"] = len(uncovered_rows)
    return stats, uncovered_rows


def print_summary(stats: dict[str, int], source_label: str) -> None:
    print(f"Polyphonic reading coverage ({source_label})")
    print("======================================")
    print(f"Polyphonic characters: {stats['polyphonic_chars']}")
    print(f"Full coverage by basic_meanings with 例词 only: {stats['basic_full']}")
    print(
        "Full coverage by basic_meanings with 例词 + 常用词组按拼音: "
        f"{stats['basic_plus_hwxnet_phrases_full']}"
    )
    print(
        "Full coverage by basic_meanings with 例词 + 常用词组按拼音 + WordsByPinyin: "
        f"{stats['basic_plus_hwxnet_plus_feng_full']}"
    )
    print(f"Polyphonic chars with any 常用词组按拼音 bucket phrases: {stats['has_hwxnet_phrase_buckets']}")
    print(f"Polyphonic chars with any WordsByPinyin bucket phrases: {stats['has_feng_buckets']}")
    print(f"Still uncovered after all 3 sources: {stats['remaining_after_all']}")


def print_uncovered(rows: list[dict[str, Any]], limit: int) -> None:
    if not rows:
        print("\nNo uncovered rows remain.")
        return
    print("\nUncovered examples")
    print("------------------")
    for row in rows[:limit]:
        print(row["character"])
        print(f"  top pinyin: {row['top_pinyin']}")
        print(f"  basic_meanings with 例词: {row['basic_meanings_pinyin_with_examples']}")
        print(f"  常用词组按拼音: {row['hwxnet_phrase_bucket_pinyin']}")
        print(f"  WordsByPinyin: {row['feng_bucket_pinyin']}")
        print(f"  missing after all: {row['missing_after_all']}")


def print_examples(rows: list[dict[str, Any]], characters: list[str]) -> None:
    row_by_character = {row["character"]: row for row in rows}
    print("\nRequested examples")
    print("------------------")
    for character in characters:
        row = row_by_character.get(character)
        if not row:
            print(f"{character}: fully covered or not polyphonic")
            continue
        print(character)
        print(f"  top pinyin: {row['top_pinyin']}")
        print(f"  basic_meanings with 例词: {row['basic_meanings_pinyin_with_examples']}")
        print(f"  常用词组按拼音: {row['hwxnet_phrase_bucket_pinyin']}")
        print(f"  WordsByPinyin: {row['feng_bucket_pinyin']}")
        print(f"  missing after all: {row['missing_after_all']}")


def compare_results(
    local_stats: dict[str, int],
    local_rows: list[dict[str, Any]],
    db_stats: dict[str, int],
    db_rows: list[dict[str, Any]],
) -> int:
    print("\nCompare local vs live DB")
    print("------------------------")

    differences = 0
    if local_stats == db_stats:
        print("Summary stats: match")
    else:
        print("Summary stats: differ")
        for key in local_stats:
            local_value = local_stats.get(key)
            db_value = db_stats.get(key)
            if local_value != db_value:
                print(f"  {key}: local={local_value} db={db_value}")
                differences += 1

    local_uncovered = {row["character"] for row in local_rows}
    db_uncovered = {row["character"] for row in db_rows}
    if local_uncovered == db_uncovered:
        print(f"Uncovered character set: match ({len(local_uncovered)} chars)")
    else:
        only_local = sorted(local_uncovered - db_uncovered)
        only_db = sorted(db_uncovered - local_uncovered)
        print(
            "Uncovered character set: differ "
            f"(only local={len(only_local)}, only db={len(only_db)})"
        )
        if only_local:
            print(f"  only in local: {only_local[:20]}")
        if only_db:
            print(f"  only in db: {only_db[:20]}")
        differences += 1

    return differences


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute polyphonic reading coverage from local JSON or live DB.",
    )
    parser.add_argument(
        "--source",
        choices=["local", "db"],
        default="local",
        help="Data source to use: local JSON files or live DB tables (default: local).",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run both local JSON and live DB, then compare summary stats and uncovered characters.",
    )
    parser.add_argument(
        "--limit-uncovered",
        type=int,
        default=20,
        help="How many uncovered examples to print (default: 20).",
    )
    parser.add_argument(
        "--examples",
        nargs="*",
        default=[],
        help="Specific characters to show after the summary.",
    )
    args = parser.parse_args()

    if args.compare:
        local_hwxnet, local_feng_lookup = load_local_data()
        local_stats, local_rows = compute_coverage(local_hwxnet, local_feng_lookup)
        print_summary(local_stats, "local JSON")
        print_uncovered(local_rows, max(0, args.limit_uncovered))
        if args.examples:
            print_examples(local_rows, args.examples)

        print()

        db_hwxnet, db_feng_lookup = load_db_data()
        db_stats, db_rows = compute_coverage(db_hwxnet, db_feng_lookup)
        print_summary(db_stats, "live DB")
        print_uncovered(db_rows, max(0, args.limit_uncovered))
        if args.examples:
            print_examples(db_rows, args.examples)

        differences = compare_results(local_stats, local_rows, db_stats, db_rows)
        if differences:
            raise SystemExit(1)
        return

    if args.source == "db":
        hwxnet_data, feng_lookup = load_db_data()
        source_label = "live DB"
    else:
        hwxnet_data, feng_lookup = load_local_data()
        source_label = "local JSON"

    stats, uncovered_rows = compute_coverage(hwxnet_data, feng_lookup)

    print_summary(stats, source_label)
    print_uncovered(uncovered_rows, max(0, args.limit_uncovered))
    if args.examples:
        print_examples(uncovered_rows, args.examples)


if __name__ == "__main__":
    main()
