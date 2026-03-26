#!/usr/bin/env python3
"""
Add the transition WordsByPinyin field to data/characters.json.

Polyphonic characters use the reviewed feng_word_reading_decisions.applied.json
artifact as the source of truth. Monophonic characters are wrapped mechanically.
Legacy Words stays unchanged. Any reviewed-artifact override vs legacy Words is
recorded in an audit report for follow-up review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
OUTER_APP_DIR = ROOT.parent
CHARACTERS_JSON = OUTER_APP_DIR / "data" / "characters.json"
REVIEWED_ARTIFACT = ROOT / "review" / "feng_word_reading_decisions.applied.json"
DEFAULT_AUDIT_PATH = OUTER_APP_DIR / "data" / "feng_words_by_pinyin_audit.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_string_list(values) -> list[str]:
    return [str(value).strip() for value in (values or []) if isinstance(value, str) and str(value).strip()]


def build_review_lookup(artifact: dict) -> dict[str, dict]:
    lookup = {}
    for item in artifact.get("characters") or []:
        character = (item.get("character") or "").strip()
        if character:
            lookup[character] = item
    return lookup


def build_monophonic_words_by_pinyin(pinyin: list[str], legacy_words: list[str]) -> list[dict]:
    if not pinyin:
        return []
    return [{"Pinyin": pinyin[0], "Phrases": list(legacy_words)}]


def build_polyphonic_words_by_pinyin(
    character: str,
    pinyin: list[str],
    review_item: dict,
) -> list[dict]:
    bucket_map = {reading: [] for reading in pinyin}
    for result in review_item.get("results") or []:
        phrase = (result.get("text") or "").strip()
        reading = (result.get("reading") or "").strip()
        if not phrase:
            continue
        if not reading or reading == "unknown":
            raise ValueError(f"{character}: reviewed phrase {phrase!r} has no resolved reading")
        if reading not in bucket_map:
            raise ValueError(f"{character}: reviewed reading {reading!r} not present in Feng pinyin {pinyin}")
        bucket_map[reading].append(phrase)
    return [{"Pinyin": reading, "Phrases": bucket_map[reading]} for reading in pinyin]


def flatten_words_by_pinyin(words_by_pinyin: list[dict]) -> list[str]:
    flattened = []
    seen = set()
    for bucket in words_by_pinyin:
        for phrase in bucket.get("Phrases") or []:
            phrase_text = (phrase or "").strip()
            if phrase_text and phrase_text not in seen:
                flattened.append(phrase_text)
                seen.add(phrase_text)
    return flattened


def build_audit_entry(index: str, character: str, legacy_words: list[str], reviewed_words: list[str]) -> dict:
    legacy_set = set(legacy_words)
    reviewed_set = set(reviewed_words)
    return {
        "index": index,
        "character": character,
        "legacy_words": legacy_words,
        "reviewed_words": reviewed_words,
        "missing_from_reviewed": [word for word in legacy_words if word not in reviewed_set],
        "extra_in_reviewed": [word for word in reviewed_words if word not in legacy_set],
        "order_differs": legacy_words != reviewed_words and legacy_set == reviewed_set,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the transition WordsByPinyin field for Feng characters.")
    parser.add_argument("--characters", type=Path, default=CHARACTERS_JSON, help="Path to characters.json")
    parser.add_argument("--artifact", type=Path, default=REVIEWED_ARTIFACT, help="Path to reviewed Feng artifact")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT_PATH, help="Where to write the discrepancy audit report")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print summary without modifying characters.json")
    args = parser.parse_args()

    if not args.characters.exists():
        print(f"Not found: {args.characters}", file=sys.stderr)
        sys.exit(1)
    if not args.artifact.exists():
        print(f"Not found: {args.artifact}", file=sys.stderr)
        sys.exit(1)

    characters = load_json(args.characters)
    artifact = load_json(args.artifact)
    review_lookup = build_review_lookup(artifact)

    polyphonic_count = 0
    audit_entries = []
    missing_review_characters = []

    for entry in characters:
        character = (entry.get("Character") or "").strip()
        index = (entry.get("Index") or "").strip()
        pinyin = normalize_string_list(entry.get("Pinyin") or [])
        legacy_words = normalize_string_list(entry.get("Words") or [])

        if len(pinyin) <= 1:
            entry["WordsByPinyin"] = build_monophonic_words_by_pinyin(pinyin, legacy_words)
            continue

        polyphonic_count += 1
        review_item = review_lookup.get(character)
        if not review_item:
            missing_review_characters.append({"index": index, "character": character, "pinyin": pinyin})
            entry["WordsByPinyin"] = [{"Pinyin": reading, "Phrases": []} for reading in pinyin]
            continue

        words_by_pinyin = build_polyphonic_words_by_pinyin(character, pinyin, review_item)
        entry["WordsByPinyin"] = words_by_pinyin

        reviewed_words = flatten_words_by_pinyin(words_by_pinyin)
        if legacy_words != reviewed_words:
            audit_entries.append(build_audit_entry(index, character, legacy_words, reviewed_words))

    if missing_review_characters:
        print("Missing reviewed artifact entries for polyphonic characters:", file=sys.stderr)
        for item in missing_review_characters[:20]:
            print(f"  {item['index']} {item['character']} {item['pinyin']}", file=sys.stderr)
        sys.exit(1)

    audit_payload = {
        "summary": {
            "characters_total": len(characters),
            "polyphonic_characters": polyphonic_count,
            "reviewed_polyphonic_characters": len(review_lookup),
            "discrepancy_count": len(audit_entries),
        },
        "discrepancies": audit_entries,
    }

    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.dry_run:
        args.characters.write_text(json.dumps(characters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Characters: {len(characters)}")
    print(f"Polyphonic characters: {polyphonic_count}")
    print(f"Artifact-reviewed polyphonic characters: {len(review_lookup)}")
    print(f"Audit discrepancies: {len(audit_entries)}")
    print(f"Audit report: {args.audit}")
    if args.dry_run:
        print("Dry run only: characters.json was not modified")
    else:
        print(f"Updated: {args.characters}")


if __name__ == "__main__":
    main()
