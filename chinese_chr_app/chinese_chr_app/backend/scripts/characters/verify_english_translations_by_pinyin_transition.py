#!/usr/bin/env python3
"""
Verify the HWXNet 英文解释按拼音 transition field invariants.

Checks:
1. Every monophonic row has exactly one bucket.
2. Every polyphonic row's bucket order matches 拼音.
3. Every reading in 拼音 has a corresponding bucket.
4. Every bucket contains only reviewed final gloss strings.
5. Optional live DB check: english_translations_by_pinyin matches the JSON field.
"""

from __future__ import annotations

import argparse
import json
import os
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
REVIEWED_JSON = (
    OUTER_APP_DIR
    / "generate_english_meaning_using_ai"
    / "batch_artifacts"
    / "reading_glosses.reviewed.json"
)


TONE_MARKS = {
    "ā": ("a", "1"),
    "á": ("a", "2"),
    "ǎ": ("a", "3"),
    "à": ("a", "4"),
    "ē": ("e", "1"),
    "é": ("e", "2"),
    "ě": ("e", "3"),
    "è": ("e", "4"),
    "ī": ("i", "1"),
    "í": ("i", "2"),
    "ǐ": ("i", "3"),
    "ì": ("i", "4"),
    "ō": ("o", "1"),
    "ó": ("o", "2"),
    "ǒ": ("o", "3"),
    "ò": ("o", "4"),
    "ū": ("u", "1"),
    "ú": ("u", "2"),
    "ǔ": ("u", "3"),
    "ù": ("u", "4"),
    "ǖ": ("v", "1"),
    "ǘ": ("v", "2"),
    "ǚ": ("v", "3"),
    "ǜ": ("v", "4"),
    "ü": ("v", "5"),
    "ń": ("n", "2"),
    "ň": ("n", "3"),
    "ǹ": ("n", "4"),
    "ḿ": ("m", "2"),
}


