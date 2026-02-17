#!/usr/bin/env python3
"""
Run one MCQ distractor-generation prompt for a single character (default: 代).
Uses the system and user message format from mcq_distractor_generation_prompt.md.

Including the full 3664-character universe in the user message adds roughly 5k–6k
input tokens per request (most of the user payload). Use --count-tokens to measure.

Usage:
  # Count input tokens (needs: pip install tiktoken)
  python3 run_single_distractor_prompt.py --count-tokens

  # Dry run: print request, do not call API
  python3 run_single_distractor_prompt.py --dry-run

  # Call OpenAI API (requires OPENAI_API_KEY)
  python3 run_single_distractor_prompt.py

  # Custom character (edit CHARACTER_PAYLOADS or extend script)
  python3 run_single_distractor_prompt.py --hanzi 代
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Character payload for 代 (from mcq_distractor_generation_prompt.md example)
CHARACTER_DAI = {
    "hanzi": "代",
    "pinyin": "dài",
    "radical": "亻",
    "stroke_count": 5,
    "structure": "左右结构",
    "english_gloss": "substitute; generation; era",
}

# Add more characters here if needed: hanzi -> character payload
CHARACTER_PAYLOADS = {
    "代": CHARACTER_DAI,
}


def extract_system_message(prompt_md_path: Path) -> str:
    """Extract the system message from the first code block under '## 1. System message'."""
    text = prompt_md_path.read_text(encoding="utf-8")
    # Find "## 1. System message" then the next ``` and take content until closing ```
    start_marker = "## 1. System message"
    idx = text.find(start_marker)
    if idx == -1:
        raise ValueError(f"Could not find '{start_marker}' in {prompt_md_path}")
    rest = text[idx + len(start_marker) :]
    match = re.search(r"```\s*\n(.*?)```", rest, re.DOTALL)
    if not match:
        raise ValueError("Could not find system message code block in prompt .md")
    return match.group(1).strip()


def load_character_universe(hwxnet_json_path: Path) -> list[str]:
    """Load the list of valid hanzi (character universe) from extracted_characters_hwxnet.json."""
    data = json.loads(hwxnet_json_path.read_text(encoding="utf-8"))
    return list(data.keys())


def build_user_message(
    character: dict,
    character_universe_hanzi: list[str],
    english_level: str = "L1",
    prompt_type: str = "hanzi_to_meaning",
) -> str:
    """Build the user message JSON string. Universe is sent as a single string to save tokens."""
    payload = {
        "character": character,
        "character_universe_hanzi": "".join(character_universe_hanzi),
        "english_level": english_level,
        "prompt_type": prompt_type,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_and_fix_response(parsed: dict, expected_hanzi: str, expected_english_level: str) -> tuple[dict, list[str]]:
    """
    Validate API response and fill missing/invalid fields. Returns (fixed_parsed, list of fix messages).
    """
    fixes: list[str] = []
    prompt_hanzi = expected_hanzi

    if not isinstance(parsed.get("prompt_hanzi"), str) or parsed["prompt_hanzi"] != expected_hanzi:
        parsed["prompt_hanzi"] = expected_hanzi
        fixes.append("Set prompt_hanzi from request")

    if not parsed.get("answer_en_controlled") or not isinstance(parsed["answer_en_controlled"], str):
        parsed["answer_en_controlled"] = "unknown"
        fixes.append("Set answer_en_controlled to placeholder (missing)")

    if "confusable_candidates" not in parsed or not isinstance(parsed["confusable_candidates"], list):
        parsed["confusable_candidates"] = []
        fixes.append("Set confusable_candidates to [] (missing)")
    elif len(parsed["confusable_candidates"]) < 5 and parsed.get("distractors_final"):
        existing = set(parsed["confusable_candidates"])
        for d in parsed["distractors_final"]:
            if isinstance(d, dict) and d.get("hanzi") and d["hanzi"] != prompt_hanzi:
                existing.add(d["hanzi"])
        parsed["confusable_candidates"] = list(existing)[:10]
        fixes.append("Filled confusable_candidates from distractors_final (had < 5)")

    if isinstance(parsed.get("distractors_final"), list):
        original_len = len(parsed["distractors_final"])
        parsed["distractors_final"] = [
            d for d in parsed["distractors_final"]
            if isinstance(d, dict) and d.get("hanzi") != prompt_hanzi
        ]
        if len(parsed["distractors_final"]) < original_len:
            fixes.append(f"Removed {original_len - len(parsed['distractors_final'])} distractor(s) that were the prompt character")

    if "qc_flags" not in parsed or not isinstance(parsed["qc_flags"], dict):
        parsed["qc_flags"] = parsed.get("qc_flags") or {}
    if "english_level" not in parsed["qc_flags"] or not parsed["qc_flags"].get("english_level"):
        parsed["qc_flags"]["english_level"] = expected_english_level
        fixes.append("Set qc_flags.english_level from request")

    return parsed, fixes


def main():
    parser = argparse.ArgumentParser(description="Run one distractor prompt for a character (default: 代)")
    parser.add_argument("--hanzi", default="代", help="Character to run (must be in CHARACTER_PAYLOADS)")
    parser.add_argument("--english-level", default="L1", choices=("L1", "L2"), help="Controlled vocabulary level")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model (e.g. gpt-4o-mini, gpt-4o)")
    parser.add_argument("--dry-run", action="store_true", help="Print request only; do not call the API")
    parser.add_argument("--count-tokens", action="store_true", help="Count input tokens (tiktoken) and exit; no API call")
    parser.add_argument("--prompt-md", type=Path, default=None, help="Path to mcq_distractor_generation_prompt.md")
    parser.add_argument("--universe-json", type=Path, default=None, help="Path to extracted_characters_hwxnet.json (character universe)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    prompt_md_path = args.prompt_md or script_dir / "mcq_distractor_generation_prompt.md"
    if not prompt_md_path.exists():
        print(f"Error: Prompt file not found: {prompt_md_path}", file=sys.stderr)
        sys.exit(1)

    # Character universe: list of 3664 hanzi so the AI only proposes distractors from this set
    universe_path = args.universe_json or script_dir.parent / "data" / "extracted_characters_hwxnet.json"
    if not universe_path.exists():
        print(f"Error: Character universe not found: {universe_path}", file=sys.stderr)
        sys.exit(1)
    character_universe_hanzi = load_character_universe(universe_path)

    if args.hanzi not in CHARACTER_PAYLOADS:
        print(f"Error: No payload for '{args.hanzi}'. Add it to CHARACTER_PAYLOADS in this script.", file=sys.stderr)
        sys.exit(1)

    character = CHARACTER_PAYLOADS[args.hanzi]
    system_content = extract_system_message(prompt_md_path)
    user_content = build_user_message(character, character_universe_hanzi, english_level=args.english_level)

    request = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }

    if args.count_tokens:
        try:
            import tiktoken
        except ImportError:
            print("Error: tiktoken required for --count-tokens. Install with: pip install tiktoken", file=sys.stderr)
            sys.exit(1)
        enc = tiktoken.encoding_for_model(args.model)
        system_tokens = len(enc.encode(system_content))
        user_tokens = len(enc.encode(user_content))
        total_input = system_tokens + user_tokens
        print(f"Input tokens (model={args.model}):")
        print(f"  system:  {system_tokens:,}")
        universe_str_len = len("".join(character_universe_hanzi))
        print(f"  user:    {user_tokens:,}  (character_universe_hanzi is a string of {universe_str_len} hanzi)")
        print(f"  total:   {total_input:,}")
        print(f"\nRough cost (single request): input ~${total_input * 0.15 / 1_000_000:.4f} at $0.15/1M (standard); batch ~50% less.")
        print(f"For 3664 characters: ~{total_input * 3664:,} input tokens (~${total_input * 3664 * 0.09 / 1_000_000:.2f} at ~$0.09/1M batch input).")
        return

    if args.dry_run:
        print("Dry run: request that would be sent to OpenAI Chat Completions:")
        print(json.dumps({"model": request["model"], "response_format": request["response_format"]}, indent=2))
        print("\n--- System message (first 200 chars) ---")
        print(system_content[:200] + "..." if len(system_content) > 200 else system_content)
        universe_str = "".join(character_universe_hanzi)
        print("\n--- User message (character_universe_hanzi is a string of", len(universe_str), "hanzi) ---")
        user_obj = json.loads(user_content)
        if len(user_obj["character_universe_hanzi"]) > 40:
            user_obj["character_universe_hanzi"] = user_obj["character_universe_hanzi"][:40] + f"... ({len(universe_str)} total)"
        print(json.dumps(user_obj, ensure_ascii=False, indent=2))
        print("\n(Set OPENAI_API_KEY and run without --dry-run to call the API.)")
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
        parsed, fixes = validate_and_fix_response(parsed, args.hanzi, args.english_level)
        if fixes:
            for msg in fixes:
                print(f"Validation fix: {msg}", file=sys.stderr)
        else:
            print("Validation: passed (no fixes needed)", file=sys.stderr)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print(content)


if __name__ == "__main__":
    main()
