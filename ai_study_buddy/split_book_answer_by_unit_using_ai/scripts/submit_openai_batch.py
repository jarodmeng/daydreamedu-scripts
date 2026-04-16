#!/usr/bin/env python3
"""
Upload an OpenAI Batch API JSONL file and create a batch job.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path


def _api_request(
    *,
    method: str,
    url: str,
    api_key: str,
    body: bytes | None = None,
    content_type: str | None = "application/json",
) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ssl_context = None
    try:
        import certifi  # type: ignore

        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ssl_context = None
    try:
        with urllib.request.urlopen(req, context=ssl_context) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI API error {exc.code}: {payload}") from exc


def upload_batch_file(input_jsonl: Path, api_key: str) -> dict:
    boundary = "----openai-batch-upload-boundary"
    content = input_jsonl.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="purpose"\r\n\r\n',
        b"batch\r\n",
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{input_jsonl.name}"\r\n'.encode(),
        b"Content-Type: application/jsonl\r\n\r\n",
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    return _api_request(
        method="POST",
        url="https://api.openai.com/v1/files",
        api_key=api_key,
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload JSONL and create OpenAI batch job")
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("--job-info", type=Path, required=True, help="Where to save batch job metadata JSON")
    parser.add_argument(
        "--job-name-file",
        type=Path,
        default=None,
        help="Optional: write the batch job id (one line)",
    )
    parser.add_argument(
        "--completion-window",
        default="24h",
        help="OpenAI batch completion window (default: 24h)",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Error: OPENAI_API_KEY is not set in the environment")
    if not args.input_jsonl.exists():
        raise SystemExit(f"Error: Input file not found: {args.input_jsonl}")

    uploaded = upload_batch_file(args.input_jsonl, api_key)
    payload = {
        "input_file_id": uploaded["id"],
        "endpoint": "/v1/responses",
        "completion_window": args.completion_window,
        "metadata": {"source_jsonl": str(args.input_jsonl)},
    }
    batch = _api_request(
        method="POST",
        url="https://api.openai.com/v1/batches",
        api_key=api_key,
        body=json.dumps(payload).encode("utf-8"),
    )

    out = {
        "input_jsonl": str(args.input_jsonl),
        "uploaded_file": uploaded,
        "batch": batch,
    }
    args.job_info.parent.mkdir(parents=True, exist_ok=True)
    args.job_info.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    batch_id = batch.get("id")
    print(f"Uploaded file: {uploaded.get('id')}")
    print(f"Created batch job: {batch_id}")
    print(f"Saved job info to {args.job_info}")

    if args.job_name_file is not None:
        args.job_name_file.parent.mkdir(parents=True, exist_ok=True)
        args.job_name_file.write_text(f"{batch_id}\n", encoding="utf-8")
        print(f"Wrote job id to {args.job_name_file}")


if __name__ == "__main__":
    main()