def _import_psycopg():
    try:
        import psycopg

        return psycopg
    except ImportError:
        print("psycopg is required for --check-db. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)


def tone_mark_to_numbered(pinyin: str) -> str:
    if not pinyin:
        return ""
    chars = []
    tone = "5"
    for ch in unicodedata.normalize("NFC", pinyin.strip().lower()):
        mapped = TONE_MARKS.get(ch)
        if mapped:
            base, detected_tone = mapped
            chars.append(base)
            if detected_tone != "5":
                tone = detected_tone
        elif ch.isalpha():
            chars.append(ch)
    return "".join(chars) + tone


def dedupe_strings(values: list[Any]) -> list[str]:
    seen = set()
    out: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def expected_reviewed_glosses(reviewed_row: dict[str, Any]) -> list[str]:
    short_glosses = reviewed_row.get("short_glosses")
    if isinstance(short_glosses, list):
        return dedupe_strings(short_glosses)

    english_gloss = reviewed_row.get("english_gloss")
    if isinstance(english_gloss, str):
        return dedupe_strings([part.strip() for part in english_gloss.split(";")])
    return []


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_json(hwxnet_data: dict[str, Any], reviewed_data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for character, entry in hwxnet_data.items():
        if not isinstance(entry, dict):
            continue
        pinyin = dedupe_strings(entry.get("拼音") or [])
        buckets = entry.get("英文解释按拼音")

        if not pinyin:
            if buckets not in (None, []):
                errors.append(f"{character}: no 拼音 but 英文解释按拼音 is not empty")
            continue

        if not isinstance(buckets, list):
            errors.append(f"{character}: 英文解释按拼音 must be a list")
            continue

        if len(buckets) != len(pinyin):
            errors.append(
                f"{character}: bucket count {len(buckets)} does not match 拼音 count {len(pinyin)}"
            )
            continue

        for expected_reading, bucket in zip(pinyin, buckets):
            if not isinstance(bucket, dict):
                errors.append(f"{character}: bucket for {expected_reading} is not an object")
                continue
            if bucket.get("Pinyin") != expected_reading:
                errors.append(
                    f"{character}: bucket order mismatch, expected {expected_reading!r}, got {bucket.get('Pinyin')!r}"
                )
            glosses = bucket.get("Glosses")
            if not isinstance(glosses, list):
                errors.append(f"{character}|{expected_reading}: Glosses must be a list")
                continue
            if dedupe_strings(glosses) != glosses:
                errors.append(f"{character}|{expected_reading}: Glosses are not clean/deduped strings")
                continue

            if len(pinyin) == 1:
                expected = dedupe_strings(entry.get("英文翻译") or [])
                if glosses != expected:
                    errors.append(
                        f"{character}: monophonic bucket {glosses!r} does not match legacy 英文翻译 {expected!r}"
                    )
            else:
                unit_id = f"{character}|{tone_mark_to_numbered(expected_reading)}"
                reviewed_row = reviewed_data.get(unit_id)
                if not isinstance(reviewed_row, dict):
                    errors.append(f"{unit_id}: missing reviewed reading-gloss artifact row")
                    continue
                expected = expected_reviewed_glosses(reviewed_row)
                if glosses != expected:
                    errors.append(
                        f"{unit_id}: bucket glosses {glosses!r} do not match reviewed artifact {expected!r}"
                    )

    return errors


def verify_db(hwxnet_data: dict[str, Any]) -> list[str]:
    pg = _import_psycopg()
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL for --check-db", file=sys.stderr)
        sys.exit(1)

    expected_by_key: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for character, entry in hwxnet_data.items():
        if not isinstance(entry, dict):
            continue
        zibiao_index = entry.get("zibiao_index")
        if not isinstance(zibiao_index, int):
            try:
                zibiao_index = int(zibiao_index)
            except (TypeError, ValueError):
                continue
        expected_by_key[(character, zibiao_index)] = entry.get("英文解释按拼音") or []

    errors: list[str] = []
    conn = pg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT character, zibiao_index, english_translations_by_pinyin
                FROM hwxnet_characters
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    seen_keys = set()
    for character, zibiao_index, english_by_pinyin in rows:
        key = (character, zibiao_index)
        seen_keys.add(key)
        expected = expected_by_key.get(key)
        if expected is None:
            errors.append(f"{character} zibiao={zibiao_index}: row exists in DB but not JSON")
            continue
        actual = english_by_pinyin or []
        if actual != expected:
            errors.append(
                f"{character} zibiao={zibiao_index}: DB english_translations_by_pinyin does not match JSON"
            )

    missing = set(expected_by_key) - seen_keys
    for character, zibiao_index in sorted(missing)[:20]:
        errors.append(f"{character} zibiao={zibiao_index}: row exists in JSON but not DB")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify HWXNet 英文解释按拼音 transition invariants")
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Also verify live hwxnet_characters.english_translations_by_pinyin matches JSON.",
    )
    args = parser.parse_args()

    if not HWXNET_JSON.exists():
        print(f"Missing JSON: {HWXNET_JSON}", file=sys.stderr)
        return 1
    if not REVIEWED_JSON.exists():
        print(f"Missing reviewed artifact: {REVIEWED_JSON}", file=sys.stderr)
        return 1

    hwxnet_data = load_json(HWXNET_JSON)
    reviewed_data = load_json(REVIEWED_JSON)

    errors = verify_json(hwxnet_data, reviewed_data)
    if args.check_db:
        errors.extend(verify_db(hwxnet_data))

    if errors:
        print("Verification failed:")
        for error in errors[:100]:
            print(f"  {error}")
        if len(errors) > 100:
            print(f"  ... and {len(errors) - 100} more")
        return 1

    print("Verified 英文解释按拼音 transition invariants.")
    print("  - monophonic rows have exactly one bucket")
    print("  - polyphonic bucket order matches 拼音")
    print("  - every reading in 拼音 has a bucket")
    print("  - every bucket matches reviewed final gloss strings")
    if args.check_db:
        print("  - DB english_translations_by_pinyin matches JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
