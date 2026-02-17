#!/usr/bin/env python3
"""
Submit a batch job to the OpenAI Batch API.

Uploads the JSONL input file and creates a batch. Saves the batch_id for
check_batch_status.py to poll and download results.

Usage:
  # Build pilot input, then submit (run from scripts/ or repo root)
  python3 build_batch_input.py --pilot 50 --stratify -o ../batch_artifacts/batch_pilot.jsonl
  python3 submit_batch.py ../batch_artifacts/batch_pilot.jsonl

  # Submit with default (batch_artifacts/batch_input.jsonl)
  python3 submit_batch.py

  # Custom batch ID file
  python3 submit_batch.py ../batch_artifacts/batch_input.jsonl --batch-id-file ../batch_artifacts/batch_id_custom.txt
"""

import argparse
import sys
from pathlib import Path

# Default paths
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"
DEFAULT_INPUT_JSONL = BATCH_ARTIFACTS / "batch_input.jsonl"
DEFAULT_BATCH_ID_FILE = BATCH_ARTIFACTS / "batch_id.txt"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload JSONL and create OpenAI Batch job"
    )
    parser.add_argument(
        "input_jsonl",
        type=Path,
        nargs="?",
        default=DEFAULT_INPUT_JSONL,
        help="Path to input JSONL file (from build_batch_input.py)",
    )
    parser.add_argument(
        "--batch-id-file",
        type=Path,
        default=DEFAULT_BATCH_ID_FILE,
        help="Where to save batch_id for check_batch_status.py",
    )
    parser.add_argument(
        "--endpoint",
        default="/v1/chat/completions",
        help="API endpoint for batch (default: /v1/chat/completions)",
    )
    parser.add_argument(
        "--completion-window",
        default="24h",
        choices=("24h",),
        help="Batch completion window (default: 24h)",
    )
    args = parser.parse_args()

    if not args.input_jsonl.exists():
        print(f"Error: Input file not found: {args.input_jsonl}", file=sys.stderr)
        print(
            "Run build_batch_input.py first, e.g.:\n"
            "  python3 build_batch_input.py --pilot 50 --stratify -o batch_pilot.jsonl",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package required. Install with: pip install openai", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()
    n_lines = sum(1 for _ in args.input_jsonl.open(encoding="utf-8"))
    print(f"Uploading {args.input_jsonl} ({n_lines} requests)...", file=sys.stderr)

    # 1. Upload file
    with args.input_jsonl.open("rb") as f:
        file_obj = client.files.create(file=f, purpose="batch")

    print(f"Uploaded file: {file_obj.id}", file=sys.stderr)

    # 2. Create batch
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint=args.endpoint,
        completion_window=args.completion_window,
    )

    batch_id = batch.id
    args.batch_id_file.write_text(batch_id, encoding="utf-8")
    print(f"Created batch: {batch_id}", file=sys.stderr)
    print(f"Saved batch_id to {args.batch_id_file}", file=sys.stderr)
    print(
        f"\nPoll status with:\n  python3 check_batch_status.py\n"
        f"  python3 check_batch_status.py --batch-id {batch_id}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
