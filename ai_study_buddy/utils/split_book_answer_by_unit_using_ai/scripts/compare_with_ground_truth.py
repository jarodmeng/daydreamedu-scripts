#!/usr/bin/env python3
"""
Compare a processed batch result against a ground-truth mapping file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DEFAULT_PROCESSED = ROOT / "batch_artifacts" / "processed_output.json"
DEFAULT_GROUND_TRUTH = ROOT / "pilot_ground_truth" / "science_practice_primary_5_and_6_ground_truth.json"


def index_mappings(items: list[dict]) -> dict[int, dict]:
    return {int(item["unit_index"]): item for item in items}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare model output with pilot ground truth")
    parser.add_argument("--processed", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--custom-id", default="book:science_practice_primary_5_and_6")
    args = parser.parse_args()

    processed = json.loads(args.processed.read_text(encoding="utf-8"))
    truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))

    result = (processed.get("results") or {}).get(args.custom_id)
    if not result:
        print(f"Error: No processed result found for {args.custom_id}", file=sys.stderr)
        sys.exit(1)

    pred_map = index_mappings(result.get("mappings") or [])
    truth_map = index_mappings(truth.get("mappings") or [])

    exact_matches = 0
    range_matches = 0
    mismatches = []

    for unit_index in sorted(truth_map):
        truth_item = truth_map[unit_index]
        pred_item = pred_map.get(unit_index)
        if not pred_item:
            mismatches.append({"unit_index": unit_index, "error": "missing_in_prediction"})
            continue

        same_range = (
            pred_item.get("answer_page_start") == truth_item.get("answer_page_start")
            and pred_item.get("answer_page_end") == truth_item.get("answer_page_end")
        )
        same_split_flags = (
            bool(pred_item.get("starts_mid_page")) == bool(truth_item.get("starts_mid_page"))
            and bool(pred_item.get("ends_mid_page")) == bool(truth_item.get("ends_mid_page"))
        )

        if same_range:
            range_matches += 1
        if same_range and same_split_flags:
            exact_matches += 1
        else:
            mismatches.append(
                {
                    "unit_index": unit_index,
                    "unit_file": truth_item.get("unit_file"),
                    "expected": {
                        "answer_page_start": truth_item.get("answer_page_start"),
                        "answer_page_end": truth_item.get("answer_page_end"),
                        "starts_mid_page": truth_item.get("starts_mid_page"),
                        "ends_mid_page": truth_item.get("ends_mid_page"),
                    },
                    "predicted": {
                        "answer_page_start": pred_item.get("answer_page_start"),
                        "answer_page_end": pred_item.get("answer_page_end"),
                        "starts_mid_page": pred_item.get("starts_mid_page"),
                        "ends_mid_page": pred_item.get("ends_mid_page"),
                    },
                }
            )

    summary = {
        "custom_id": args.custom_id,
        "truth_unit_count": len(truth_map),
        "predicted_unit_count": len(pred_map),
        "range_matches": range_matches,
        "exact_matches": exact_matches,
        "mismatches": mismatches,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

