#!/usr/bin/env python3
"""
Check a Gemini batch job and download output when complete.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path


def serialize(obj):
    if obj is None:
        return None
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    for attr in ("model_dump", "to_json_dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    if isinstance(obj, (dict, list, str, int, float, bool)):
        return obj
    return repr(obj)


def to_jsonable(value):
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]
    return serialize(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Gemini batch job status")
    parser.add_argument("--job-info", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None, help="Where to save batch output JSONL when complete")
    parser.add_argument("--metadata-out", type=Path, default=None, help="Where to save refreshed job metadata JSON")
    parser.add_argument("--poll", action="store_true", help="Poll until the batch reaches a terminal state")
    parser.add_argument("--poll-interval", type=int, default=30, help="Polling interval in seconds")
    args = parser.parse_args()

    api_key = os.getenv("GOOGLE_AI_DAYDREAMEDU_KEY")
    if not api_key:
        raise SystemExit("Error: GOOGLE_AI_DAYDREAMEDU_KEY is not set in the environment")
    if not args.job_info.exists():
        raise SystemExit(f"Error: Job info file not found: {args.job_info}")

    try:
        from google import genai
    except ImportError:
        raise SystemExit("Error: google-genai package required. Install with: pip install google-genai")

    payload = json.loads(args.job_info.read_text(encoding="utf-8"))
    job_name = ((payload.get("job") or {}).get("name")) or ((payload.get("job") or {}).get("id"))
    if not job_name:
        raise SystemExit("Error: Could not determine Gemini batch job name from job info")

    client = genai.Client(api_key=api_key)
    meta_path = args.metadata_out or args.job_info
    terminal_suffixes = ("SUCCEEDED", "FAILED", "CANCELLED", "EXPIRED")

    print(f"job: {job_name}")
    while True:
        job = client.batches.get(name=job_name)
        merged = dict(payload)
        merged["job"] = serialize(job)
        meta_path.write_text(json.dumps(to_jsonable(merged), ensure_ascii=False, indent=2), encoding="utf-8")

        state = getattr(job, "state", None)
        timestamp = datetime.now().isoformat(timespec="seconds")
        print(f"[{timestamp}] state: {state}")

        if not args.poll or str(state).upper().endswith(terminal_suffixes):
            break
        time.sleep(args.poll_interval)

    if str(state).upper().endswith("SUCCEEDED"):
        dest = args.output
        if dest is None:
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        results = client.files.download(file=job.dest.file_name)
        if isinstance(results, bytes):
            dest.write_bytes(results)
        else:
            dest.write_text(results.decode("utf-8") if isinstance(results, bytearray) else str(results), encoding="utf-8")
        print(f"Saved output to {dest}")


if __name__ == "__main__":
    main()
