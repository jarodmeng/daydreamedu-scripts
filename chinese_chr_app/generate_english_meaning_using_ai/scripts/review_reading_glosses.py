#!/usr/bin/env python3
"""
Review reading-level English gloss results from the batch run.

This CLI is intentionally simple: it lists flagged units and lets you accept,
edit, or skip them while saving decisions to a JSON file so review can be
resumed later.

Usage:
  python3 review_reading_glosses.py list
  python3 review_reading_glosses.py review
  python3 review_reading_glosses.py review --unit-id 叉|cha4
  python3 review_reading_glosses.py review --include-reviewed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"

READING_UNITS_JSON = BATCH_ARTIFACTS / "reading_units_polyphonic.json"
READING_GLOSSES_JSON = BATCH_ARTIFACTS / "reading_glosses.json"
DECISIONS_JSON = BATCH_ARTIFACTS / "reading_gloss_review_decisions.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_unit_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        row["unit_id"]: row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("unit_id"), str)
    }


def build_flagged_items(
    units_by_id: dict[str, dict[str, Any]],
    glosses_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items = []
    for unit_id, gloss in glosses_by_id.items():
        qc = gloss.get("qc_flags") or {}
        if not qc.get("needs_human_review"):
            continue
        unit = units_by_id.get(unit_id) or {}
        items.append(
            {
                "unit_id": unit_id,
                "unit": unit,
                "gloss": gloss,
                "confidence_score": gloss.get("confidence_score"),
                "review_reason": qc.get("review_reason"),
            }
        )
    items.sort(
        key=lambda item: (
            99 if item.get("confidence_score") is None else item["confidence_score"],
            item["unit_id"],
        )
    )
    return items


def summarize(items: list[dict[str, Any]], decisions: dict[str, Any]) -> tuple[int, int, int]:
    total = len(items)
    reviewed = sum(1 for item in items if item["unit_id"] in decisions)
    pending = total - reviewed
    accepted = sum(
        1
        for item in items
        if (decisions.get(item["unit_id"]) or {}).get("decision") == "accept"
    )
    return total, reviewed, pending + accepted - accepted


def print_item(item: dict[str, Any], decision: dict[str, Any] | None = None) -> None:
    unit = item["unit"]
    gloss = item["gloss"]
    print("=" * 80)
    print(f"{item['unit_id']}  confidence={item.get('confidence_score')}")
    print(f"Review reason: {item.get('review_reason')}")
    if decision:
        print(f"Saved decision: {decision.get('decision')}")
        if decision.get("edited_english_gloss"):
            print(f"Saved edited gloss: {decision['edited_english_gloss']}")
        if decision.get("edited_short_glosses"):
            print(f"Saved edited short glosses: {decision['edited_short_glosses']}")
        if decision.get("notes"):
            print(f"Saved notes: {decision['notes']}")
    print()
    print(f"Model english_gloss: {gloss.get('english_gloss')}")
    print(f"Model short_glosses: {gloss.get('short_glosses')}")
    print()
    print(f"Reading: {unit.get('reading')}  All readings: {unit.get('all_readings')}")
    print(f"Likely needs review: {unit.get('likely_needs_review')}  reason={unit.get('likely_review_reason')}")
    print(f"Evidence summary: {unit.get('evidence_summary')}")
    print()
    print(f"Feng WordsByPinyin: {unit.get('reading_feng_words_by_pinyin')}")
    print(f"HWXNet 常用词组按拼音: {unit.get('reading_common_phrases_by_pinyin')}")
    print(f"basic_meanings 例词 / merged examples: {unit.get('reading_example_phrases')}")
    print()
    print("Reading basic_meanings:")
    print(json.dumps(unit.get("reading_basic_meanings"), ensure_ascii=False, indent=2))
    print()
    print("CC-CEDICT candidates:")
    print(json.dumps(unit.get("cedict_candidates"), ensure_ascii=False, indent=2))
    print()


def run_list(items: list[dict[str, Any]], decisions: dict[str, Any], limit: int | None) -> None:
    total = len(items)
    reviewed = sum(1 for item in items if item["unit_id"] in decisions)
    pending = total - reviewed
    print(f"Flagged units: {total}  reviewed: {reviewed}  pending: {pending}")
    shown = 0
    for item in items:
        if limit is not None and shown >= limit:
            break
        decision = decisions.get(item["unit_id"])
        status = decision.get("decision") if isinstance(decision, dict) else "pending"
        print(
            f"{item['unit_id']}\tconfidence={item.get('confidence_score')}\tstatus={status}\treason={item.get('review_reason')}"
        )
        shown += 1


def prompt_choice() -> str:
    while True:
        value = input("[a]ccept / [e]dit / [s]kip / [q]uit: ").strip().lower()
        if value in {"a", "e", "s", "q"}:
            return value
        print("Please enter a, e, s, or q.")


def prompt_notes() -> str:
    return input("Notes (optional): ").strip()


def prompt_edit(gloss: dict[str, Any]) -> tuple[str, list[str]]:
    current_gloss = gloss.get("english_gloss") or ""
    current_short = gloss.get("short_glosses") or []
    print(f"Current english_gloss: {current_gloss}")
    new_gloss = input("Edited english_gloss: ").strip()
    print(f"Current short_glosses: {current_short}")
    short_line = input("Edited short_glosses (semicolon-separated): ").strip()
    short_glosses = [part.strip() for part in short_line.split(";") if part.strip()]
    return new_gloss, short_glosses


def run_review(
    items: list[dict[str, Any]],
    decisions: dict[str, Any],
    *,
    include_reviewed: bool,
    limit: int | None,
    unit_id: str | None,
) -> int:
    count = 0
    filtered = items
    if unit_id:
        filtered = [item for item in filtered if item["unit_id"] == unit_id]
    if not include_reviewed:
        filtered = [item for item in filtered if item["unit_id"] not in decisions]
    if limit is not None:
        filtered = filtered[:limit]

    if not filtered:
        print("No matching review items.")
        return 0

    for item in filtered:
        count += 1
        print_item(item, decisions.get(item["unit_id"]))
        choice = prompt_choice()
        if choice == "q":
            break
        if choice == "s":
            continue

        payload = {
            "decision": "accept" if choice == "a" else "edit",
            "notes": prompt_notes(),
        }
        if choice == "e":
            edited_gloss, edited_short = prompt_edit(item["gloss"])
            payload["edited_english_gloss"] = edited_gloss
            payload["edited_short_glosses"] = edited_short
        decisions[item["unit_id"]] = payload
        save_json(DECISIONS_JSON, decisions)
        print(f"Saved decision for {item['unit_id']}.")
        print()

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Review flagged reading-level glosses")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in ("list", "review"):
        sub = subparsers.add_parser(command_name)
        sub.add_argument("--limit", type=int, default=None)
        sub.add_argument("--unit-id", type=str, default=None)
        if command_name == "review":
            sub.add_argument("--include-reviewed", action="store_true")

    args = parser.parse_args()

    if not READING_UNITS_JSON.exists() or not READING_GLOSSES_JSON.exists():
        print(
            "Missing reading_units_polyphonic.json or reading_glosses.json.\n"
            "Build/process the batch outputs first.",
            file=sys.stderr,
        )
        sys.exit(1)

    units_by_id = build_unit_lookup(load_json(READING_UNITS_JSON))
    glosses_by_id = load_json(READING_GLOSSES_JSON)
    decisions = load_json(DECISIONS_JSON) if DECISIONS_JSON.exists() else {}

    items = build_flagged_items(units_by_id, glosses_by_id)

    if args.command == "list":
        if args.unit_id:
            items = [item for item in items if item["unit_id"] == args.unit_id]
        run_list(items, decisions, args.limit)
        return

    run_review(
        items,
        decisions,
        include_reviewed=args.include_reviewed,
        limit=args.limit,
        unit_id=args.unit_id,
    )


if __name__ == "__main__":
    main()
