#!/usr/bin/env python3
"""
Validate the applied Feng word reading review artifact.

Run from repo root:
  python3 chinese_chr_app/tag_character_pinyin_using_review/scripts/validate_feng_word_review_results.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = ROOT / "review" / "feng_word_reading_decisions.applied.json"


def load_payload(path: Path) -> dict:
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def validate(payload: dict) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    characters = payload.get("characters")
    if not isinstance(characters, list):
        return ["Top-level 'characters' must be a list."], warnings, info

    actual_character_count = len(characters)
    actual_total_words = 0
    actual_decided_words = 0
    actual_undecided_words = 0

    seen_characters: set[str] = set()
    characters_with_extra_readings: list[str] = []
    characters_missing_allowed_coverage: list[str] = []
    characters_with_unused_extra_readings: list[str] = []

    for idx, character_block in enumerate(characters, start=1):
        if not isinstance(character_block, dict):
            errors.append(f"characters[{idx - 1}] is not an object.")
            continue

        character = (character_block.get("character") or "").strip()
        if not character:
            errors.append(f"characters[{idx - 1}] has no character value.")
            continue
        if character in seen_characters:
            errors.append(f"Duplicate character entry found for {character!r}.")
        seen_characters.add(character)

        allowed_readings = character_block.get("allowed_readings") or []
        extra_readings = character_block.get("extra_readings") or []
        results = character_block.get("results") or []

        if not isinstance(allowed_readings, list):
            errors.append(f"{character}: allowed_readings must be a list.")
            allowed_readings = []
        if not isinstance(extra_readings, list):
            errors.append(f"{character}: extra_readings must be a list.")
            extra_readings = []
        if not isinstance(results, list):
            errors.append(f"{character}: results must be a list.")
            results = []

        allowed_readings = [
            reading.strip()
            for reading in allowed_readings
            if isinstance(reading, str) and reading.strip()
        ]
        extra_readings = [
            reading.strip()
            for reading in extra_readings
            if isinstance(reading, str) and reading.strip()
        ]

        if not allowed_readings:
            warnings.append(f"{character}: no allowed_readings listed.")

        declared_readings = set(allowed_readings) | set(extra_readings)
        assigned_counts: Counter[str] = Counter()

        if extra_readings:
            characters_with_extra_readings.append(
                f"{character}: extras={extra_readings!r}, allowed={allowed_readings!r}"
            )

        for result_index, result in enumerate(results, start=1):
            if not isinstance(result, dict):
                errors.append(f"{character}: results[{result_index - 1}] is not an object.")
                continue

            actual_total_words += 1

            text = (result.get("text") or "").strip()
            reading = (result.get("reading") or "").strip()
            notes = result.get("notes")
            source = (result.get("source") or "").strip()

            if not text:
                errors.append(f"{character}: results[{result_index - 1}] has empty text.")

            if reading and reading != "unknown":
                actual_decided_words += 1
                assigned_counts[reading] += 1
                if reading not in declared_readings:
                    errors.append(
                        f"{character}: word {text!r} uses reading {reading!r}, "
                        "which is not in allowed_readings or extra_readings."
                    )
            else:
                actual_undecided_words += 1

            if notes is not None and not isinstance(notes, str):
                errors.append(f"{character}: word {text!r} has non-string notes.")

            if not source:
                warnings.append(f"{character}: word {text!r} has empty source.")

        missing_allowed = [
            reading for reading in allowed_readings if assigned_counts.get(reading, 0) == 0
        ]
        if missing_allowed:
            characters_missing_allowed_coverage.append(
                f"{character}: missing assignments for allowed_readings={missing_allowed!r}"
            )

        unused_extra = [
            reading for reading in extra_readings if assigned_counts.get(reading, 0) == 0
        ]
        if unused_extra:
            characters_with_unused_extra_readings.append(
                f"{character}: unused extra_readings={unused_extra!r}"
            )

    if payload.get("character_count") != actual_character_count:
        errors.append(
            "character_count mismatch: "
            f"expected {actual_character_count}, found {payload.get('character_count')!r}"
        )
    if payload.get("total_words") != actual_total_words:
        errors.append(
            "total_words mismatch: "
            f"expected {actual_total_words}, found {payload.get('total_words')!r}"
        )
    if payload.get("decided_words") != actual_decided_words:
        errors.append(
            "decided_words mismatch: "
            f"expected {actual_decided_words}, found {payload.get('decided_words')!r}"
        )
    if payload.get("undecided_words") != actual_undecided_words:
        errors.append(
            "undecided_words mismatch: "
            f"expected {actual_undecided_words}, found {payload.get('undecided_words')!r}"
        )

    if characters_missing_allowed_coverage:
        warnings.append(
            "Allowed readings with no tagged words:\n  - "
            + "\n  - ".join(characters_missing_allowed_coverage)
        )
    if characters_with_unused_extra_readings:
        warnings.append(
            "Declared extra_readings with no tagged words:\n  - "
            + "\n  - ".join(characters_with_unused_extra_readings)
        )
    if characters_with_extra_readings:
        info.append(
            "Characters with extra pinyin tagging beyond allowed_readings:\n  - "
            + "\n  - ".join(characters_with_extra_readings)
        )
    else:
        info.append("Characters with extra pinyin tagging beyond allowed_readings: none")

    info.append(
        "Artifact counts: "
        f"characters={actual_character_count}, "
        f"words={actual_total_words}, "
        f"decided={actual_decided_words}, "
        f"undecided={actual_undecided_words}"
    )

    return errors, warnings, info


def print_section(title: str, items: list[str]) -> None:
    print(title)
    if not items:
        print("  none")
        return
    for item in items:
        for line in item.splitlines():
            print(f"  {line}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate reviewed Feng word reading results.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to feng_word_reading_decisions.applied.json",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as errors.",
    )
    args = parser.parse_args()

    payload = load_payload(args.input)
    errors, warnings, info = validate(payload)

    print(f"Validated: {args.input}")
    print_section("Errors", errors)
    print_section("Warnings", warnings)
    print_section("Info", info)

    if errors or (args.strict and warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
