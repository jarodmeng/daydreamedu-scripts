#!/usr/bin/env python3
"""
Apply exported Feng word review decisions into a curated artifact.

Usage:
  python3 chinese_chr_app/tag_character_pinyin_using_ai/scripts/apply_feng_word_reading_decisions.py --decisions ~/Downloads/feng_word_reading_decisions.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT = ROOT / "artifacts" / "feng_word_reading_decisions.applied.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply exported Feng word reading decisions.")
    parser.add_argument("--decisions", type=Path, required=True, help="Path to exported feng_word_reading_decisions.json")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help="Output artifact path.")
    args = parser.parse_args()

    if not args.decisions.exists():
        print(f"Error: decisions file not found: {args.decisions}", file=sys.stderr)
        sys.exit(1)

    payload = json.loads(args.decisions.read_text(encoding="utf-8"))
    results = []
    total_words = 0
    decided_words = 0

    for character_block in payload:
        character = character_block.get("character")
        allowed_readings = character_block.get("allowed_readings") or []
        extra_readings = character_block.get("extra_readings") or []
        word_results = []
        for word in character_block.get("words", []):
            total_words += 1
            reading = (word.get("reading") or "").strip()
            if reading:
                decided_words += 1
            word_results.append(
                {
                    "text": word.get("text"),
                    "reading": reading or "unknown",
                    "notes": (word.get("notes") or "").strip(),
                    "source": (word.get("source") or "feng_word").strip() or "feng_word",
                }
            )
        results.append(
            {
                "character": character,
                "allowed_readings": allowed_readings,
                "extra_readings": extra_readings,
                "results": word_results,
            }
        )

    artifact = {
        "character_count": len(results),
        "total_words": total_words,
        "decided_words": decided_words,
        "undecided_words": total_words - decided_words,
        "characters": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote applied decisions to {args.output}")
    print(f"Characters: {len(results)}")
    print(f"Words: {total_words}")
    print(f"Decided: {decided_words}")


if __name__ == "__main__":
    main()
