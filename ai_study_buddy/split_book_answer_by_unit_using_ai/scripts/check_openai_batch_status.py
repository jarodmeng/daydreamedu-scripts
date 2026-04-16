#!/usr/bin/env python3
"""
Poll an OpenAI Batch job and download output JSONL when complete.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


def _ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _get_json(*, url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
    try:
        with urllib.request.urlopen(req, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI API error {exc.code}: {payload}") from exc


def _get_bytes(*, url: str, api_key: str) -> bytes:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
    try:
        with urllib.request.urlopen(req, context=_ssl_context()) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI API error {exc.code}: {payload}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Check OpenAI batch job status and download output")
    parser.add_argument("--job-info", type=Path, required=True, help="Job metadata JSON from submit_openai_batch.py")
    parser.add_argument("--output", type=Path, default=None, help="Where to save batch output JSONL when complete")
    parser.add_argument(
        "--metadata-out",
        type=Path,
        default=None,
        help="Where to save refreshed job metadata (defaults to --job-info)",
    )
    parser.add_argument("--poll", action="store_true", help="Poll until the batch reaches a terminal state")
    parser.add_argument("--poll-interval", type=int, default=30, help="Polling interval in seconds")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Error: OPENAI_API_KEY is not set in the environment")
    if not args.job_info.exists():
        raise SystemExit(f"Error: Job info file not found: {args.job_info}")

    payload = json.loads(args.job_info.read_text(encoding="utf-8"))
    batch_id = (payload.get("batch") or {}).get("id")
    if not batch_id:
        raise SystemExit("Error: Could not determine OpenAI batch id from job info")

    meta_path = args.metadata_out or args.job_info
    terminal = {"completed", "failed", "expired", "cancelled"}

    print(f"batch: {batch_id}")
    while True:
        batch = _get_json(url=f"https://api.openai.com/v1/batches/{batch_id}", api_key=api_key)
        merged = {
            "input_jsonl": payload.get("input_jsonl"),
            "uploaded_file": payload.get("uploaded_file"),
            "batch": batch,
        }
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

        status = (batch.get("status") or "").lower()
        ts = datetime.now().isoformat(timespec="seconds")
        print(f"[{ts}] status: {status}")

        if not args.poll or status in terminal:
            break
        time.sleep(args.poll_interval)

    if status == "completed" and args.output is not None:
        out_id = batch.get("output_file_id")
        if not out_id:
            raise SystemExit("Error: Batch completed but output_file_id is missing")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        body = _get_bytes(url=f"https://api.openai.com/v1/files/{out_id}/content", api_key=api_key)
        args.output.write_bytes(body)
        print(f"Saved output to {args.output}")
    elif status != "completed" and args.output is not None:
        print(f"Batch did not complete successfully (status={status}); not downloading output", file=sys.stderr)


if __name__ == "__main__":
    main()
