#!/usr/bin/env python3
"""
Review extra HWXNet basic_meanings readings not present in top-level 拼音.

Run from backend/:
  python3 scripts/characters/review_extra_basic_meanings_pinyin.py review
  python3 scripts/characters/review_extra_basic_meanings_pinyin.py review --limit 20
  python3 scripts/characters/review_extra_basic_meanings_pinyin.py list --limit 10
  python3 scripts/characters/review_extra_basic_meanings_pinyin.py apply

The review mode saves decisions to a JSON artifact so you can stop/resume.
Apply mode writes a cleaned JSON file using "remove" decisions without
modifying the source file unless you explicitly point --output at it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
DATA_DIR = OUTER_APP_DIR / "data"
INPUT_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
DECISIONS_JSON = DATA_DIR / "hwxnet_extra_basic_meanings_pinyin_decisions.json"
DEFAULT_OUTPUT_JSON = DATA_DIR / "extracted_characters_hwxnet.basic_meanings_pinyin_reviewed.json"


def normalize_pinyin(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFC", value).strip()


def normalize_pinyin_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []

    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        norm = normalize_pinyin(item)
        if norm and norm not in seen:
            out.append(norm)
            seen.add(norm)
    return out


def load_data(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected top-level dict keyed by character.")
    return payload


def extract_candidates(data: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for character, entry in data.items():
        top_pinyin = normalize_pinyin_list(entry.get("拼音"))
        top_set = set(top_pinyin)
        basic_meanings = entry.get("基本字义解释") or []
        if not isinstance(basic_meanings, list):
            continue

        grouped: dict[str, dict[str, Any]] = {}
        for sense in basic_meanings:
            if not isinstance(sense, dict):
                continue
            reading = normalize_pinyin(sense.get("读音"))
            if not reading or reading in top_set:
                continue
            bucket = grouped.setdefault(
                reading,
                {
                    "character": character,
                    "top_pinyin": top_pinyin,
                    "basic_meanings_readings": [],
                    "reading": reading,
                    "sense_count": 0,
                    "definitions": [],
                    "examples": [],
                    "zibiao_index": entry.get("zibiao_index"),
                },
            )
            bucket["sense_count"] += 1
            for definition in sense.get("释义") or []:
                if not isinstance(definition, dict):
                    continue
                explanation = (definition.get("解释") or "").strip()
                if explanation and explanation not in bucket["definitions"]:
                    bucket["definitions"].append(explanation)
                for example in definition.get("例词") or []:
                    if not isinstance(example, str):
                        continue
                    example_text = example.strip()
                    if example_text and example_text not in bucket["examples"]:
                        bucket["examples"].append(example_text)

        for reading in grouped.values():
            basic_meanings_readings = []
            seen_basic = set()
            for sense in basic_meanings:
                if not isinstance(sense, dict):
                    continue
                basic_reading = normalize_pinyin(sense.get("读音"))
                if basic_reading and basic_reading not in seen_basic:
                    basic_meanings_readings.append(basic_reading)
                    seen_basic.add(basic_reading)
            reading["basic_meanings_readings"] = basic_meanings_readings
            candidates.append(reading)

    candidates.sort(
        key=lambda item: (
            10**9 if item.get("zibiao_index") is None else item["zibiao_index"],
            item["character"],
            item["reading"],
        )
    )
    return candidates


def decision_key(character: str, reading: str) -> str:
    return f"{character}|{reading}"


def load_decisions(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    decisions: dict[str, dict[str, Any]] = {}
    for item in payload.get("decisions", []):
        character = item.get("character")
        reading = item.get("reading")
        if isinstance(character, str) and isinstance(reading, str):
            decisions[decision_key(character, reading)] = item
    return decisions


def save_decisions(path: Path, decisions: dict[str, dict[str, Any]]) -> None:
    ordered = [
        decisions[key]
        for key in sorted(
            decisions.keys(),
            key=lambda key: (
                key.split("|", 1)[0],
                key.split("|", 1)[1],
            ),
        )
    ]
    payload = {
        "version": 1,
        "description": "Review decisions for extra HWXNet 基本字义解释 readings not present in top-level 拼音.",
        "decisions": ordered,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summarize(candidates: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> tuple[int, int, int, int]:
    reviewed = 0
    kept = 0
    removed = 0
    modified = 0
    for candidate in candidates:
        key = decision_key(candidate["character"], candidate["reading"])
        decision = decisions.get(key, {})
        action = decision.get("action")
        if action in {"keep", "remove", "modify"}:
            reviewed += 1
        if action == "keep":
            kept += 1
        elif action == "remove":
            removed += 1
        elif action == "modify":
            modified += 1
    return reviewed, kept, removed, modified


def print_candidate(candidate: dict[str, Any], index: int, total: int, existing_action: str | None) -> None:
    print()
    print(f"[{index}/{total}] {candidate['character']}  extra reading: {candidate['reading']}")
    print(f"top-level 拼音: {candidate['top_pinyin']}")
    print(f"基本字义解释 readings: {candidate.get('basic_meanings_readings') or []}")
    print(f"zibiao_index: {candidate.get('zibiao_index')}")
    print(f"existing decision: {existing_action or 'undecided'}")
    print("definitions:")
    for definition in candidate["definitions"][:5]:
        print(f"  - {definition}")
    if candidate["examples"]:
        print("examples:")
        for example in candidate["examples"][:8]:
            print(f"  - {example}")


def run_list(candidates: list[dict[str, Any]], decisions: dict[str, dict[str, Any]], limit: int | None) -> None:
    reviewed, kept, removed, modified = summarize(candidates, decisions)
    print(f"Candidates: {len(candidates)}")
    print(f"Reviewed: {reviewed}  keep: {kept}  remove: {removed}  modify: {modified}")
    rows = candidates[:limit] if limit else candidates
    for candidate in rows:
        key = decision_key(candidate["character"], candidate["reading"])
        decision = decisions.get(key, {})
        action = decision.get("action") or "undecided"
        print(
            json.dumps(
                {
                    "character": candidate["character"],
                    "reading": candidate["reading"],
                    "top_pinyin": candidate["top_pinyin"],
                    "basic_meanings_readings": candidate.get("basic_meanings_readings") or [],
                    "action": action,
                    "replacement_reading": decision.get("replacement_reading"),
                    "definitions": candidate["definitions"][:3],
                    "examples": candidate["examples"][:5],
                },
                ensure_ascii=False,
            )
        )


def run_review(
    candidates: list[dict[str, Any]],
    decisions_path: Path,
    decisions: dict[str, dict[str, Any]],
    limit: int | None,
    character_filter: str | None,
    include_reviewed: bool,
) -> None:
    filtered = []
    for candidate in candidates:
        if character_filter and candidate["character"] != character_filter:
            continue
        key = decision_key(candidate["character"], candidate["reading"])
        if not include_reviewed and key in decisions:
            continue
        filtered.append(candidate)
        if limit and len(filtered) >= limit:
            break

    if not filtered:
        print("No matching review items.")
        return

    print("Commands: [k]eep  [r]emove  [m]odify  [s]kip  [q]uit")
    for idx, candidate in enumerate(filtered, start=1):
        key = decision_key(candidate["character"], candidate["reading"])
        existing_decision = decisions.get(key) or {}
        existing_action = existing_decision.get("action")
        print_candidate(candidate, idx, len(filtered), existing_action)
        if existing_action == "modify" and existing_decision.get("replacement_reading"):
            print(f"existing replacement: {existing_decision['replacement_reading']}")
        while True:
            answer = input("decision> ").strip().lower()
            if answer in {"k", "keep"}:
                decisions[key] = {
                    "character": candidate["character"],
                    "reading": candidate["reading"],
                    "action": "keep",
                }
                save_decisions(decisions_path, decisions)
                break
            if answer in {"r", "remove"}:
                decisions[key] = {
                    "character": candidate["character"],
                    "reading": candidate["reading"],
                    "action": "remove",
                }
                save_decisions(decisions_path, decisions)
                break
            if answer in {"m", "modify"}:
                replacement = normalize_pinyin(input("new pinyin> "))
                if not replacement:
                    print("Replacement pinyin cannot be empty.")
                    continue
                decisions[key] = {
                    "character": candidate["character"],
                    "reading": candidate["reading"],
                    "action": "modify",
                    "replacement_reading": replacement,
                }
                save_decisions(decisions_path, decisions)
                break
            if answer in {"s", "skip", ""}:
                break
            if answer in {"q", "quit"}:
                save_decisions(decisions_path, decisions)
                print(f"Saved decisions to {decisions_path}")
                return
            print("Enter k, r, m, s, or q.")

    save_decisions(decisions_path, decisions)
    print(f"Saved decisions to {decisions_path}")


def apply_decisions(
    data: dict[str, Any],
    decisions: dict[str, dict[str, Any]],
    output_path: Path,
    in_place: bool,
) -> tuple[int, int, int]:
    updated_characters = 0
    removed_senses = 0
    modified_senses = 0

    for character, entry in data.items():
        basic_meanings = entry.get("基本字义解释") or []
        if not isinstance(basic_meanings, list):
            continue

        next_basic_meanings = []
        char_changed = False
        for sense in basic_meanings:
            if not isinstance(sense, dict):
                next_basic_meanings.append(sense)
                continue
            reading = normalize_pinyin(sense.get("读音"))
            key = decision_key(character, reading)
            decision = decisions.get(key, {})
            if decision.get("action") == "remove":
                removed_senses += 1
                char_changed = True
                continue
            if decision.get("action") == "modify":
                replacement = normalize_pinyin(decision.get("replacement_reading"))
                if replacement and replacement != reading:
                    next_sense = dict(sense)
                    next_sense["读音"] = replacement
                    next_basic_meanings.append(next_sense)
                    modified_senses += 1
                    char_changed = True
                    continue
            next_basic_meanings.append(sense)

        if char_changed:
            entry["基本字义解释"] = next_basic_meanings
            updated_characters += 1

    if in_place:
        backup_path = output_path.with_suffix(output_path.suffix + ".extra_basic_meanings_backup")
        shutil.copy2(output_path, backup_path)
        print(f"Backup written to {backup_path}")

    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return updated_characters, removed_senses, modified_senses


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review extra 基本字义解释 pinyin readings not present in top-level 拼音.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in ("list", "review"):
        sub = subparsers.add_parser(command_name)
        sub.add_argument("--input", type=Path, default=INPUT_JSON, help="Input HWXNet JSON path.")
        sub.add_argument("--decisions", type=Path, default=DECISIONS_JSON, help="Decision artifact path.")
        sub.add_argument("--limit", type=int, default=None, help="Maximum items to show/review.")
        sub.add_argument("--character", type=str, default=None, help="Only show/review one character.")
        if command_name == "review":
            sub.add_argument(
                "--include-reviewed",
                action="store_true",
                help="Include entries that already have a keep/remove decision.",
            )

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--input", type=Path, default=INPUT_JSON, help="Input HWXNet JSON path.")
    apply_parser.add_argument("--decisions", type=Path, default=DECISIONS_JSON, help="Decision artifact path.")
    apply_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON, help="Output JSON path.")
    apply_parser.add_argument(
        "--in-place",
        action="store_true",
        help="Write back to the input file path and create a backup first.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    data = load_data(args.input)
    candidates = extract_candidates(data)
    decisions = load_decisions(args.decisions)

    if args.command == "list":
        run_list(
            [
                candidate
                for candidate in candidates
                if not args.character or candidate["character"] == args.character
            ],
            decisions,
            args.limit,
        )
        return

    if args.command == "review":
        run_review(
            candidates,
            args.decisions,
            decisions,
            args.limit,
            args.character,
            args.include_reviewed,
        )
        return

    if args.command == "apply":
        output_path = args.input if args.in_place else args.output
        updated_characters, removed_senses, modified_senses = apply_decisions(
            data,
            decisions,
            output_path,
            in_place=args.in_place,
        )
        print(f"Candidates: {len(candidates)}")
        print(f"Decisions loaded: {len(decisions)}")
        print(f"Characters changed: {updated_characters}")
        print(f"Basic-meaning senses removed: {removed_senses}")
        print(f"Basic-meaning senses modified: {modified_senses}")
        print(f"Wrote {output_path}")
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
