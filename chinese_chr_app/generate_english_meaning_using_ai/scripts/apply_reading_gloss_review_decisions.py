#!/usr/bin/env python3
"""
Apply reading-gloss review decisions to produce a curated reviewed artifact.

Usage:
  python3 apply_reading_gloss_review_decisions.py
  python3 apply_reading_gloss_review_decisions.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"

READING_GLOSSES_JSON = BATCH_ARTIFACTS / "reading_glosses.json"
DECISIONS_JSON = BATCH_ARTIFACTS / "reading_gloss_review_decisions.json"
OUTPUT_JSON = BATCH_ARTIFACTS / "reading_glosses.reviewed.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply reading-gloss review decisions")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output")
    parser.add_argument("--output", type=Path, default=OUTPUT_JSON, help="Reviewed output JSON path")
    args = parser.parse_args()

    if not READING_GLOSSES_JSON.exists():
        print(f"Error: missing {READING_GLOSSES_JSON}", file=sys.stderr)
        sys.exit(1)
    if not DECISIONS_JSON.exists():
        print(f"Error: missing {DECISIONS_JSON}", file=sys.stderr)
        sys.exit(1)

    glosses = load_json(READING_GLOSSES_JSON)
    decisions = load_json(DECISIONS_JSON)

    reviewed = {}
    accept_count = 0
    edit_count = 0
    unchanged_count = 0

    for unit_id, gloss in glosses.items():
        item = json.loads(json.dumps(gloss, ensure_ascii=False))
        decision = decisions.get(unit_id)
        if decision:
            item["review_status"] = "reviewed"
            item["review_decision"] = decision.get("decision")
            notes = decision.get("notes")
            if notes:
                item["review_notes"] = notes

            if decision.get("decision") == "edit":
                edited_gloss = (decision.get("edited_english_gloss") or "").strip()
                edited_short = decision.get("edited_short_glosses") or []
                if edited_gloss:
                    item["english_gloss"] = edited_gloss
                if isinstance(edited_short, list):
                    cleaned = [str(x).strip() for x in edited_short if str(x).strip()]
                    if cleaned:
                        item["short_glosses"] = cleaned
                edit_count += 1
            else:
                accept_count += 1

            qc = item.setdefault("qc_flags", {})
            qc["needs_human_review"] = False
            qc["review_reason"] = None
        else:
            item["review_status"] = "unreviewed"
            unchanged_count += 1

        reviewed[unit_id] = item

    print(f"Total glosses: {len(reviewed)}", file=sys.stderr)
    print(f"Reviewed accepts: {accept_count}", file=sys.stderr)
    print(f"Reviewed edits: {edit_count}", file=sys.stderr)
    print(f"Unreviewed unchanged: {unchanged_count}", file=sys.stderr)

    if args.dry_run:
        print("Dry run: no files written", file=sys.stderr)
        return

    args.output.write_text(
        json.dumps(reviewed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote reviewed glosses to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
