#!/usr/bin/env python3
"""
Run one English gloss generation prompt for a single character.
Uses the system and user message format from english_gloss_generation_prompt.md.

Loads the character from extracted_characters_hwxnet.json (supports any character in the corpus).

Usage:
  # Dry run: print request, do not call API
  python3 run_single_gloss_prompt.py --hanzi 代 --dry-run

  # Count input tokens (needs: pip install tiktoken)
  python3 run_single_gloss_prompt.py --hanzi 代 --count-tokens

  # Call OpenAI API (requires OPENAI_API_KEY)
  python3 run_single_gloss_prompt.py --hanzi 代

  # Default character: 大 (has multiple senses; good test case)
  python3 run_single_gloss_prompt.py

  # Exclude existing gloss—derive purely from Chinese definitions
  python3 run_single_gloss_prompt.py --hanzi 代 --no-current-gloss
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Default paths
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DEFAULT_PROMPT_MD = ROOT / "prompts" / "english_gloss_generation_prompt.md"
DEFAULT_DATA_JSON = ROOT.parent / "data" / "extracted_characters_hwxnet.json"


def extract_system_message(prompt_md_path: Path) -> str:
    """Extract the system message from the first code block under '## 1. System message'."""
    text = prompt_md_path.read_text(encoding="utf-8")
    start_marker = "## 1. System message"
    idx = text.find(start_marker)
    if idx == -1:
        raise ValueError(f"Could not find '{start_marker}' in {prompt_md_path}")
    rest = text[idx + len(start_marker) :]
    match = re.search(r"```\s*\n(.*?)```", rest, re.DOTALL)
    if not match:
        raise ValueError("Could not find system message code block in prompt .md")
    return match.group(1).strip()


def char_to_user_payload(
    hanzi: str,
    entry: dict,
    *,
    include_current_gloss: bool = True,
) -> dict:
    """Convert a character entry from hwxnet JSON to the user message payload."""
    pinyin = entry.get("拼音") or []
    if not isinstance(pinyin, list):
        pinyin = [pinyin] if pinyin else []
    stroke_count = entry.get("总笔画")
    if stroke_count is not None and not isinstance(stroke_count, int):
        try:
            stroke_count = int(stroke_count)
        except (TypeError, ValueError):
            stroke_count = None

    payload = {
        "hanzi": hanzi,
        "pinyin": pinyin,
        "radical": entry.get("部首", ""),
        "stroke_count": stroke_count,
        "basic_meanings": entry.get("基本字义解释", []),
    }
    if include_current_gloss:
        payload["current_english_gloss"] = entry.get("英文翻译") or []
    return payload


def validate_and_fix_response(parsed: dict, expected_hanzi: str) -> tuple[dict, list[str]]:
    """
    Validate API response and fill missing/invalid fields. Returns (fixed_parsed, list of fix messages).
    """
    fixes: list[str] = []

    if not isinstance(parsed.get("hanzi"), str) or parsed["hanzi"] != expected_hanzi:
        parsed["hanzi"] = expected_hanzi
        fixes.append("Set hanzi from request")

    if not parsed.get("english_gloss") or not isinstance(parsed["english_gloss"], str):
        parsed["english_gloss"] = "unknown"
        fixes.append("Set english_gloss to placeholder (missing)")

    if "confidence_score" not in parsed or not isinstance(parsed.get("confidence_score"), (int, float)):
        parsed["confidence_score"] = 0.5
        fixes.append("Set confidence_score to 0.5 (missing or invalid)")
    else:
        score = float(parsed["confidence_score"])
        if score < 0 or score > 1:
            parsed["confidence_score"] = max(0, min(1, score))
            fixes.append("Clamped confidence_score to [0, 1]")

    if "qc_flags" not in parsed or not isinstance(parsed.get("qc_flags"), dict):
        parsed["qc_flags"] = parsed.get("qc_flags") or {}
    for key in ("multi_sense", "needs_human_review", "review_reason"):
        if key not in parsed["qc_flags"]:
            parsed["qc_flags"][key] = False if key != "review_reason" else None
            fixes.append(f"Set qc_flags.{key}")

    return parsed, fixes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one gloss prompt for a character (default: 大)"
    )
    parser.add_argument(
        "--hanzi",
        default="大",
        help="Character to run (must exist in data JSON)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model (e.g. gpt-4o-mini, gpt-4o)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print request only; do not call the API",
    )
    parser.add_argument(
        "--count-tokens",
        action="store_true",
        help="Count input tokens (tiktoken) and exit; no API call",
    )
    parser.add_argument(
        "--prompt-md",
        type=Path,
        default=DEFAULT_PROMPT_MD,
        help="Path to english_gloss_generation_prompt.md",
    )
    parser.add_argument(
        "--data-json",
        type=Path,
        default=DEFAULT_DATA_JSON,
        help="Path to extracted_characters_hwxnet.json",
    )
    parser.add_argument(
        "--no-current-gloss",
        action="store_true",
        help="Exclude existing English gloss; derive purely from Chinese definitions",
    )
    args = parser.parse_args()

    if not args.prompt_md.exists():
        print(f"Error: Prompt file not found: {args.prompt_md}", file=sys.stderr)
        sys.exit(1)
    if not args.data_json.exists():
        print(f"Error: Data file not found: {args.data_json}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(args.data_json.read_text(encoding="utf-8"))
    if args.hanzi not in data:
        print(f"Error: Character '{args.hanzi}' not found in {args.data_json}", file=sys.stderr)
        sys.exit(1)

    entry = data[args.hanzi]
    system_content = extract_system_message(args.prompt_md)
    user_payload = char_to_user_payload(
        args.hanzi, entry, include_current_gloss=not args.no_current_gloss
    )
    user_content = json.dumps(user_payload, ensure_ascii=False, indent=2)

    request = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 256,
    }

    if args.count_tokens:
        try:
            import tiktoken
        except ImportError:
            print(
                "Error: tiktoken required for --count-tokens. Install with: pip install tiktoken",
                file=sys.stderr,
            )
            sys.exit(1)
        enc = tiktoken.encoding_for_model(args.model)
        system_tokens = len(enc.encode(system_content))
        user_tokens = len(enc.encode(user_content))
        total_input = system_tokens + user_tokens
        print(f"Input tokens (model={args.model}):")
        print(f"  system:  {system_tokens:,}")
        print(f"  user:    {user_tokens:,}")
        print(f"  total:   {total_input:,}")
        print(
            f"\nRough cost (single request): input ~${total_input * 0.15 / 1_000_000:.4f} at $0.15/1M; batch ~50% less."
        )
        return

    if args.dry_run:
        print("Dry run: request that would be sent to OpenAI Chat Completions:", file=sys.stderr)
        print(json.dumps({"model": request["model"], "response_format": request["response_format"]}, indent=2))
        print("\n--- System message (first 200 chars) ---", file=sys.stderr)
        print(
            system_content[:200] + "..." if len(system_content) > 200 else system_content,
            file=sys.stderr,
        )
        print("\n--- User message ---", file=sys.stderr)
        print(user_content, file=sys.stderr)
        print("\n(Set OPENAI_API_KEY and run without --dry-run to call the API.)", file=sys.stderr)
        return

    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package required. Install with: pip install openai", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()
    print(f"Calling OpenAI Chat Completions for character '{args.hanzi}' (model={args.model})...", file=sys.stderr)
    response = client.chat.completions.create(**request)
    content = response.choices[0].message.content

    try:
        parsed = json.loads(content)
        parsed, fixes = validate_and_fix_response(parsed, args.hanzi)
        if fixes:
            for msg in fixes:
                print(f"Validation fix: {msg}", file=sys.stderr)
        else:
            print("Validation: passed (no fixes needed)", file=sys.stderr)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print("Raw response (invalid JSON):", file=sys.stderr)
        print(content)


if __name__ == "__main__":
    main()
