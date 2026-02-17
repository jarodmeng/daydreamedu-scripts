#!/usr/bin/env python3
"""
Check OpenAI Batch job status and download results when complete.

Polls until the batch is completed, failed, expired, or cancelled.
On completion: downloads output to batch_output.jsonl.
On failure: downloads error file to batch_errors.jsonl.

Usage:
  # Use batch_id from batch_id.txt (saved by submit_batch.py)
  python3 check_batch_status.py

  # Specify batch ID explicitly
  python3 check_batch_status.py --batch-id batch_abc123

  # Download only (skip polling, batch must already be complete)
  python3 check_batch_status.py --batch-id batch_abc123 --download-only

  # Poll interval in seconds
  python3 check_batch_status.py --poll-interval 60
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Default paths
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"
DEFAULT_BATCH_ID_FILE = BATCH_ARTIFACTS / "batch_id.txt"
DEFAULT_OUTPUT_FILE = BATCH_ARTIFACTS / "batch_output.jsonl"
DEFAULT_ERROR_FILE = BATCH_ARTIFACTS / "batch_errors.jsonl"

TERMINAL_STATUSES = frozenset({"completed", "failed", "expired", "cancelled"})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poll Batch API status and download results"
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Batch ID (default: read from batch_id.txt)",
    )
    parser.add_argument(
        "--batch-id-file",
        type=Path,
        default=DEFAULT_BATCH_ID_FILE,
        help="File containing batch_id",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Output file for successful results (default: batch_output.jsonl)",
    )
    parser.add_argument(
        "--error-file",
        type=Path,
        default=DEFAULT_ERROR_FILE,
        help="Output file for error details when batch fails",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Seconds between status checks (default: 30)",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Skip polling; assume batch is already complete and download only",
    )
    args = parser.parse_args()

    batch_id = args.batch_id
    if not batch_id and args.batch_id_file.exists():
        batch_id = args.batch_id_file.read_text(encoding="utf-8").strip()
    if not batch_id:
        print(
            f"Error: No batch_id. Run submit_batch.py first or pass --batch-id",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package required. Install with: pip install openai", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()

    if not args.download_only:
        # Poll until terminal status
        print(f"Polling batch {batch_id} (interval={args.poll_interval}s)...", file=sys.stderr)
        while True:
            batch = client.batches.retrieve(batch_id)
            status = batch.status
            counts = getattr(batch, "request_counts", None)
            req_info = ""
            if counts:
                total = getattr(counts, "total", 0)
                completed = getattr(counts, "completed", 0)
                failed = getattr(counts, "failed", 0)
                req_info = f" ({completed}/{total} completed, {failed} failed)"

            print(f"  status={status}{req_info}", file=sys.stderr)

            if status in TERMINAL_STATUSES:
                break
            time.sleep(args.poll_interval)

        if status != "completed":
            print(f"Batch ended with status: {status}", file=sys.stderr)
            if getattr(batch, "error_file_id", None):
                print("Downloading error file...", file=sys.stderr)
                err_content = client.files.content(batch.error_file_id)
                args.error_file.write_text(err_content.text, encoding="utf-8")
                print(f"Saved errors to {args.error_file}", file=sys.stderr)
            sys.exit(1)
    else:
        batch = client.batches.retrieve(batch_id)
        if batch.status != "completed":
            print(f"Error: Batch status is '{batch.status}', not completed. Remove --download-only to poll.", file=sys.stderr)
            sys.exit(1)

    # Download output
    output_file_id = batch.output_file_id
    if not output_file_id:
        print("Error: No output_file_id (batch may not have completed successfully)", file=sys.stderr)
        sys.exit(1)

    print(f"Downloading output from file {output_file_id}...", file=sys.stderr)
    file_response = client.files.content(output_file_id)
    content = file_response.text if hasattr(file_response, "text") else file_response.read()

    # Batch API output: each line is JSON with custom_id and response
    args.output.write_text(content, encoding="utf-8")
    n_lines = len([line for line in content.splitlines() if line.strip()])
    print(f"Saved {n_lines} results to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
