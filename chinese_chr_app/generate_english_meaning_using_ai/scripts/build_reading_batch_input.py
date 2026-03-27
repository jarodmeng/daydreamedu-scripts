#!/usr/bin/env python3
"""
Build JSONL input for OpenAI Batch API from the reading-level evidence artifact.

This prepares the batch input only. It does not submit the batch.

Usage:
  python3 build_reading_batch_input.py
  python3 build_reading_batch_input.py --pilot 25 -o ../batch_artifacts/reading_batch_pilot.jsonl
  python3 build_reading_batch_input.py --units "累|lei4,参|shen1"
"""

import argparse
import json
import random
import sys
from pathlib import Path

from run_single_reading_gloss_prompt import extract_system_message


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"
DEFAULT_PROMPT_MD = ROOT / "prompts" / "reading_level_english_gloss_generation_prompt.md"
DEFAULT_ARTIFACT_JSON = BATCH_ARTIFACTS / "reading_units_polyphonic.json"
DEFAULT_OUTPUT = BATCH_ARTIFACTS / "reading_batch_input.jsonl"


def build_batch_request_line(
    row: dict,
    system_content: str,
    *,
    model: str,
    max_tokens: int,
) -> dict:
    return {
        "custom_id": f"unit:{row['unit_id']}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": json.dumps(row, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Batch API JSONL from reading-unit artifact")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSONL file",
    )
    parser.add_argument(
        "--artifact-json",
        type=Path,
        default=DEFAULT_ARTIFACT_JSON,
        help="Reading-unit artifact JSON",
    )
    parser.add_argument(
        "--prompt-md",
        type=Path,
        default=DEFAULT_PROMPT_MD,
        help="Reading-level prompt markdown",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model for batch",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256,
        help="Max tokens per response",
    )
    parser.add_argument(
        "--pilot",
        type=int,
        default=None,
        help="Randomly sample N reading units",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for --pilot",
    )
    parser.add_argument(
        "--units",
        type=str,
        default=None,
        help="Comma-separated unit_ids, e.g. '累|lei4,参|shen1'",
    )
    args = parser.parse_args()

    if not args.artifact_json.exists():
        print(
            f"Error: reading-unit artifact not found: {args.artifact_json}\n"
            "Run build_reading_unit_artifact.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    rows = json.loads(args.artifact_json.read_text(encoding="utf-8"))
    system_content = extract_system_message(args.prompt_md)

    if args.units:
        wanted = {u.strip() for u in args.units.split(",") if u.strip()}
        rows = [row for row in rows if row.get("unit_id") in wanted]
        print(f"Filtered to {len(rows)} requested unit(s)", file=sys.stderr)
    elif args.pilot is not None:
        rng = random.Random(args.seed)
        rows = list(rows)
        rng.shuffle(rows)
        rows = rows[: args.pilot]
        print(f"Pilot sample: {len(rows)} unit(s)", file=sys.stderr)
    else:
        print(f"Full batch prep: {len(rows)} unit(s)", file=sys.stderr)

    lines = [
        json.dumps(
            build_batch_request_line(
                row,
                system_content,
                model=args.model,
                max_tokens=args.max_tokens,
            ),
            ensure_ascii=False,
        )
        for row in rows
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} requests to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
