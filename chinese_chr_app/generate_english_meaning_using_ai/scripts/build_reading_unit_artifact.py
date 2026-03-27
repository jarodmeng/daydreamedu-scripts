#!/usr/bin/env python3
"""
Build a reading-level evidence artifact for polyphonic characters.

This prepares one JSON record per character+reading unit with all evidence needed
for reading-level English gloss generation, but does not call the OpenAI API.

Usage:
  python3 build_reading_unit_artifact.py
  python3 build_reading_unit_artifact.py --chars "累,参,叉"
  python3 build_reading_unit_artifact.py -o ../batch_artifacts/reading_units_pilot.json
"""

import argparse
import json
import sys
from pathlib import Path

from run_single_reading_gloss_prompt import (
    DEFAULT_CEDICT_FILE,
    DEFAULT_FENG_JSON,
    DEFAULT_HWXNET_JSON,
    build_user_payload,
    load_cedict_lookup,
    load_feng_lookup,
    load_hwxnet,
)


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"
DEFAULT_OUTPUT = BATCH_ARTIFACTS / "reading_units_polyphonic.json"


def unique_readings(entry: dict) -> list[str]:
    readings = []
    seen = set()
    for item in (entry.get("拼音") or []):
        if not isinstance(item, str):
            continue
        value = item.strip()
        if value and value not in seen:
            seen.add(value)
            readings.append(value)
    return readings


def has_sample_words(row: dict) -> bool:
    return any(
        row.get(field)
        for field in (
            "reading_feng_words_by_pinyin",
            "reading_common_phrases_by_pinyin",
            "reading_example_phrases",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reading-level evidence artifact for polyphonic units")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON file",
    )
    parser.add_argument(
        "--hwxnet-json",
        type=Path,
        default=DEFAULT_HWXNET_JSON,
        help="HWXNet data JSON",
    )
    parser.add_argument(
        "--feng-json",
        type=Path,
        default=DEFAULT_FENG_JSON,
        help="Feng data JSON",
    )
    parser.add_argument(
        "--cedict-json",
        type=Path,
        default=DEFAULT_CEDICT_FILE,
        help="CC-CEDICT source (.txt/.txt.gz or local JSON fixture)",
    )
    parser.add_argument(
        "--chars",
        type=str,
        default=None,
        help="Optional comma-separated character list to limit output",
    )
    parser.add_argument(
        "--require-sample-words",
        action="store_true",
        help="Only include units with sample words from WordsByPinyin, 常用词组按拼音, or basic_meanings 例词",
    )
    args = parser.parse_args()

    hwxnet = load_hwxnet(args.hwxnet_json)
    feng_lookup = load_feng_lookup(args.feng_json)
    cedict_lookup = load_cedict_lookup(args.cedict_json)

    selected_chars = None
    if args.chars:
        selected_chars = {c.strip() for c in args.chars.split(",") if c.strip()}

    rows = []
    for hanzi, entry in hwxnet.items():
        if selected_chars is not None and hanzi not in selected_chars:
            continue
        readings = unique_readings(entry)
        if len(readings) <= 1:
            continue
        for reading in readings:
            row = build_user_payload(
                hanzi,
                reading,
                entry,
                feng_lookup.get(hanzi),
                cedict_lookup,
            )
            if args.require_sample_words and not has_sample_words(row):
                continue
            rows.append(row)

    rows.sort(key=lambda row: (row["hanzi"], row["reading"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} reading units to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
