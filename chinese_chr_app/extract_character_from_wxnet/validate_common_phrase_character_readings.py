#!/usr/bin/env python3
"""
Validate extracted_hwxnet_common_phrase_character_readings.json.

Checks:
- top-level structure
- required fields and basic types
- allowed_readings format and DB consistency
- phrase row structure and reading membership
- reading vs displayed phrase pinyin prefix consistency
- duplicate phrase/reading rows
- unresolved row counts and multi-reading phrase counts
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv

    ENV_FILE = Path(__file__).resolve().parent.parent / "chinese_chr_app" / "backend" / ".env.local"
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
except ImportError:
    pass

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

from extract_character_hwxnet import _normalize_pinyin_list


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DEFAULT_INPUT = BASE_DIR / "data" / "extracted_hwxnet_common_phrase_character_readings.json"

PINYIN_RE = re.compile(
    r"^[a-zāáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü]+[1-5]?$",
    re.IGNORECASE,
)
PINYIN_SEGMENT_RE = re.compile(
    r"[a-zāáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü]+[1-5]?",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def add_info(self, msg: str) -> None:
        self.info.append(msg)


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL is not set.")
    if psycopg is None:
        raise RuntimeError("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    return url


def load_db_pinyin_map() -> Dict[str, List[str]]:
    query = """
    SELECT character, pinyin
    FROM hwxnet_characters
    """
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    return {
        row["character"]: _normalize_pinyin_list(row.get("pinyin") or [])
        for row in rows
        if row.get("character")
    }


def validate_pinyin(pinyin: str) -> Tuple[bool, str]:
    if not isinstance(pinyin, str) or not pinyin.strip():
        return False, "empty or non-string pinyin"
    if not PINYIN_RE.match(pinyin):
        return False, f"invalid pinyin format: {pinyin}"
    return True, ""


def reading_matches_phrase_pinyin(reading: str, phrase_pinyin: str) -> bool:
    compact = phrase_pinyin.replace(" ", "")
    normalized = _normalize_pinyin_list([compact])
    if normalized and normalized[0].startswith(reading):
        return True

    for segment in PINYIN_SEGMENT_RE.findall(phrase_pinyin):
        normalized_segment = _normalize_pinyin_list([segment])
        if normalized_segment and normalized_segment[0].startswith(reading):
            return True

    return False


def validate_row(
    char: str,
    row: Dict[str, Any],
    allowed_readings: List[str],
    result: ValidationResult,
    duplicate_counter: Counter,
) -> None:
    phrase = row.get("phrase")
    reading = row.get("reading")
    phrase_pinyin = row.get("displayed_phrase_pinyin")
    note = row.get("note")

    if not isinstance(phrase, str) or not phrase.strip():
        result.add_error(f"{char}: row missing valid phrase")
        return

    if char not in phrase:
        result.add_warning(f"{char}: phrase does not contain target character: {phrase}")

    if not isinstance(phrase_pinyin, str) or not phrase_pinyin.strip():
        result.add_error(f"{char}: {phrase} missing displayed_phrase_pinyin")
        return

    if reading is None:
        if not isinstance(note, str) or not note.strip():
            result.add_warning(f"{char}: {phrase} unresolved row missing note")
        return

    if reading not in allowed_readings:
        result.add_error(f"{char}: {phrase} reading {reading!r} not in allowed_readings")
        return

    ok, msg = validate_pinyin(reading)
    if not ok:
        result.add_error(f"{char}: {phrase} {msg}")
        return

    compact = phrase_pinyin.replace(" ", "")
    normalized = _normalize_pinyin_list([compact])
    if not normalized:
        result.add_warning(f"{char}: {phrase} phrase pinyin could not be normalized: {phrase_pinyin!r}")
    elif not reading_matches_phrase_pinyin(reading, phrase_pinyin):
        result.add_warning(
            f"{char}: {phrase} reading {reading!r} does not match the displayed pinyin {phrase_pinyin!r}"
        )

    duplicate_counter[(char, phrase, reading)] += 1


def validate_entry(
    key_char: str,
    entry: Dict[str, Any],
    db_pinyin_map: Dict[str, List[str]],
    result: ValidationResult,
    duplicate_counter: Counter,
    multi_reading_tracker: Dict[Tuple[str, str], set],
) -> None:
    if not isinstance(entry, dict):
        result.add_error(f"{key_char}: entry is not an object")
        return

    for field in ("character", "source_url", "allowed_readings", "common_phrase_readings"):
        if field not in entry:
            result.add_error(f"{key_char}: missing field {field!r}")

    if entry.get("character") != key_char:
        result.add_error(f"{key_char}: character field mismatch: {entry.get('character')!r}")

    source_url = entry.get("source_url")
    if not isinstance(source_url, str) or "hwxnet.com/search.do?keyword=" not in source_url:
        result.add_warning(f"{key_char}: unexpected source_url {source_url!r}")

    allowed_readings = entry.get("allowed_readings")
    if not isinstance(allowed_readings, list):
        result.add_error(f"{key_char}: allowed_readings is not a list")
        return

    normalized_allowed = _normalize_pinyin_list(allowed_readings)
    if normalized_allowed != allowed_readings:
        result.add_warning(f"{key_char}: allowed_readings not normalized/deduped")
    if not normalized_allowed:
        result.add_error(f"{key_char}: allowed_readings is empty")
        return

    for pinyin in normalized_allowed:
        ok, msg = validate_pinyin(pinyin)
        if not ok:
            result.add_error(f"{key_char}: allowed_readings {msg}")

    db_readings = db_pinyin_map.get(key_char)
    if db_readings is None:
        result.add_error(f"{key_char}: character missing from hwxnet_characters DB table")
    elif set(normalized_allowed) != set(db_readings):
        result.add_error(
            f"{key_char}: allowed_readings mismatch DB value. artifact={normalized_allowed!r} db={db_readings!r}"
        )

    rows = entry.get("common_phrase_readings")
    if not isinstance(rows, list):
        result.add_error(f"{key_char}: common_phrase_readings is not a list")
        return

    for row in rows:
        if not isinstance(row, dict):
            result.add_error(f"{key_char}: non-object row in common_phrase_readings")
            continue
        validate_row(key_char, row, normalized_allowed, result, duplicate_counter)
        phrase = row.get("phrase")
        reading = row.get("reading")
        if isinstance(phrase, str) and reading:
            multi_reading_tracker[(key_char, phrase)].add(reading)


def validate_file(path: Path) -> ValidationResult:
    result = ValidationResult()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        result.add_error("Top-level JSON is not an object")
        return result

    db_pinyin_map = load_db_pinyin_map()
    duplicate_counter: Counter = Counter()
    multi_reading_tracker: Dict[Tuple[str, str], set] = defaultdict(set)

    total_rows = 0
    resolved_rows = 0
    unresolved_rows = 0
    chars_with_unresolved = set()

    for i, (char, entry) in enumerate(data.items(), start=1):
        validate_entry(char, entry, db_pinyin_map, result, duplicate_counter, multi_reading_tracker)
        rows = entry.get("common_phrase_readings", []) if isinstance(entry, dict) else []
        total_rows += len(rows)
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("reading") is None:
                unresolved_rows += 1
                chars_with_unresolved.add(char)
            else:
                resolved_rows += 1

    duplicate_rows = [
        {"character": char, "phrase": phrase, "reading": reading, "count": count}
        for (char, phrase, reading), count in duplicate_counter.items()
        if count > 1
    ]
    multi_reading_phrases = [
        {"character": char, "phrase": phrase, "readings": sorted(readings)}
        for (char, phrase), readings in multi_reading_tracker.items()
        if len(readings) > 1
    ]
    duplicate_rows.sort(key=lambda x: (x["character"], x["phrase"], x["reading"]))
    multi_reading_phrases.sort(key=lambda x: (x["character"], x["phrase"]))

    result.stats = {
        "characters": len(data),
        "total_rows": total_rows,
        "resolved_rows": resolved_rows,
        "unresolved_rows": unresolved_rows,
        "resolved_pct": round((resolved_rows / total_rows * 100) if total_rows else 0, 2),
        "characters_with_unresolved": len(chars_with_unresolved),
        "duplicate_phrase_reading_rows": len(duplicate_rows),
        "multi_reading_phrases": len(multi_reading_phrases),
        "sample_duplicate_rows": duplicate_rows[:20],
        "sample_multi_reading_phrases": multi_reading_phrases[:20],
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate extracted_hwxnet_common_phrase_character_readings.json",
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to extracted_hwxnet_common_phrase_character_readings.json",
    )
    args = parser.parse_args()

    result = validate_file(Path(args.input))
    print(json.dumps(
        {
            "errors": result.errors,
            "warnings": result.warnings,
            "info": result.info,
            "stats": result.stats,
        },
        ensure_ascii=False,
        indent=2,
    ))

    if result.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
