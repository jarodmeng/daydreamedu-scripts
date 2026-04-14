#!/usr/bin/env python3
"""
Process Gemini Batch API output JSONL into the common processed-results shape.

When the batch request used thinkingConfig.includeThoughts, non-JSON parts with
thought=true are concatenated into results[key]["_thought_summary"]. Final JSON
is taken only from non-thought text parts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _part_is_thought(part: dict) -> bool:
    """Gemini returns thought summaries in parts with thought=True (see Gemini thinking docs)."""
    return bool(part.get("thought"))


def _split_thought_and_answer_text(parts: list) -> tuple[str, str]:
    thought_chunks: list[str] = []
    answer_chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if not text:
            continue
        if _part_is_thought(part):
            thought_chunks.append(text)
        else:
            answer_chunks.append(text)
    return "".join(thought_chunks).strip(), "".join(answer_chunks).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process Gemini batch output JSONL")
    parser.add_argument("-i", "--input", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Error: Input file not found: {args.input}")

    results = {}
    parse_errors = []

    for line_no, line in enumerate(args.input.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            parse_errors.append({"line": line_no, "error": f"jsonl_parse_error: {exc}"})
            continue

        key = row.get("key") or f"line:{line_no}"
        response = row.get("response") or {}
        candidates = response.get("candidates") or []
        if not candidates:
            parse_errors.append({"line": line_no, "key": key, "error": "missing_candidates"})
            continue

        cand0 = candidates[0]
        parts = ((cand0.get("content") or {}).get("parts")) or []
        thought_text, output_text = _split_thought_and_answer_text(parts)
        if not output_text:
            fr = cand0.get("finishReason")
            err: dict = {
                "line": line_no,
                "key": key,
                "error": "missing_text_parts",
                "finishReason": fr,
            }
            if thought_text:
                err["thought_summary_excerpt"] = thought_text[:2000]
            parse_errors.append(err)
            continue

        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            err = {
                "line": line_no,
                "key": key,
                "error": f"output_json_parse_error: {exc}",
                "raw_output_excerpt": output_text[:400],
            }
            if thought_text:
                err["thought_summary_excerpt"] = thought_text[:2000]
            parse_errors.append(err)
            continue

        if thought_text:
            parsed["_thought_summary"] = thought_text
        results[key] = parsed

    payload = {
        "provider": "google_ai",
        "results": results,
        "parse_errors": parse_errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} parsed result(s) to {args.output}")
    if parse_errors:
        print(f"Parse errors: {len(parse_errors)}", file=sys.stderr)


if __name__ == "__main__":
    main()
