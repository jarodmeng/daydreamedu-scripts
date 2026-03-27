#!/usr/bin/env python3
"""
Build the HWXNet 英文解释按拼音 transition field from the reviewed reading-gloss artifact.

Rules:
- Keep the reviewed reading-gloss artifact as the provenance source for polyphonic rows.
- For monophonic characters, wrap the existing flat 英文翻译 list mechanically.
- Emit one bucket per reading in the character's 拼音 list.
- Bucket order follows the character's 拼音 order in extracted_characters_hwxnet.json.
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
MAIN_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
REVIEWED_JSON = (
    BASE_DIR
    / "generate_english_meaning_using_ai"
    / "batch_artifacts"
    / "reading_glosses.reviewed.json"
)
FIELD_NAME = "英文解释按拼音"


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


def _dedupe_strings(values: List[Any]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


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


def glosses_from_reviewed_row(row: Dict[str, Any]) -> List[str]:
    short_glosses = row.get("short_glosses")
    if isinstance(short_glosses, list):
        glosses = _dedupe_strings(short_glosses)
        if glosses:
            return glosses

    english_gloss = row.get("english_gloss")
    if isinstance(english_gloss, str):
        parts = [part.strip() for part in english_gloss.split(";")]
        glosses = _dedupe_strings(parts)
        if glosses:
            return glosses

    return []


def build_transition_buckets(
    character: str,
    main_entry: Dict[str, Any],
    reviewed_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    pinyin_list = _dedupe_strings(main_entry.get("拼音") or [])
    if not pinyin_list:
        return []

    flat_english = _dedupe_strings(main_entry.get("英文翻译") or [])
    if len(pinyin_list) == 1:
        return [{"Pinyin": pinyin_list[0], "Glosses": flat_english}]

    buckets = []
    for reading in pinyin_list:
        unit_id = f"{character}|{tone_mark_to_numbered(reading)}"
        reviewed_row = reviewed_data.get(unit_id)
        glosses = glosses_from_reviewed_row(reviewed_row) if isinstance(reviewed_row, dict) else []
        buckets.append({"Pinyin": reading, "Glosses": glosses})
    return buckets


def build_transition_map(
    main_data: Dict[str, Any],
    reviewed_data: Dict[str, Any],
) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    transition: Dict[str, List[Dict[str, Any]]] = {}
    monophonic_wrapped = 0
    polyphonic_buckets = 0
    polyphonic_missing_glosses: List[str] = []
    empty_rows = 0

    for character, main_entry in main_data.items():
        if not isinstance(main_entry, dict):
            transition[character] = []
            empty_rows += 1
            continue

        pinyin_list = _dedupe_strings(main_entry.get("拼音") or [])
        buckets = build_transition_buckets(character, main_entry, reviewed_data)
        transition[character] = buckets

        if not pinyin_list:
            empty_rows += 1
            continue
        if len(pinyin_list) == 1:
            monophonic_wrapped += 1
            continue

        polyphonic_buckets += len(buckets)
        for bucket in buckets:
            if not bucket.get("Glosses"):
                polyphonic_missing_glosses.append(f"{character}|{tone_mark_to_numbered(bucket['Pinyin'])}")

    stats = {
        "characters": len(main_data),
        "monophonic_wrapped_characters": monophonic_wrapped,
        "polyphonic_bucket_count": polyphonic_buckets,
        "characters_with_no_pinyin": empty_rows,
        "polyphonic_units_missing_glosses": polyphonic_missing_glosses,
    }
    return transition, stats


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build HWXNet 英文解释按拼音 buckets from the reviewed reading-gloss artifact.",
    )
    parser.add_argument("--main", default=str(MAIN_JSON), help="Path to extracted_characters_hwxnet.json")
    parser.add_argument(
        "--reviewed",
        default=str(REVIEWED_JSON),
        help="Path to reading_glosses.reviewed.json",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output JSON path for the transition map, or '-' to print to stdout.",
    )
    args = parser.parse_args()

    main_data = load_json(Path(args.main))
    reviewed_data = load_json(Path(args.reviewed))
    transition, stats = build_transition_map(main_data, reviewed_data)

    payload = {
        "field_name": FIELD_NAME,
        "stats": stats,
        "characters": transition,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output == "-":
        print(text, end="")
    else:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
