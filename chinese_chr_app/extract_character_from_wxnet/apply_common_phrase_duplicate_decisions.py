#!/usr/bin/env python3
"""
Apply reviewed duplicate-phrase decisions to the common-phrase reading artifact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DEFAULT_INPUT = BASE_DIR / "data" / "extracted_hwxnet_common_phrase_character_readings.json"
DEFAULT_OUTPUT = BASE_DIR / "data" / "extracted_hwxnet_common_phrase_character_readings.reviewed.json"


def load_decisions(path: Path) -> dict[tuple[str, str], dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    decisions = {}
    for item in payload.get("decisions", []):
        key = (item["character"], item["phrase"])
        decisions[key] = item
    return decisions


def apply_decisions(input_path: Path, decisions_path: Path, output_path: Path) -> None:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    decisions = load_decisions(decisions_path)

    for character, entry in data.items():
        rows = entry.get("common_phrase_readings", [])
        grouped = {}
        for row in rows:
            grouped.setdefault(row.get("phrase"), []).append(row)

        next_rows = []
        for phrase, phrase_rows in grouped.items():
            decision = decisions.get((character, phrase))
            if not decision or decision.get("mode") == "keep_both":
                next_rows.extend(phrase_rows)
                continue
            if decision.get("mode") == "keep_one":
                kept = set(decision.get("kept_readings") or [])
                next_rows.extend([row for row in phrase_rows if row.get("reading") in kept])
                continue
            next_rows.extend(phrase_rows)

        entry["common_phrase_readings"] = next_rows

    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply duplicate common-phrase review decisions.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input extracted artifact path.")
    parser.add_argument("--decisions", required=True, help="Path to exported decisions JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output artifact path.")
    args = parser.parse_args()

    apply_decisions(Path(args.input), Path(args.decisions), Path(args.output))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
