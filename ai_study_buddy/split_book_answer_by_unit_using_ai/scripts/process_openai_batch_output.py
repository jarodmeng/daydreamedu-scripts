#!/usr/bin/env python3
"""
Process OpenAI Batch API output JSONL (Responses endpoint) into the common
processed-results shape expected by assemble_ranges_from_page_segments_continuation.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _extract_output_text(body: dict) -> str:
    chunks: list[str] = []
    for block in body.get("output") or []:
        if not isinstance(block, dict):
            continue
        for part in block.get("content") or []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "output_text":
                t = part.get("text")
                if isinstance(t, str):
                    chunks.append(t)
    return "".join(chunks).strip()


def _extract_reasoning_summary_text(body: dict) -> str:
    """Collect OpenAI reasoning.summary entries (when reasoning.summary was requested)."""
    parts: list[str] = []
    for block in body.get("output") or []:
        if not isinstance(block, dict) or block.get("type") != "reasoning":
            continue
        for item in block.get("summary") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "summary_text":
                t = item.get("text")
                if isinstance(t, str) and t.strip():
                    parts.append(t.strip())
    return "\n\n".join(parts).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process OpenAI batch output JSONL into processed JSON")
    parser.add_argument("-i", "--input", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Error: Input file not found: {args.input}")

    results: dict[str, dict] = {}
    parse_errors: list[dict] = []

    for line_no, line in enumerate(args.input.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            parse_errors.append({"line": line_no, "error": f"jsonl_parse_error: {exc}"})
            continue

        custom_id = row.get("custom_id") or f"line:{line_no}"
        err = row.get("error")
        if err:
            parse_errors.append({"line": line_no, "custom_id": custom_id, "error": "batch_row_error", "detail": err})
            continue

        response = row.get("response") or {}
        status_code = response.get("status_code")
        body = response.get("body") or {}
        if status_code != 200:
            parse_errors.append(
                {
                    "line": line_no,
                    "custom_id": custom_id,
                    "error": "non_200_response",
                    "status_code": status_code,
                    "body_error": body.get("error"),
                }
            )
            continue

        output_text = _extract_output_text(body)
        if not output_text:
            parse_errors.append(
                {
                    "line": line_no,
                    "custom_id": custom_id,
                    "error": "missing_output_text",
                    "response_status": body.get("status"),
                }
            )
            continue

        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            parse_errors.append(
                {
                    "line": line_no,
                    "custom_id": custom_id,
                    "error": f"output_json_parse_error: {exc}",
                    "raw_output_excerpt": output_text[:400],
                }
            )
            continue

        thought = _extract_reasoning_summary_text(body)
        if thought:
            parsed["_thought_summary"] = thought

        results[custom_id] = parsed

    out_payload = {
        "provider": "openai",
        "results": results,
        "parse_errors": parse_errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} parsed result(s) to {args.output}")
    if parse_errors:
        print(f"Parse errors: {len(parse_errors)}", file=sys.stderr)


if __name__ == "__main__":
    main()
