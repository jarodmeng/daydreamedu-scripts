#!/usr/bin/env python3
"""
Estimate total cost for running gloss generation on all 3,664 characters.

Uses actual token usage from batch_output.jsonl (pilot) to extrapolate.
Batch API pricing for gpt-4o-mini: $0.075/1M input, $0.30/1M output (as of 2025).
See https://platform.openai.com/docs/pricing for current rates.

Usage:
  python3 estimate_batch_cost.py
  python3 estimate_batch_cost.py -i batch_output.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"
DEFAULT_BATCH_OUTPUT = BATCH_ARTIFACTS / "batch_output.jsonl"
TOTAL_CHARACTERS = 3664

# Batch API pricing for gpt-4o-mini (per 1M tokens) - check pricing page for updates
BATCH_INPUT_RATE = 0.075   # $/1M input tokens
BATCH_OUTPUT_RATE = 0.30   # $/1M output tokens


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate batch cost from pilot token usage"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_BATCH_OUTPUT,
        help="Batch output JSONL (from pilot run)",
    )
    parser.add_argument(
        "--total-chars",
        type=int,
        default=TOTAL_CHARACTERS,
        help=f"Total characters to process (default: {TOTAL_CHARACTERS})",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        print("Run a pilot batch first and use check_batch_status.py to download results.", file=sys.stderr)
        sys.exit(1)

    total_prompt = 0
    total_completion = 0
    n_lines = 0

    for line in args.input.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            body = row.get("response", {}).get("body", {})
            usage = body.get("usage", {})
            total_prompt += usage.get("prompt_tokens", 0)
            total_completion += usage.get("completion_tokens", 0)
            n_lines += 1
        except (json.JSONDecodeError, KeyError):
            continue

    if n_lines == 0:
        print("Error: No valid lines in batch output", file=sys.stderr)
        sys.exit(1)

    scale = args.total_chars / n_lines
    est_prompt = int(total_prompt * scale)
    est_completion = int(total_completion * scale)
    est_total = est_prompt + est_completion

    cost_input = (est_prompt / 1_000_000) * BATCH_INPUT_RATE
    cost_output = (est_completion / 1_000_000) * BATCH_OUTPUT_RATE
    cost_total = cost_input + cost_output

    # Standard API cost (for comparison - 2x batch)
    std_input_rate = 0.15
    std_output_rate = 0.60
    cost_std = (est_prompt / 1_000_000) * std_input_rate + (est_completion / 1_000_000) * std_output_rate

    print("=== Cost estimate: full corpus gloss generation ===\n")
    print(f"Based on pilot: {n_lines} characters from {args.input}")
    print(f"Extrapolated to: {args.total_chars} characters\n")
    print("Token usage (extrapolated):")
    print(f"  Input tokens:     {est_prompt:,}")
    print(f"  Output tokens:    {est_completion:,}")
    print(f"  Total:            {est_total:,}")
    print(f"  Avg per character: {est_total / args.total_chars:,.0f} tokens\n")
    print("Batch API cost (gpt-4o-mini, 50% discount):")
    print(f"  Input:  {est_prompt:,} tokens × ${BATCH_INPUT_RATE}/1M = ${cost_input:.3f}")
    print(f"  Output: {est_completion:,} tokens × ${BATCH_OUTPUT_RATE}/1M = ${cost_output:.3f}")
    print(f"  Total:  ${cost_total:.3f}\n")
    print(f"(Standard API would be ~${cost_std:.3f}, ~2× batch)")


if __name__ == "__main__":
    main()
