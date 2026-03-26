#!/usr/bin/env python3
"""
Build the HWXNet 常用词组按拼音 transition field from the reviewed phrase-reading artifact.

Rules:
- Keep the reviewed artifact as the provenance source for polyphonic phrase/readings.
- For monophonic characters, wrap the existing flat 常用词组 list mechanically.
- For polyphonic characters missing reviewed data, emit an empty list rather than guessing.
- Bucket order follows the character's 拼音 order in extracted_characters_hwxnet.json.
- Phrases may appear in multiple buckets when genuinely polyphonic (for example 琢磨).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"
MAIN_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
REVIEWED_JSON = DATA_DIR / "extracted_hwxnet_common_phrase_character_readings.reviewed.json"
FIELD_NAME = "常用词组按拼音"


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


def build_transition_buckets(
    character: str,
    main_entry: Dict[str, Any],
    reviewed_entry: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    pinyin_list = _dedupe_strings(main_entry.get("拼音") or [])
    flat_phrases = _dedupe_strings(main_entry.get("常用词组") or [])

    if not pinyin_list or not flat_phrases:
        return []

    if reviewed_entry is None:
        if len(pinyin_list) == 1:
            return [{"Pinyin": pinyin_list[0], "Phrases": flat_phrases}]
        return []

    grouped: Dict[str, List[str]] = {pinyin: [] for pinyin in pinyin_list}
    seen_per_bucket: Dict[str, set[str]] = {pinyin: set() for pinyin in pinyin_list}
    rows = reviewed_entry.get("common_phrase_readings") or []

    for row in rows:
        if not isinstance(row, dict):
            continue
        reading = row.get("reading")
        phrase = row.get("phrase")
        if not isinstance(reading, str) or not isinstance(phrase, str):
            continue
        reading = reading.strip()
        phrase = phrase.strip()
        if not reading or not phrase:
            continue
        if reading not in grouped:
            raise ValueError(
                f"{character}: reviewed reading {reading!r} not present in main 拼音 {pinyin_list!r}"
            )
        if phrase in seen_per_bucket[reading]:
            continue
        seen_per_bucket[reading].add(phrase)
        grouped[reading].append(phrase)

    return [
        {"Pinyin": pinyin, "Phrases": phrases}
        for pinyin, phrases in ((p, grouped[p]) for p in pinyin_list)
        if phrases
    ]


def build_transition_map(
    main_data: Dict[str, Any],
    reviewed_data: Dict[str, Any],
) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    transition: Dict[str, List[Dict[str, Any]]] = {}
    monophonic_wrapped = 0
    reviewed_polyphonic = 0
    polyphonic_missing_review: List[str] = []
    empty_chars = 0

    for character, main_entry in main_data.items():
        if not isinstance(main_entry, dict):
            transition[character] = []
            empty_chars += 1
            continue

        pinyin_list = _dedupe_strings(main_entry.get("拼音") or [])
        flat_phrases = _dedupe_strings(main_entry.get("常用词组") or [])
        reviewed_entry = reviewed_data.get(character)
        buckets = build_transition_buckets(character, main_entry, reviewed_entry)
        transition[character] = buckets

        if not flat_phrases:
            empty_chars += 1
        elif reviewed_entry is not None:
            reviewed_polyphonic += 1
        elif len(pinyin_list) == 1:
            monophonic_wrapped += 1
        else:
            polyphonic_missing_review.append(character)

    stats = {
        "characters": len(main_data),
        "reviewed_polyphonic_characters": reviewed_polyphonic,
        "monophonic_wrapped_characters": monophonic_wrapped,
        "characters_with_no_common_phrases": empty_chars,
        "polyphonic_characters_missing_review": polyphonic_missing_review,
    }
    return transition, stats


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build HWXNet 常用词组按拼音 buckets from the reviewed phrase-reading artifact.",
    )
    parser.add_argument("--main", default=str(MAIN_JSON), help="Path to extracted_characters_hwxnet.json")
    parser.add_argument(
        "--reviewed",
        default=str(REVIEWED_JSON),
        help="Path to extracted_hwxnet_common_phrase_character_readings.reviewed.json",
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
