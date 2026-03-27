#!/usr/bin/env python3
"""
Review uncovered polyphonic readings and either remove the reading or add a sample word.

Coverage is considered present only when a reading has at least one sample word from:
1. 基本字义解释 -> 释义 -> 例词
2. 常用词组按拼音 -> Phrases
3. Feng WordsByPinyin -> Phrases

Review mode saves decisions to a JSON artifact so you can stop/resume.
Apply mode writes a curated JSON output where:
- remove decisions prune the reading from top-level 拼音 and reading-keyed fields
- add_sample_word decisions append the word into 常用词组按拼音 for that reading

Run from backend/:
  python3 scripts/characters/review_uncovered_polyphonic_readings.py list --limit 10
  python3 scripts/characters/review_uncovered_polyphonic_readings.py review --limit 20
  python3 scripts/characters/review_uncovered_polyphonic_readings.py apply
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
HWXNET_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
FENG_JSON = DATA_DIR / "characters.json"
DECISIONS_JSON = DATA_DIR / "hwxnet_polyphonic_uncovered_reading_decisions.json"
DEFAULT_OUTPUT_JSON = DATA_DIR / "extracted_characters_hwxnet.polyphonic_readings_reviewed.json"


def normalize_pinyin(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFC", value).strip()


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def unique_pinyin_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        pinyin = normalize_pinyin(value)
        if pinyin and pinyin not in seen:
            out.append(pinyin)
            seen.add(pinyin)
    return out


def has_nonempty_strings(values: Any) -> bool:
    if not isinstance(values, list):
        return False
    return any(isinstance(value, str) and value.strip() for value in values)


def unique_bucket_pinyin_with_phrases(buckets: Any) -> list[str]:
    if not isinstance(buckets, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        if not has_nonempty_strings(bucket.get("Phrases")):
            continue
        pinyin = normalize_pinyin(bucket.get("Pinyin"))
        if pinyin and pinyin not in seen:
            out.append(pinyin)
            seen.add(pinyin)
    return out


def basic_meaning_pinyin_with_examples(basic_meanings: Any) -> list[str]:
    if not isinstance(basic_meanings, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for sense in basic_meanings:
        if not isinstance(sense, dict):
            continue
        pinyin = normalize_pinyin(sense.get("读音"))
        if not pinyin:
            continue
        for definition in sense.get("释义") or []:
            if not isinstance(definition, dict):
                continue
            if has_nonempty_strings(definition.get("例词")):
                if pinyin not in seen:
                    out.append(pinyin)
                    seen.add(pinyin)
                break
    return out


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_feng_lookup(rows: Any) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return lookup
    for row in rows:
        if not isinstance(row, dict):
            continue
        character = normalize_text(row.get("Character"))
        if character and character not in lookup:
            lookup[character] = row
    return lookup


def collect_basic_meaning_context(entry: dict[str, Any], reading: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    matching_senses: list[dict[str, Any]] = []
    definitions: list[str] = []
    examples: list[str] = []
    for sense in entry.get("基本字义解释") or []:
        if not isinstance(sense, dict):
            continue
        if normalize_pinyin(sense.get("读音")) != reading:
            continue
        matching_senses.append(sense)
        for definition in sense.get("释义") or []:
            if not isinstance(definition, dict):
                continue
            explanation = normalize_text(definition.get("解释"))
            if explanation and explanation not in definitions:
                definitions.append(explanation)
            for example in definition.get("例词") or []:
                example_text = normalize_text(example)
                if example_text and example_text not in examples:
                    examples.append(example_text)
    return matching_senses, definitions, examples


def classify_basic_meanings_status(matching_senses: list[dict[str, Any]], examples: list[str]) -> str:
    if examples:
        return "has_examples"
    if matching_senses:
        return "has_entry_no_examples"
    return "missing_entry"


def extract_candidates(
    hwxnet_data: dict[str, Any],
    feng_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for character, entry in hwxnet_data.items():
        if not isinstance(entry, dict):
            continue

        top_pinyin = unique_pinyin_list(entry.get("拼音") or [])
        if len(top_pinyin) <= 1:
            continue

        basic_with_examples = set(basic_meaning_pinyin_with_examples(entry.get("基本字义解释") or []))
        hwxnet_bucket_with_phrases = set(
            unique_bucket_pinyin_with_phrases(entry.get("常用词组按拼音") or [])
        )
        feng_entry = feng_lookup.get(character) or {}
        feng_bucket_with_phrases = set(
            unique_bucket_pinyin_with_phrases(feng_entry.get("WordsByPinyin") or [])
        )

        covered = basic_with_examples | hwxnet_bucket_with_phrases | feng_bucket_with_phrases
        uncovered = [reading for reading in top_pinyin if reading not in covered]
        if not uncovered:
            continue

        for reading in uncovered:
            matching_senses, definitions, examples = collect_basic_meaning_context(entry, reading)
            basic_meanings_status = classify_basic_meanings_status(matching_senses, examples)
            candidate = {
                "character": character,
                "reading": reading,
                "top_pinyin": top_pinyin,
                "zibiao_index": entry.get("zibiao_index"),
                "basic_meanings_reading_entry": matching_senses,
                "basic_meanings_has_reading": bool(matching_senses),
                "basic_meanings_status": basic_meanings_status,
                "basic_meanings_examples": examples,
                "definitions": definitions,
                "covered_by_basic_meanings_with_examples": reading in basic_with_examples,
                "covered_by_hwxnet_phrase_buckets": reading in hwxnet_bucket_with_phrases,
                "covered_by_feng_words_by_pinyin": reading in feng_bucket_with_phrases,
                "hwxnet_bucket_phrases": bucket_phrases_for_reading(entry.get("常用词组按拼音") or [], reading),
                "feng_bucket_phrases": bucket_phrases_for_reading(feng_entry.get("WordsByPinyin") or [], reading),
            }
            candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            10**9 if item.get("zibiao_index") is None else item["zibiao_index"],
            item["character"],
            item["reading"],
        )
    )
    return candidates


def bucket_phrases_for_reading(buckets: Any, reading: str) -> list[str]:
    phrases: list[str] = []
    if not isinstance(buckets, list):
        return phrases
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        if normalize_pinyin(bucket.get("Pinyin")) != reading:
            continue
        for phrase in bucket.get("Phrases") or []:
            phrase_text = normalize_text(phrase)
            if phrase_text and phrase_text not in phrases:
                phrases.append(phrase_text)
    return phrases


def decision_key(character: str, reading: str) -> str:
    return f"{character}|{reading}"


def load_decisions(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = load_json(path)
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
        "description": (
            "Review decisions for uncovered polyphonic readings. "
            "Actions: remove or add_sample_word into 常用词组按拼音."
        ),
        "decisions": ordered,
    }
    save_json(path, payload)


def summarize(candidates: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> tuple[int, int, int, int]:
    reviewed = 0
    removed = 0
    added = 0
    skipped = 0
    for candidate in candidates:
        decision = decisions.get(decision_key(candidate["character"], candidate["reading"]), {})
        action = decision.get("action")
        if action in {"remove", "add_sample_word", "skip"}:
            reviewed += 1
        if action == "remove":
            removed += 1
        elif action == "add_sample_word":
            added += 1
        elif action == "skip":
            skipped += 1
    return reviewed, removed, added, skipped


def print_candidate(candidate: dict[str, Any], index: int, total: int, existing_action: str | None) -> None:
    print()
    print(f"[{index}/{total}] {candidate['character']}  reading: {candidate['reading']}")
    print(f"top-level 拼音: {candidate['top_pinyin']}")
    print(f"zibiao_index: {candidate.get('zibiao_index')}")
    print(f"existing decision: {existing_action or 'undecided'}")
    print(
        "coverage flags: "
        f"basic_with_examples={candidate['covered_by_basic_meanings_with_examples']}  "
        f"常用词组按拼音={candidate['covered_by_hwxnet_phrase_buckets']}  "
        f"WordsByPinyin={candidate['covered_by_feng_words_by_pinyin']}"
    )
    print(
        "basic_meanings status: "
        f"{candidate['basic_meanings_status']} "
        "(has_examples | has_entry_no_examples | missing_entry)"
    )
    if candidate["definitions"]:
        print("definitions:")
        for definition in candidate["definitions"][:5]:
            print(f"  - {definition}")
    if candidate["basic_meanings_examples"]:
        print("basic_meanings 例词:")
        for example in candidate["basic_meanings_examples"][:8]:
            print(f"  - {example}")
    if candidate["hwxnet_bucket_phrases"]:
        print("常用词组按拼音 phrases:")
        for phrase in candidate["hwxnet_bucket_phrases"][:8]:
            print(f"  - {phrase}")
    if candidate["feng_bucket_phrases"]:
        print("WordsByPinyin phrases:")
        for phrase in candidate["feng_bucket_phrases"][:8]:
            print(f"  - {phrase}")
    if candidate["basic_meanings_has_reading"]:
        print("basic_meanings reading entry:")
        print(json.dumps(candidate["basic_meanings_reading_entry"], ensure_ascii=False, indent=2))


def run_list(candidates: list[dict[str, Any]], decisions: dict[str, dict[str, Any]], limit: int | None) -> None:
    reviewed, removed, added, skipped = summarize(candidates, decisions)
    print(f"Candidates: {len(candidates)}")
    print(f"Reviewed: {reviewed}  remove: {removed}  add_sample_word: {added}  skip: {skipped}")
    rows = candidates[:limit] if limit else candidates
    for candidate in rows:
        decision = decisions.get(decision_key(candidate["character"], candidate["reading"]), {})
        print(
            json.dumps(
                {
                    "character": candidate["character"],
                    "reading": candidate["reading"],
                    "top_pinyin": candidate["top_pinyin"],
                    "basic_meanings_has_reading": candidate["basic_meanings_has_reading"],
                    "basic_meanings_status": candidate["basic_meanings_status"],
                    "basic_meanings_reading_entry": candidate["basic_meanings_reading_entry"],
                    "definitions": candidate["definitions"][:3],
                    "basic_meanings_examples": candidate["basic_meanings_examples"][:5],
                    "hwxnet_bucket_phrases": candidate["hwxnet_bucket_phrases"][:5],
                    "feng_bucket_phrases": candidate["feng_bucket_phrases"][:5],
                    "action": decision.get("action") or "undecided",
                    "sample_word": decision.get("sample_word"),
                },
                ensure_ascii=False,
            )
        )


def filter_candidates(
    candidates: list[dict[str, Any]],
    character_filter: str | None,
    basic_meanings_status: str | None,
    include_reviewed: bool,
    decisions: dict[str, dict[str, Any]],
    limit: int | None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for candidate in candidates:
        if character_filter and candidate["character"] != character_filter:
            continue
        if basic_meanings_status and candidate.get("basic_meanings_status") != basic_meanings_status:
            continue
        key = decision_key(candidate["character"], candidate["reading"])
        if not include_reviewed and key in decisions:
            continue
        filtered.append(candidate)
        if limit and len(filtered) >= limit:
            break
    return filtered


def run_review(
    candidates: list[dict[str, Any]],
    decisions_path: Path,
    decisions: dict[str, dict[str, Any]],
    limit: int | None,
    character_filter: str | None,
    basic_meanings_status: str | None,
    include_reviewed: bool,
) -> None:
    filtered = filter_candidates(
        candidates,
        character_filter,
        basic_meanings_status,
        include_reviewed,
        decisions,
        limit,
    )

    if not filtered:
        print("No matching review items.")
        return

    print("Commands: [r]emove  [a]dd sample word  [s]kip  [q]uit")
    for idx, candidate in enumerate(filtered, start=1):
        key = decision_key(candidate["character"], candidate["reading"])
        existing_decision = decisions.get(key) or {}
        existing_action = existing_decision.get("action")
        print_candidate(candidate, idx, len(filtered), existing_action)
        if existing_action == "add_sample_word" and existing_decision.get("sample_word"):
            print(f"existing sample word: {existing_decision['sample_word']}")
        while True:
            answer = input("decision> ").strip().lower()
            if answer in {"r", "remove"}:
                decisions[key] = {
                    "character": candidate["character"],
                    "reading": candidate["reading"],
                    "action": "remove",
                }
                save_decisions(decisions_path, decisions)
                break
            if answer in {"a", "add"}:
                sample_word = normalize_text(input("sample word> "))
                if not sample_word:
                    print("Sample word cannot be empty.")
                    continue
                decisions[key] = {
                    "character": candidate["character"],
                    "reading": candidate["reading"],
                    "action": "add_sample_word",
                    "sample_word": sample_word,
                }
                save_decisions(decisions_path, decisions)
                break
            if answer in {"s", "skip", ""}:
                decisions[key] = {
                    "character": candidate["character"],
                    "reading": candidate["reading"],
                    "action": "skip",
                }
                save_decisions(decisions_path, decisions)
                break
            if answer in {"q", "quit"}:
                save_decisions(decisions_path, decisions)
                print(f"Saved decisions to {decisions_path}")
                return
            print("Enter r, a, s, or q.")

    save_decisions(decisions_path, decisions)
    print(f"Saved decisions to {decisions_path}")


def remove_reading_from_buckets(buckets: Any, reading: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(buckets, list):
        return out
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        if normalize_pinyin(bucket.get("Pinyin")) == reading:
            continue
        out.append(bucket)
    return out


def ensure_hwxnet_bucket(entry: dict[str, Any], reading: str) -> list[dict[str, Any]]:
    buckets = entry.get("常用词组按拼音")
    if not isinstance(buckets, list):
        buckets = []
        entry["常用词组按拼音"] = buckets
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        if normalize_pinyin(bucket.get("Pinyin")) == reading:
            phrases = bucket.get("Phrases")
            if not isinstance(phrases, list):
                bucket["Phrases"] = []
            return buckets
    buckets.append({"Pinyin": reading, "Phrases": []})
    return buckets


def add_phrase_to_hwxnet_bucket(entry: dict[str, Any], reading: str, sample_word: str) -> bool:
    buckets = ensure_hwxnet_bucket(entry, reading)
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        if normalize_pinyin(bucket.get("Pinyin")) != reading:
            continue
        phrases = bucket.get("Phrases")
        if not isinstance(phrases, list):
            phrases = []
            bucket["Phrases"] = phrases
        if sample_word in [normalize_text(phrase) for phrase in phrases]:
            return False
        phrases.append(sample_word)
        return True
    return False


def apply_decisions(
    hwxnet_data: dict[str, Any],
    decisions: dict[str, dict[str, Any]],
    output_path: Path,
    in_place: bool,
) -> tuple[int, int, int]:
    changed_characters = 0
    removed_readings = 0
    added_sample_words = 0

    for key, decision in decisions.items():
        action = decision.get("action")
        if action not in {"remove", "add_sample_word"}:
            continue
        character = normalize_text(decision.get("character"))
        reading = normalize_pinyin(decision.get("reading"))
        if not character or not reading:
            continue
        entry = hwxnet_data.get(character)
        if not isinstance(entry, dict):
            continue

        char_changed = False
        if action == "remove":
            top_pinyin = unique_pinyin_list(entry.get("拼音") or [])
            next_top = [item for item in top_pinyin if item != reading]
            if next_top != top_pinyin:
                entry["拼音"] = next_top
                char_changed = True

            basic_meanings = entry.get("基本字义解释") or []
            if isinstance(basic_meanings, list):
                next_basic_meanings = [
                    sense
                    for sense in basic_meanings
                    if not (
                        isinstance(sense, dict)
                        and normalize_pinyin(sense.get("读音")) == reading
                    )
                ]
                if next_basic_meanings != basic_meanings:
                    entry["基本字义解释"] = next_basic_meanings
                    char_changed = True

            next_hwxnet_buckets = remove_reading_from_buckets(entry.get("常用词组按拼音") or [], reading)
            if next_hwxnet_buckets != (entry.get("常用词组按拼音") or []):
                entry["常用词组按拼音"] = next_hwxnet_buckets
                char_changed = True

            if char_changed:
                changed_characters += 1
                removed_readings += 1

        elif action == "add_sample_word":
            sample_word = normalize_text(decision.get("sample_word"))
            if sample_word and add_phrase_to_hwxnet_bucket(entry, reading, sample_word):
                changed_characters += 1
                added_sample_words += 1

    if in_place:
        backup_path = output_path.with_suffix(output_path.suffix + ".polyphonic_review_backup")
        shutil.copy2(output_path, backup_path)
        print(f"Backup written to {backup_path}")

    save_json(output_path, hwxnet_data)
    return changed_characters, removed_readings, added_sample_words


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review uncovered polyphonic readings and add sample words or remove readings.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in ("list", "review"):
        sub = subparsers.add_parser(command_name)
        sub.add_argument("--input", type=Path, default=HWXNET_JSON, help="Input HWXNet JSON path.")
        sub.add_argument("--feng", type=Path, default=FENG_JSON, help="Input Feng JSON path.")
        sub.add_argument("--decisions", type=Path, default=DECISIONS_JSON, help="Decision artifact path.")
        sub.add_argument("--limit", type=int, default=None, help="Maximum items to show/review.")
        sub.add_argument("--character", type=str, default=None, help="Only show/review one character.")
        sub.add_argument(
            "--basic-meanings-status",
            choices=["has_examples", "has_entry_no_examples", "missing_entry"],
            default=None,
            help="Filter to one basic_meanings status bucket.",
        )
        if command_name == "review":
            sub.add_argument(
                "--include-reviewed",
                action="store_true",
                help="Include entries that already have a recorded decision.",
            )

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--input", type=Path, default=HWXNET_JSON, help="Input HWXNet JSON path.")
    apply_parser.add_argument("--feng", type=Path, default=FENG_JSON, help="Input Feng JSON path.")
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

    hwxnet_data = load_json(args.input)
    if not isinstance(hwxnet_data, dict):
        raise SystemExit(f"Unexpected HWXNet JSON shape in {args.input}")
    feng_data = load_json(args.feng)
    feng_lookup = build_feng_lookup(feng_data)

    candidates = extract_candidates(hwxnet_data, feng_lookup)
    decisions = load_decisions(args.decisions)

    if args.command == "list":
        filtered = filter_candidates(
            candidates,
            args.character,
            args.basic_meanings_status,
            include_reviewed=True,
            decisions=decisions,
            limit=args.limit,
        )
        run_list(filtered, decisions, None)
        return

    if args.command == "review":
        run_review(
            candidates,
            args.decisions,
            decisions,
            args.limit,
            args.character,
            args.basic_meanings_status,
            args.include_reviewed,
        )
        return

    if args.command == "apply":
        output_path = args.input if args.in_place else args.output
        changed_characters, removed_readings, added_sample_words = apply_decisions(
            hwxnet_data,
            decisions,
            output_path,
            in_place=args.in_place,
        )
        print(f"Candidates: {len(candidates)}")
        print(f"Decisions loaded: {len(decisions)}")
        print(f"Characters changed: {changed_characters}")
        print(f"Readings removed: {removed_readings}")
        print(f"Sample words added to 常用词组按拼音: {added_sample_words}")
        print(f"Wrote {output_path}")
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
