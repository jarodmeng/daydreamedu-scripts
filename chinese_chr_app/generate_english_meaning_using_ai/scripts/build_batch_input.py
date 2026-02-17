#!/usr/bin/env python3
"""
Build JSONL input file for OpenAI Batch API (English gloss generation).

Loads extracted_characters_hwxnet.json, builds one Chat Completions request per character,
writes JSONL for batch upload. Supports stratified pilot sampling for testing.

Usage:
  # Full corpus (3664 characters)
  python3 build_batch_input.py -o ../batch_artifacts/batch_input.jsonl

  # Pilot run: 50 characters with stratified sampling
  python3 build_batch_input.py --pilot 50 --stratify -o ../batch_artifacts/batch_pilot.jsonl

  # First N characters only (no stratification)
  python3 build_batch_input.py --limit 100 -o ../batch_artifacts/batch_input.jsonl

  # Batch by zibiao_index range (e.g. batch 1 of 4: zibiao 1-1000)
  python3 build_batch_input.py --zibiao-min 1 --zibiao-max 1000 -o ../batch_artifacts/batch_input_b1.jsonl

  # Specific characters only (e.g. rerun for missing primary_sense)
  python3 build_batch_input.py --chars "丁,入,乃,也" -o ../batch_artifacts/batch_rerun.jsonl

  # Reproducible pilot with seed
  python3 build_batch_input.py --pilot 50 --stratify --seed 42 -o ../batch_artifacts/batch_pilot.jsonl

  # Exclude existing gloss (derive purely from Chinese definitions)
  python3 build_batch_input.py --no-current-gloss -o ../batch_artifacts/batch_input.jsonl
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Default paths (relative to repo root)
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent  # generate_english_meaning_using_ai/
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


def build_batch_request_line(
    hanzi: str,
    user_payload: dict,
    system_content: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 256,
) -> dict:
    """Build a single batch API request line (one JSON object per line in JSONL)."""
    return {
        "custom_id": f"char:{hanzi}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
        },
    }


def stratify_characters(
    data: dict,
    pilot_n: int,
    seed: int | None,
) -> list[str]:
    """
    Stratified sampling for pilot. Targets:
    - ~60% from 常用字 (changyong)
    - ~40% from 通用字 only (tongyong_only)
    - Ensure mix of stroke counts and multi-sense characters.

    Character classification: 常用字 vs 通用字-only (no "other" in this corpus).
    """
    import random

    rng = random.Random(seed)

    changyong = []  # has 常用字 in 分类
    tongyong_only = []  # has 通用字 but not 常用字
    multi_sense = []  # multiple 释义 or 读音

    for hanzi, entry in data.items():
        cats = entry.get("分类") or []
        if "常用字" in cats:
            changyong.append(hanzi)
        elif "通用字" in cats:
            tongyong_only.append(hanzi)

        # Multi-sense: multiple 释义 across 基本字义解释
        basic = entry.get("基本字义解释") or []
        total_shiyi = sum(
            len(reading.get("释义") or [])
            for reading in basic
            if isinstance(reading, dict)
        )
        if total_shiyi > 1 or len(basic) > 1:
            multi_sense.append(hanzi)

    # Targets: ~30 changyong, ~20 tongyong_only (50 total)
    n_changyong = min(int(pilot_n * 0.6), len(changyong))
    n_tongyong = min(pilot_n - n_changyong, len(tongyong_only))
    if n_changyong + n_tongyong < pilot_n:
        n_changyong = min(pilot_n - n_tongyong, len(changyong))

    sample_hanzi = []
    sample_hanzi_set = set()

    # Ensure some multi-sense in the sample (at least ~20% if available)
    n_multi_target = min(int(pilot_n * 0.25), len(multi_sense))
    multi_in_changyong = [h for h in multi_sense if h in changyong]
    multi_in_tongyong = [h for h in multi_sense if h in tongyong_only]
    rng.shuffle(multi_in_changyong)
    rng.shuffle(multi_in_tongyong)
    for h in multi_in_changyong[: max(1, n_multi_target // 2)]:
        if h not in sample_hanzi_set and len(sample_hanzi) < pilot_n:
            sample_hanzi.append(h)
            sample_hanzi_set.add(h)
    for h in multi_in_tongyong[: max(1, n_multi_target // 2)]:
        if h not in sample_hanzi_set and len(sample_hanzi) < pilot_n:
            sample_hanzi.append(h)
            sample_hanzi_set.add(h)

    # Fill changyong quota (excluding already chosen)
    changyong_pool = [h for h in changyong if h not in sample_hanzi_set]
    rng.shuffle(changyong_pool)
    for h in changyong_pool[: n_changyong - sum(1 for x in sample_hanzi if x in changyong)]:
        if len(sample_hanzi) < pilot_n:
            sample_hanzi.append(h)
            sample_hanzi_set.add(h)

    # Fill tongyong quota
    tongyong_pool = [h for h in tongyong_only if h not in sample_hanzi_set]
    rng.shuffle(tongyong_pool)
    for h in tongyong_pool[:n_tongyong]:
        if len(sample_hanzi) < pilot_n:
            sample_hanzi.append(h)
            sample_hanzi_set.add(h)

    # Top up from changyong if needed
    changyong_remaining = [h for h in changyong if h not in sample_hanzi_set]
    rng.shuffle(changyong_remaining)
    for h in changyong_remaining:
        if len(sample_hanzi) >= pilot_n:
            break
        sample_hanzi.append(h)
        sample_hanzi_set.add(h)

    # Top up from tongyong if still needed
    tongyong_remaining = [h for h in tongyong_only if h not in sample_hanzi_set]
    rng.shuffle(tongyong_remaining)
    for h in tongyong_remaining:
        if len(sample_hanzi) >= pilot_n:
            break
        sample_hanzi.append(h)
        sample_hanzi_set.add(h)

    return sample_hanzi[:pilot_n]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build JSONL input for OpenAI Batch API (English gloss generation)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("batch_input.jsonl"),
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--data-json",
        type=Path,
        default=DEFAULT_DATA_JSON,
        help="Path to extracted_characters_hwxnet.json",
    )
    parser.add_argument(
        "--prompt-md",
        type=Path,
        default=DEFAULT_PROMPT_MD,
        help="Path to english_gloss_generation_prompt.md",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model for batch",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256,
        help="Max tokens per response",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="First N characters only (no stratification)",
    )
    parser.add_argument(
        "--zibiao-min",
        type=int,
        default=None,
        help="Filter: zibiao_index >= this (batch by zibiao range)",
    )
    parser.add_argument(
        "--zibiao-max",
        type=int,
        default=None,
        help="Filter: zibiao_index <= this (use with --zibiao-min)",
    )
    parser.add_argument(
        "--chars",
        type=str,
        default=None,
        help="Comma-separated list of characters (e.g. '丁,入,乃'). Overrides other filters.",
    )
    parser.add_argument(
        "--pilot",
        type=int,
        default=None,
        help="Pilot run: sample N characters (use with --stratify)",
    )
    parser.add_argument(
        "--stratify",
        action="store_true",
        help="Use stratified sampling for --pilot (常用字, 通用字, multi-sense)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for stratified sampling (default: 42)",
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
    system_content = extract_system_message(args.prompt_md)

    if args.no_current_gloss:
        print("Mode: independent (no current gloss in prompt)", file=sys.stderr)

    # Select characters
    zibiao_min = args.zibiao_min
    zibiao_max = args.zibiao_max
    use_zibiao_range = zibiao_min is not None or zibiao_max is not None
    if use_zibiao_range:
        zibiao_min = zibiao_min if zibiao_min is not None else 0
        zibiao_max = zibiao_max if zibiao_max is not None else 999999

    if args.chars is not None:
        hanzi_list = [c.strip() for c in args.chars.split(",") if c.strip()]
        hanzi_list = [h for h in hanzi_list if h in data]
        print(f"Characters list (--chars): {len(hanzi_list)} characters", file=sys.stderr)
    elif args.pilot is not None and args.stratify:
        hanzi_list = stratify_characters(data, args.pilot, args.seed)
        print(f"Stratified pilot: selected {len(hanzi_list)} characters", file=sys.stderr)
    elif args.pilot is not None:
        # Pilot without stratify: random sample
        import random
        rng = random.Random(args.seed)
        all_hanzi = list(data.keys())
        rng.shuffle(all_hanzi)
        hanzi_list = all_hanzi[: args.pilot]
        print(f"Pilot (random): selected {len(hanzi_list)} characters", file=sys.stderr)
    elif args.limit is not None and not use_zibiao_range:
        hanzi_list = list(data.keys())[: args.limit]
        print(f"Limit: first {len(hanzi_list)} characters", file=sys.stderr)
    elif use_zibiao_range:
        # Filter by zibiao_index range; sort by zibiao for consistent ordering
        def _zi(e):
            zi = e.get("zibiao_index")
            if zi is None:
                return 999999
            try:
                return int(zi)
            except (TypeError, ValueError):
                return 999999

        candidates = [
            (h, _zi(data[h]))
            for h in data
            if zibiao_min <= _zi(data[h]) <= zibiao_max
        ]
        candidates.sort(key=lambda x: (x[1], x[0]))
        hanzi_list = [h for h, _ in candidates]
        print(
            f"Zibiao range [{zibiao_min}, {zibiao_max}]: {len(hanzi_list)} characters",
            file=sys.stderr,
        )
    else:
        hanzi_list = list(data.keys())
        print(f"Full corpus: {len(hanzi_list)} characters", file=sys.stderr)

    # Build JSONL
    include_current_gloss = not args.no_current_gloss
    lines = []
    for hanzi in hanzi_list:
        if hanzi not in data:
            continue
        entry = data[hanzi]
        payload = char_to_user_payload(hanzi, entry, include_current_gloss=include_current_gloss)
        req = build_batch_request_line(
            hanzi, payload, system_content, model=args.model, max_tokens=args.max_tokens
        )
        lines.append(json.dumps(req, ensure_ascii=False))

    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} requests to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
