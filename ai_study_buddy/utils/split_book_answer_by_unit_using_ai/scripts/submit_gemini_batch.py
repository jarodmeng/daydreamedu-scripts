#!/usr/bin/env python3
"""
Upload a Gemini Batch API JSONL file and create a batch job.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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
    parser = argparse.ArgumentParser(description="Upload JSONL and create Gemini batch job")
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("--job-info", type=Path, required=True, help="Where to save batch job metadata JSON")
    parser.add_argument(
        "--job-name-file",
        type=Path,
        default=None,
        help="Optional: write the batch job resource name (one line) for check_gemini_batch_status.py --job-info",
    )
    parser.add_argument("--model", default="models/gemini-2.5-pro")
    args = parser.parse_args()

    api_key = os.getenv("GOOGLE_AI_DAYDREAMEDU_KEY")
    if not api_key:
        raise SystemExit("Error: GOOGLE_AI_DAYDREAMEDU_KEY is not set in the environment")
    if not args.input_jsonl.exists():
        raise SystemExit(f"Error: Input file not found: {args.input_jsonl}")

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise SystemExit("Error: google-genai package required. Install with: pip install google-genai")

    client = genai.Client(api_key=api_key)

    uploaded = client.files.upload(file=str(args.input_jsonl), config=types.UploadFileConfig(mime_type="jsonl"))
    job = client.batches.create(
        model=args.model,
        src=uploaded.name,
        config=types.CreateBatchJobConfig(display_name=f"batch-{args.input_jsonl.stem}"),
    )

    payload = {
        "input_jsonl": str(args.input_jsonl),
        "uploaded_file": serialize(uploaded),
        "job": serialize(job),
    }
    args.job_info.parent.mkdir(parents=True, exist_ok=True)
    args.job_info.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    job_ref = getattr(job, "name", None) or getattr(job, "id", None)
    print(f"Uploaded file: {uploaded.name}")
    print(f"Created batch job: {job_ref}")
    print(f"Saved job info to {args.job_info}")
    if args.job_name_file is not None:
        args.job_name_file.parent.mkdir(parents=True, exist_ok=True)
        args.job_name_file.write_text(f"{job_ref}\n", encoding="utf-8")
        print(f"Wrote job name to {args.job_name_file}")


if __name__ == "__main__":
    main()
