#!/usr/bin/env python3
"""
Process batch_output.jsonl into a clean JSON file.

Extracts the assistant's JSON content from each batch response and outputs
a dict keyed by character (hanzi) for easy lookup and merging.

Usage:
  python3 process_batch_output.py
  python3 process_batch_output.py -i batch_output.jsonl -o pilot_glosses.json
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"
DEFAULT_INPUT = BATCH_ARTIFACTS / "batch_output.jsonl"
DEFAULT_OUTPUT = BATCH_ARTIFACTS / "pilot_glosses.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process batch API output into JSON"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Input JSONL file (from check_batch_status.py)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON file",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    results = {}
    parse_errors = 0

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
        if not custom_id.startswith("char:"):
            continue

        hanzi = custom_id[5:]  # strip "char:"
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
            gloss = json.loads(content)
        except json.JSONDecodeError:
            parse_errors += 1
            continue

        results[hanzi] = gloss

    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(results)} glosses to {args.output}", file=sys.stderr)
    if parse_errors:
        print(f"Parse errors: {parse_errors}", file=sys.stderr)


if __name__ == "__main__":
    main()
