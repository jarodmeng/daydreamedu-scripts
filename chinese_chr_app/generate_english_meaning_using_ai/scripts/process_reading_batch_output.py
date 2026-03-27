#!/usr/bin/env python3
"""
Process reading-level batch_output.jsonl into a clean JSON file keyed by unit_id.

Usage:
  python3 process_reading_batch_output.py
  python3 process_reading_batch_output.py -i ../batch_artifacts/batch_output.jsonl -o ../batch_artifacts/reading_glosses.json
"""

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"
DEFAULT_INPUT = BATCH_ARTIFACTS / "batch_output.jsonl"
DEFAULT_OUTPUT = BATCH_ARTIFACTS / "reading_glosses.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Process reading-level batch output into JSON")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Input JSONL file from check_batch_status.py",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON file keyed by unit_id",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    results = {}
    parse_errors = 0
    skipped = 0

    for line in args.input.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue

        custom_id = row.get("custom_id") or ""
        if not custom_id.startswith("unit:"):
            skipped += 1
            continue

        unit_id = custom_id[5:]
        resp = row.get("response") or {}
        body = resp.get("body") or {}
        choices = body.get("choices") or []
        if not choices:
            parse_errors += 1
            continue

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            parse_errors += 1
            continue

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parse_errors += 1
            continue

        if parsed.get("unit_id") != unit_id:
            parsed["unit_id"] = unit_id
        results[unit_id] = parsed

    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(results)} reading glosses to {args.output}", file=sys.stderr)
    if parse_errors:
        print(f"Parse errors: {parse_errors}", file=sys.stderr)
    if skipped:
        print(f"Skipped non-reading rows: {skipped}", file=sys.stderr)


if __name__ == "__main__":
    main()
